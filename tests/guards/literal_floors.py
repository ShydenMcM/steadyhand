"""A floor typed into a Python test (#272): a lower bound written as a number, which is tight only
on the day it is measured. Floors live in ``extension/tests/floors.json``, read through
``floors.floor_breach``; this reader finds every lower bound a test typed in.

Shyden's decisions (2026-10-20, on #272):

- A literal floor is EVERY typed-in lower bound, as in TypeScript, with no exemption. A bound of 0
  is a non-emptiness check and a ceiling is a budget, as in
  ``extension/tests/lib/literal-floors.ts``.
- A bound that uses a name the reader cannot trace to a value is refused, never read as safe.
- Everything in our own code is followed: a name, a function, a method (by its name), a module's
  attribute, a function stored in a name. Only an outside library's value or result passes, as
  computed by code we do not control.
- A number used only as an index or slice is not a value the bound takes; a container's own
  numbers still count.
- Python's ``a < b`` does not say which side is measured, so both sides are judged.
- A number written as text (``Decimal("0.0001")``) is a number. A check written outside an assert
  (``if n < 5: pytest.fail(...)``, ``raise AssertionError``, unittest's ``assertGreater`` family) is
  read as well.

A bound is judged by every node in it, not its top node only (#362). A name is looked up where it is
used, through the enclosing functions out to the module, as Python looks it up, and judged by every
value its scope binds it to. A call into our code is followed to what it returns, with each
parameter standing for that call's argument.
"""

import ast
import builtins
import io
import re
import tokenize
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from pathlib import Path

FLOOR_NAME = re.compile(r"floor", re.IGNORECASE)
LOWER = (ast.Gt, ast.GtE)
UPPER = (ast.Lt, ast.LtE)
CONTAINERS = (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.JoinedStr)
# Names every module has without binding them: built-ins and the module's own attributes.
GIVEN = frozenset(dir(builtins)) | {"__file__", "__name__", "__doc__", "__package__", "__spec__"}
# unittest's bound assertions, by which argument bounds the other from below.
UNITTEST_BOUNDS = {
    "assertGreater": 1,
    "assertGreaterEqual": 1,
    "assertLess": 0,
    "assertLessEqual": 0,
}

# Why a name cannot be traced, by how the code binds it.
LOOP = "a loop over values the test made"
PARAMETER = "a fixture or helper parameter"
UNBOUND = "never bound in this file"

type Function = ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda
COMPREHENSIONS = (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
SCOPES = (
    ast.Module,
    ast.FunctionDef,
    ast.AsyncFunctionDef,
    ast.Lambda,
    ast.ClassDef,
    *COMPREHENSIONS,
)


class UnreadableSourceError(AssertionError):
    """A file the reader cannot parse: it is refused by name, never read as having no floors."""


@dataclass(frozen=True)
class Reading:
    """What one file holds: how many asserts and other checks were judged, and every literal floor
    among them."""

    asserts: int
    checks: int
    findings: list[str]


@dataclass(frozen=True)
class Binding:
    """One way the code binds a name: to the values it may take, to a function, to a name imported
    from a module, or to the reason the reader cannot say what it holds. A binding with none of
    these (a class, a caught error) holds no number."""

    values: tuple[ast.expr, ...] = ()
    untraceable: str | None = None
    function: Function | None = None
    imported: tuple[str, str | None] | None = None


@dataclass(frozen=True)
class Verdict:
    typed_in: bool
    untraceable: tuple[str, str] | None


COMPUTED = Verdict(typed_in=False, untraceable=None)
TYPED_IN = Verdict(typed_in=True, untraceable=None)


def _merge(verdicts: Iterator[Verdict]) -> Verdict:
    """A typed-in number anywhere wins; otherwise the first name that cannot be traced."""
    untraceable: tuple[str, str] | None = None
    for verdict in verdicts:
        if verdict.typed_in:
            return verdict
        untraceable = untraceable or verdict.untraceable
    return Verdict(typed_in=False, untraceable=untraceable)


def _is_number(node: ast.AST) -> bool:
    """A number written in the source, as a number or as text, other than 0 (a bound of 0 is a
    non-emptiness check)."""
    if not isinstance(node, ast.Constant) or isinstance(node.value, bool):
        return False
    if isinstance(node.value, (int, float, complex)):
        return node.value != 0
    if isinstance(node.value, str):
        try:
            written = Decimal(node.value.strip())
        except InvalidOperation:
            return False
        return written.is_finite() and written != 0
    return False


def _value_nodes(expression: ast.AST) -> Iterator[ast.AST]:
    """Every node of *expression* that can give it its value: an index or slice picks a value out of
    a container but is not one, so it is left out (Shyden, 2026-10-20, on #272: ``parents[2]`` is
    no floor). The container itself is still read, so ``LIMITS[2]`` reads ``LIMITS``."""
    yield expression
    for name, child in ast.iter_fields(expression):
        if isinstance(expression, ast.Subscript) and name == "slice":
            continue
        for one in child if isinstance(child, list) else [child]:
            if isinstance(one, ast.AST):
                yield from _value_nodes(one)


def _names(target: ast.AST) -> Iterator[ast.Name]:
    yield from (node for node in ast.walk(target) if isinstance(node, ast.Name))


def _column(row: ast.expr, index: int, width: int) -> ast.expr:
    """The value a parametrize row gives the parameter at *index*, or the whole row when the reader
    cannot split it (it is then judged whole, so a number in it still counts)."""
    if isinstance(row, ast.Call) and ast.unparse(row.func).endswith("param"):
        cells = row.args
    elif width > 1 and isinstance(row, (ast.Tuple, ast.List)):
        cells = row.elts
    else:
        return row
    return cells[index] if index < len(cells) else row


def _parametrized(function: Function) -> dict[str, list[ast.expr]]:
    """The values each parameter takes from ``@pytest.mark.parametrize``, by parameter name."""
    found: dict[str, list[ast.expr]] = {}
    for decorator in [] if isinstance(function, ast.Lambda) else function.decorator_list:
        if not (
            isinstance(decorator, ast.Call)
            and ast.unparse(decorator.func).endswith("parametrize")
            and len(decorator.args) > 1
        ):
            continue
        names_node, values_node = decorator.args[0], decorator.args[1]
        if isinstance(names_node, ast.Constant) and isinstance(names_node.value, str):
            names = [name.strip() for name in names_node.value.split(",")]
        elif isinstance(names_node, (ast.Tuple, ast.List)):
            names = [ast.literal_eval(element) for element in names_node.elts]
        else:
            continue
        rows = (
            list(values_node.elts)
            if isinstance(values_node, (ast.List, ast.Tuple))
            else [values_node]
        )
        for index, name in enumerate(names):
            found.setdefault(name, []).extend(_column(row, index, len(names)) for row in rows)
    return found


def _parameters(function: Function) -> list[ast.arg]:
    arguments = function.args
    extras = [extra for extra in (arguments.vararg, arguments.kwarg) if extra is not None]
    return [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs, *extras]


def _defaults(function: Function) -> dict[str, ast.expr]:
    arguments = function.args
    positional = [*arguments.posonlyargs, *arguments.args]
    named = [argument.arg for argument in positional[len(positional) - len(arguments.defaults) :]]
    defaults = dict(zip(named, arguments.defaults, strict=True))
    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
        if default is not None:
            defaults[argument.arg] = default
    return defaults


class _Module:
    """One file of our code, parsed once: the scope each node sits in, and every binding each scope
    makes, by name."""

    def __init__(self, name: str, tree: ast.Module) -> None:
        self.name = name
        self.tree = tree
        self.scope_of: dict[int, ast.AST] = {}
        self.parent: dict[int, ast.AST | None] = {id(tree): None}
        self.bindings: dict[int, dict[str, list[Binding]]] = {}
        self.globals: dict[int, set[str]] = {}
        self.methods: dict[str, list[Function]] = {}
        self.attributes: dict[str, list[ast.expr]] = {}
        self._place(tree, tree)
        for node in ast.walk(tree):
            self._collect(node)

    def _place(self, node: ast.AST, scope: ast.AST) -> None:
        """Record the scope of *node* and everything under it. A function's decorators and
        defaults sit in the scope around it; its parameters and body in its own."""
        self.scope_of[id(node)] = scope
        if not isinstance(node, SCOPES) or node is scope:
            for child in ast.iter_child_nodes(node):
                self._place(child, scope)
            return
        self.parent[id(node)] = scope
        outer: list[ast.AST] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            outer += node.decorator_list
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            outer += [*node.args.defaults, *(d for d in node.args.kw_defaults if d is not None)]
        if isinstance(node, ast.ClassDef):
            outer += [*node.bases, *node.keywords]
        for child in outer:
            self._place(child, scope)
        placed = {id(child) for child in outer}
        for child in ast.iter_child_nodes(node):
            if id(child) not in placed:
                self._place(child, node)

    def add(self, at: ast.AST, name: str, binding: Binding) -> None:
        scope = self.scope_of[id(at)]
        self.bindings.setdefault(id(scope), {}).setdefault(name, []).append(binding)

    def _function_scope(self, at: ast.AST) -> ast.AST:
        """The scope a walrus binds in: the nearest one that is not a comprehension."""
        scope = self.scope_of[id(at)]
        while isinstance(scope, COMPREHENSIONS):
            scope = self.parent[id(scope)] or self.tree
        return scope

    def _assigned(self, target: ast.expr, value: ast.expr) -> None:
        if (
            isinstance(target, (ast.Tuple, ast.List))
            and isinstance(value, (ast.Tuple, ast.List))
            and len(target.elts) == len(value.elts)
        ):
            for one_target, one_value in zip(target.elts, value.elts, strict=True):
                self._assigned(one_target, one_value)
            return
        for name in _names(target):
            self.add(name, name.id, Binding(values=(value,)))

    def _attribute(self, target: ast.expr, value: ast.expr) -> None:
        """An attribute given a value, by its name: ``x.least = 5``, or ``least = 5`` (and a
        dataclass's ``least: int = 5``) in a class body."""
        if isinstance(target, ast.Attribute):
            self.attributes.setdefault(target.attr, []).append(value)
        elif isinstance(target, ast.Name) and isinstance(self.scope_of[id(target)], ast.ClassDef):
            self.attributes.setdefault(target.id, []).append(value)

    def _collect(self, node: ast.AST) -> None:
        """The bindings *node* makes by giving a name a value: an assignment, a loop, a ``with``."""
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and node.value is not None:
            for target in node.targets if isinstance(node, ast.Assign) else [node.target]:
                self._attribute(target, node.value)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                self._assigned(target, node.value)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            if node.value is not None:
                self._assigned(node.target, node.value)
        elif isinstance(node, ast.NamedExpr):
            scope = self._function_scope(node)
            binding = Binding(values=(node.value,))
            self.bindings.setdefault(id(scope), {}).setdefault(node.target.id, []).append(binding)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            self._looped(node.target, node.iter)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    self._assigned(item.optional_vars, item.context_expr)
        else:
            self._declared(node)

    def _looped(self, target: ast.expr, over: ast.expr) -> None:
        """A loop over values written in the file binds its names to them; any other loop binds
        them to values the test made, which the reader cannot see."""
        for name in _names(target):
            if isinstance(over, (ast.Tuple, ast.List, ast.Set)):
                self.add(name, name.id, Binding(values=tuple(over.elts)))
            else:
                self.add(name, name.id, Binding(untraceable=LOOP))

    def _declared(self, node: ast.AST) -> None:
        """The bindings *node* makes by declaring a name: a function and its parameters, a lambda's
        parameters, an import, a class and its methods, a caught error, a ``global``."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            self._function(node)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            self._import(node)
        elif isinstance(node, ast.ClassDef):
            self.add(node, node.name, Binding())
            for statement in node.body:
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.methods.setdefault(statement.name, []).append(statement)
        elif isinstance(node, ast.ExceptHandler) and node.name is not None:
            self.add(node, node.name, Binding())
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            self.globals.setdefault(id(self.scope_of[id(node)]), set()).update(node.names)

    def _function(self, node: Function) -> None:
        """A function binds its name where it is written, and its parameters in its own scope: to
        their parametrize values and default, or, with neither, to a value the reader cannot see."""
        if not isinstance(node, ast.Lambda):
            self.add(node, node.name, Binding(function=node))
        parametrized = _parametrized(node)
        defaults = _defaults(node)
        for argument in _parameters(node):
            values = [*parametrized.get(argument.arg, [])]
            values += [defaults[argument.arg]] if argument.arg in defaults else []
            binding = Binding(values=tuple(values), untraceable=None if values else PARAMETER)
            self.add(argument, argument.arg, binding)

    def _import(self, node: ast.Import | ast.ImportFrom) -> None:
        """An import binds each name to the module, and the name in it, that it comes from."""
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname is None:
                    root = alias.name.split(".")[0]
                    self.add(node, root, Binding(imported=(root, None)))
                else:
                    self.add(node, alias.asname, Binding(imported=(alias.name, None)))
        elif node.module is not None:
            for alias in node.names:
                imported = (node.module, alias.name)
                self.add(node, alias.asname or alias.name, Binding(imported=imported))

    def lookup(self, name: str, at: ast.AST) -> tuple[ast.AST, list[Binding]] | None:
        """The scope that binds *name* as seen from *at*, with its bindings, or ``None``. A class
        body's names are not seen from the functions inside it."""
        start = self.scope_of.get(id(at), self.tree)
        scope: ast.AST | None = start
        while scope is not None:
            if name in self.globals.get(id(scope), set()):
                scope = self.tree
            found = self.bindings.get(id(scope), {}).get(name)
            if found is not None and (scope is start or not isinstance(scope, ast.ClassDef)):
                return scope, found
            scope = self.parent.get(id(scope))
        return None


class Project:
    """Our own code, by module name: the reader follows a name into it. A module not here is an
    outside library, whose values and results pass as computed by code we do not control."""

    def __init__(self, sources: Mapping[str, str]) -> None:
        self.sources = dict(sources)
        self._modules: dict[str, _Module] = {}

    @classmethod
    def of_files(cls, roots: Mapping[Path, list[Path]]) -> "Project":
        """The project made of *roots*: each import root (a folder on the import path) with the
        Python files under it. A file's module name is its path from its root; the first root to
        hold a name wins, as Python's own import does."""
        sources: dict[str, str] = {}
        for root, files in roots.items():
            for path in files:
                parts = path.relative_to(root).with_suffix("").parts
                parts = parts[:-1] if parts[-1] == "__init__" else parts
                if parts:
                    sources.setdefault(".".join(parts), path.read_text(encoding="utf-8"))
        return cls(sources)

    def module(self, name: str) -> _Module | None:
        if name not in self.sources:
            return None
        if name not in self._modules:
            try:
                tree = ast.parse(self.sources[name], name)
            except (SyntaxError, ValueError) as error:
                msg = f"our module {name}: cannot parse it ({error})"
                raise UnreadableSourceError(msg) from error
            self._modules[name] = _Module(name, tree)
        return self._modules[name]

    def attributes(self, name: str) -> list[tuple[_Module, ast.expr]]:
        """Every value our code gives an attribute named *name*: followed by its name, since the
        reader cannot tell which object an attribute is read from."""
        found = []
        for module_name in self.sources:
            module = self.module(module_name)
            if module is not None:
                found += [(module, value) for value in module.attributes.get(name, [])]
        return found

    def methods(self, name: str) -> list[tuple[_Module, Function]]:
        """Every method named *name* in our code: a method is followed by its name, since the
        reader cannot tell which class an object belongs to."""
        found = []
        for module_name in self.sources:
            module = self.module(module_name)
            if module is not None:
                found += [(module, method) for method in module.methods.get(name, [])]
        return found


type Frame = Mapping[tuple[int, str], tuple["_Context", ast.expr]]


@dataclass(frozen=True)
class _Context:
    """The module an expression is written in, and while calls are followed, each followed
    function's parameters with the arguments the call gave them (judged where the call was)."""

    module: _Module
    frame: Frame = field(default_factory=dict)


@dataclass(frozen=True)
class _Argument:
    """A parameter of a followed call: the argument the call gave it, judged where the call was."""

    context: _Context
    expression: ast.expr


@dataclass(frozen=True)
class _Found:
    """The scope that binds a name, with every binding it makes of it."""

    scope: ast.AST
    bindings: list[Binding]


class _Judge:
    """Whether an expression's value can be a number typed into our code."""

    def __init__(self, project: Project) -> None:
        self.project = project

    def verdict(self, expression: ast.AST, context: _Context, seen: frozenset[object]) -> Verdict:
        chains = _chains(expression)
        called = {
            id(node.func)
            for node in ast.walk(expression)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        return _merge(
            self._node(node, chains, context, seen)
            for node in _value_nodes(expression)
            if id(node) not in called
        )

    def _node(
        self,
        node: ast.AST,
        chains: dict[int, list[str]],
        context: _Context,
        seen: frozenset[object],
    ) -> Verdict:
        if _is_number(node):
            return TYPED_IN
        if isinstance(node, ast.Call):
            return self._called(node, context, seen)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            attributes = chains.get(id(node))
            if attributes is not None:
                return self._chain(node, attributes, context, seen)
            return self.name(node.id, node, context, seen)
        return COMPUTED

    def _bindings(self, name: str, at: ast.AST, context: _Context) -> _Argument | _Found | None:
        """What *name* is, seen from *at*: the argument a followed call gave it, or its scope and
        bindings, or ``None`` when nothing binds it."""
        found = context.module.lookup(name, at)
        if found is None:
            return None
        scope, bindings = found
        argument = context.frame.get((id(scope), name))
        return _Argument(*argument) if argument is not None else _Found(scope, bindings)

    def name(self, name: str, at: ast.AST, context: _Context, seen: frozenset[object]) -> Verdict:
        """A name used as a value: an argument standing for a parameter, or every binding of it."""
        found = self._bindings(name, at, context)
        if found is None:
            return COMPUTED if name in GIVEN else Verdict(False, (name, UNBOUND))
        if isinstance(found, _Argument):
            return self.verdict(found.expression, found.context, seen)
        key = (context.module.name, id(found.scope), name)
        if key in seen:
            return COMPUTED
        return _merge(self._bound(name, one, context, seen | {key}) for one in found.bindings)

    def _bound(
        self, name: str, binding: Binding, context: _Context, seen: frozenset[object]
    ) -> Verdict:
        found = _merge(self.verdict(value, context, seen) for value in binding.values)
        if found.typed_in:
            return found
        if binding.untraceable is not None:
            return Verdict(False, found.untraceable or (name, binding.untraceable))
        if binding.imported is not None:
            return self._imported(*binding.imported, [], seen)
        return found

    def _resolve(self, module: str, path: list[str]) -> tuple[_Module, list[str]] | None:
        """The deepest module of ours that *module* and then *path* name, with what is left of
        *path*; ``None`` for an outside library."""
        if self.project.module(module) is None:
            return None
        current, index = module, 0
        while index < len(path) and self.project.module(f"{current}.{path[index]}") is not None:
            current, index = f"{current}.{path[index]}", index + 1
        resolved = self.project.module(current)
        return (resolved, path[index:]) if resolved is not None else None

    def _imported(
        self, module: str, attribute: str | None, rest: list[str], seen: frozenset[object]
    ) -> Verdict:
        """A name imported from *module*, read further through *rest*: followed into our code, a
        value of an outside library passes."""
        target = self._resolve(module, [*([attribute] if attribute is not None else []), *rest])
        if target is None:
            return COMPUTED
        found, remaining = target
        if not remaining:
            return COMPUTED  # a module is a namespace, not a number
        head = remaining[0]
        if found.lookup(head, found.tree) is None:
            return Verdict(False, (head, f"not in our module {found.name}"))
        named = self.name(head, found.tree, _Context(found), seen)
        if len(remaining) == 1:
            return named
        return _merge(iter([named, self._attribute(remaining[-1], _Context(found), seen)]))

    def _chain(
        self, root: ast.Name, attributes: list[str], context: _Context, seen: frozenset[object]
    ) -> Verdict:
        """A name read through attributes (``consts.N``, ``fund.price``): through a module of ours
        the attribute is followed; through anything else, the name itself is judged, and the
        attribute read is followed by its name."""
        found = self._bindings(root.id, root, context)
        if isinstance(found, _Found):
            imported = [b.imported for b in found.bindings if b.imported is not None]
            if imported:
                return _merge(self._imported(*one, attributes, seen) for one in imported)
        named = self.name(root.id, root, context, seen)
        if not attributes:  # a called chain: the call follows the method
            return named
        return _merge(iter([named, self._attribute(attributes[-1], context, seen)]))

    def _attribute(self, name: str, context: _Context, seen: frozenset[object]) -> Verdict:
        """Every value our code gives an attribute called *name*. Only a typed-in number counts:
        a value that cannot be traced (``self.n = n`` in a constructor) is answered for by the
        object it is read from, which is judged where it was made."""
        key = ("attribute", name)
        if key in seen:
            return COMPUTED
        values = [(context.module, value) for value in context.module.attributes.get(name, [])]
        values += [one for one in self.project.attributes(name) if one[0] is not context.module]
        found = _merge(
            self.verdict(value, _Context(module), seen | {key}) for module, value in values
        )
        return found if found.typed_in else COMPUTED

    def _called(self, call: ast.Call, context: _Context, seen: frozenset[object]) -> Verdict:
        """A call: into our code it is followed to what it returns; an outside library's result
        passes; a name bound nowhere is refused. Its arguments are read by the walk around it."""
        func = call.func
        if isinstance(func, ast.Lambda):
            return self._returns(func, context.module, call, context, seen)
        if (
            isinstance(func, ast.Name)
            and func.id not in GIVEN
            and self._bindings(func.id, func, context) is None
        ):
            return Verdict(False, (func.id, UNBOUND))
        return _merge(
            self._returns(function, module, call, context, seen)
            for module, function in self._callees(func, context, seen)
        )

    def _callees(
        self, func: ast.expr, context: _Context, seen: frozenset[object]
    ) -> list[tuple[_Module, Function]]:
        """Every function of ours that *func* may call."""
        if isinstance(func, ast.Name):
            return self._functions_named(func.id, func, context, seen)
        if not isinstance(func, ast.Attribute):
            return []
        root, attributes = _root_and_attributes(func)
        if isinstance(root, ast.Name):
            found = self._bindings(root.id, root, context)
            if isinstance(found, _Found):
                imported = [b.imported for b in found.bindings if b.imported is not None]
                if imported:
                    return [
                        callee
                        for module, attribute in imported
                        for callee in self._module_functions(module, attribute, attributes, seen)
                    ]
        own = [(context.module, method) for method in context.module.methods.get(func.attr, [])]
        return [*own, *(m for m in self.project.methods(func.attr) if m[0] is not context.module)]

    def _module_functions(
        self, module: str, attribute: str | None, rest: list[str], seen: frozenset[object]
    ) -> list[tuple[_Module, Function]]:
        target = self._resolve(module, [*([attribute] if attribute is not None else []), *rest])
        if target is None or len(target[1]) != 1:
            return []
        found, (name,) = target
        return self._functions_named(name, found.tree, _Context(found), seen)

    def _functions_named(
        self, name: str, at: ast.AST, context: _Context, seen: frozenset[object]
    ) -> list[tuple[_Module, Function]]:
        """The functions of ours a call of *name* reaches: one defined here, one imported from our
        code, a lambda or function stored in the name, or the function an argument is."""
        found = self._bindings(name, at, context)
        if found is None:
            return []
        if isinstance(found, _Argument):
            return self._callees(found.expression, found.context, seen)
        key = ("callee", context.module.name, id(found.scope), name)
        if key in seen:
            return []
        callees: list[tuple[_Module, Function]] = []
        for binding in found.bindings:
            if binding.function is not None:
                callees.append((context.module, binding.function))
            if binding.imported is not None:
                module, attribute = binding.imported
                callees += self._module_functions(module, attribute, [], seen | {key})
            for value in binding.values:
                if isinstance(value, ast.Lambda):
                    callees.append((context.module, value))
                elif isinstance(value, (ast.Name, ast.Attribute)):
                    callees += self._callees(value, context, seen | {key})
        return callees

    def _returns(
        self,
        function: Function,
        module: _Module,
        call: ast.Call,
        caller: _Context,
        seen: frozenset[object],
    ) -> Verdict:
        """What *function* returns when *call* calls it, each parameter standing for its
        argument."""
        key = ("function", id(function))
        if key in seen:
            return COMPUTED
        callee = _Context(module, {**caller.frame, **_frame(function, call, caller)})
        if isinstance(function, ast.Lambda):
            return self.verdict(function.body, callee, seen | {key})
        returned = [
            node.value
            for node in ast.walk(function)
            if isinstance(node, ast.Return) and node.value is not None
        ]
        return _merge(self.verdict(value, callee, seen | {key}) for value in returned)


def _frame(
    function: Function, call: ast.Call, caller: _Context
) -> dict[tuple[int, str], tuple[_Context, ast.expr]]:
    """Each parameter of *function* with the argument *call* gives it; a parameter given none keeps
    its default. A method's ``self`` takes no argument."""
    positional = [*function.args.posonlyargs, *function.args.args]
    if isinstance(call.func, ast.Attribute) and positional and positional[0].arg in ("self", "cls"):
        positional = positional[1:]
    frame: dict[tuple[int, str], tuple[_Context, ast.expr]] = {}
    for parameter, argument in zip(positional, call.args, strict=False):
        if not isinstance(argument, ast.Starred):
            frame[(id(function), parameter.arg)] = (caller, argument)
    names = {parameter.arg for parameter in [*positional, *function.args.kwonlyargs]}
    for keyword in call.keywords:
        if keyword.arg is not None and keyword.arg in names:
            frame[(id(function), keyword.arg)] = (caller, keyword.value)
    return frame


def _root_and_attributes(node: ast.Attribute) -> tuple[ast.expr, list[str]]:
    attributes: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        attributes.insert(0, current.attr)
        current = current.value
    return current, attributes


def _chains(expression: ast.AST) -> dict[int, list[str]]:
    """For each name read through attributes in *expression* (``consts.N``), the attributes, by the
    name's node; a called chain (``obj.method()``) is left to the call."""
    called = {id(node.func) for node in ast.walk(expression) if isinstance(node, ast.Call)}
    inner = {
        id(node.value)
        for node in ast.walk(expression)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
    }
    found: dict[int, list[str]] = {}
    for node in ast.walk(expression):
        if isinstance(node, ast.Attribute) and id(node) not in inner:
            root, attributes = _root_and_attributes(node)
            if isinstance(root, ast.Name):
                found[id(root)] = [] if id(node) in called else attributes
    return found


def _calls(node: ast.expr, name: str) -> bool:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == name


def _compare_bounds(node: ast.Compare, *, negated: bool) -> Iterator[tuple[ast.AST, ast.expr]]:
    """Each side of *node* that bounds another from below: ``a >= b`` and ``b <= a`` bound ``a`` by
    ``b``; ``x in range(5, 10)`` bounds ``x`` by 5; ``max(x, 5) == x`` bounds ``x`` by every
    argument of ``max``; ``min(x, 5) == 5`` bounds ``x`` by the other side."""
    left = node.left
    for operator, right in zip(node.ops, node.comparators, strict=True):
        if isinstance(operator, LOWER):
            yield node, left if negated else right
        elif isinstance(operator, UPPER):
            yield node, right if negated else left
        elif isinstance(operator, (ast.In, ast.NotIn)) and isinstance(operator, ast.In) != negated:
            if isinstance(right, ast.Call) and _calls(right, "range") and len(right.args) > 1:
                yield node, right.args[0]
        elif isinstance(operator, (ast.Eq, ast.NotEq)) and isinstance(operator, ast.Eq) != negated:
            for side, other in ((left, right), (right, left)):
                if isinstance(side, ast.Call) and _calls(side, "max"):
                    yield from ((node, argument) for argument in side.args)
                elif _calls(side, "min"):
                    yield node, other
        left = right


def _bounds(node: ast.AST, *, negated: bool = False) -> Iterator[tuple[ast.AST, ast.expr]]:
    """Every comparison under *node* with each side that bounds the other from below. Under an odd
    number of ``not`` a ceiling is a floor: ``not n < 5`` says ``n >= 5``."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        yield from _bounds(node.operand, negated=not negated)
        return
    if isinstance(node, ast.Compare):
        yield from _compare_bounds(node, negated=negated)
    for child in ast.iter_child_nodes(node):
        yield from _bounds(child, negated=negated)


def _fails(body: list[ast.stmt]) -> bool:
    """Whether *body* fails the test: ``pytest.fail(...)`` or ``raise AssertionError``."""
    for statement in body:
        if (
            isinstance(statement, ast.Expr)
            and isinstance(statement.value, ast.Call)
            and ast.unparse(statement.value.func) in ("pytest.fail", "fail")
        ):
            return True
        if isinstance(statement, ast.Raise) and statement.exc is not None:
            raised = statement.exc.func if isinstance(statement.exc, ast.Call) else statement.exc
            if ast.unparse(raised) == "AssertionError":
                return True
    return False


def _checks(tree: ast.AST) -> Iterator[Iterator[tuple[ast.AST, ast.expr]]]:
    """The lower bounds of every check in *tree*: an assert, an ``if`` that fails the test (its
    condition is what must NOT hold), and unittest's bound assertions."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assert):
            yield _bounds(node.test)
        elif isinstance(node, ast.If) and _fails(node.body):
            yield _bounds(node.test, negated=True)
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in UNITTEST_BOUNDS
            and len(node.args) > 1
        ):
            yield iter([(node, node.args[UNITTEST_BOUNDS[node.func.attr]])])


def _rank(verdict: Verdict) -> int:
    """A floor outranks an untraceable name, which outranks a computed bound."""
    return 2 if verdict.typed_in else 1 if verdict.untraceable is not None else 0


def _judged(
    bounds: Iterator[tuple[ast.AST, ast.expr]], judge: _Judge, context: _Context
) -> Iterator[tuple[int, str]]:
    """Each comparison that a typed-in number bounds from below, or that a name the reader cannot
    trace bounds from below; one finding per comparison, a floor first."""
    verdicts: dict[int, tuple[ast.AST, Verdict]] = {}
    for comparison, bound in bounds:
        verdict = judge.verdict(bound, context, frozenset())
        before = verdicts.get(id(comparison))
        if before is None or _rank(verdict) > _rank(before[1]):
            verdicts[id(comparison)] = (comparison, verdict)
    for comparison, verdict in verdicts.values():
        text = ast.unparse(comparison)
        line = getattr(comparison, "lineno", 0)
        if verdict.typed_in:
            yield line, f"floor {text}"
        elif verdict.untraceable is not None:
            name, why = verdict.untraceable
            yield line, f"cannot trace {name} ({why}) in {text}"


def _floor_constants(tree: ast.AST, judge: _Judge, context: _Context) -> Iterator[tuple[int, str]]:
    """Every constant named like a floor that the file sets to a typed-in number."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if (
            isinstance(target, ast.Name)
            and FLOOR_NAME.search(target.id)
            and not isinstance(value, CONTAINERS)
            and judge.verdict(value, context, frozenset()).typed_in
        ):
            yield node.lineno, f"floor constant {target.id} = {ast.unparse(value)}"


def read(source: str, path: str, project: Project) -> Reading:
    """Every literal floor in *source* (the file at *path*), by line, and how many asserts and
    checks it read. Names are followed into *project*, our own code."""
    try:
        tree = ast.parse(source, path)
    except (SyntaxError, ValueError) as error:
        msg = f"{path}: cannot parse it ({error})"
        raise UnreadableSourceError(msg) from error
    judge = _Judge(project)
    context = _Context(_Module(path, tree))
    found = [*_floor_constants(tree, judge, context)]
    checks = 0
    for bounds in _checks(tree):
        checks += 1
        found.extend(_judged(bounds, judge, context))
    return Reading(
        asserts=sum(1 for node in ast.walk(tree) if isinstance(node, ast.Assert)),
        checks=checks,
        findings=[f"line {line}: {text}" for line, text in sorted(found, key=lambda f: f[0])],
    )


def assert_tokens(source: str, path: str) -> int:
    """How many ``assert`` keywords *source* holds, read from its tokens with comments and text
    gone: a count of the asserts that owes nothing to the parse tree."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, SyntaxError) as error:
        msg = f"{path}: cannot read its words ({error})"
        raise UnreadableSourceError(msg) from error
    return sum(1 for token in tokens if token.type == tokenize.NAME and token.string == "assert")
