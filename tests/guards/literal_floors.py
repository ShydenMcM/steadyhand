"""A floor typed into a Python test (#272): a lower bound written as a number, which is tight only
on the day it is measured. Floors live in ``extension/tests/floors.json``, read through
``floors.floor_breach``; this reader finds every lower bound in an ``assert`` that a test typed in.

Shyden's decision (2026-10-20, on #272): a literal floor is EVERY typed-in lower bound in an assert,
as in TypeScript, with no exemption, and a bound that uses a name the reader cannot trace to a value
in its file is refused, not read as safe. A bound of 0 is a non-emptiness check, not a floor; a
ceiling is a budget, not a floor; both pass, as in ``extension/tests/lib/literal-floors.ts``.

A bound is judged by every node in it, not its top node only (#362): a number anywhere in it, in
arithmetic, a call's argument or a cast, makes it a floor. A name in it is followed to every value
the file binds it to (an assignment, a parametrize value, a default, a loop over written values),
and a call to a function the file defines is followed to what it returns. A call to anything else is
computation by other code. A name bound where the reader cannot see a value (a fixture or helper
parameter, an import, a loop over values the test made) is refused by name.
"""

import ast
import builtins
import io
import re
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass

FLOOR_NAME = re.compile(r"floor", re.IGNORECASE)
LOWER = (ast.Gt, ast.GtE)
UPPER = (ast.Lt, ast.LtE)
CONTAINERS = (ast.List, ast.Tuple, ast.Set, ast.Dict, ast.JoinedStr)
BUILTINS = frozenset(dir(builtins))

# Why a name cannot be traced, by how the file binds it.
LOOP = "a loop over values the test made"
IMPORT = "an import"
PARAMETER = "a fixture or helper parameter"
UNBOUND = "never bound in this file"

type Function = ast.FunctionDef | ast.AsyncFunctionDef


class UnreadableSourceError(AssertionError):
    """A file the reader cannot parse: it is refused by name, never read as having no floors."""


@dataclass(frozen=True)
class Reading:
    """What one file holds: how many asserts were judged, and every literal floor among them."""

    asserts: int
    findings: list[str]


@dataclass(frozen=True)
class Binding:
    """One way the file binds a name: to the values it may take, to a function, or to the reason
    the reader cannot say what it holds. A binding with none of these (a class, a caught error)
    holds no number."""

    values: tuple[ast.expr, ...] = ()
    untraceable: str | None = None
    function: Function | None = None


@dataclass(frozen=True)
class Verdict:
    typed_in: bool
    untraceable: tuple[str, str] | None


COMPUTED = Verdict(typed_in=False, untraceable=None)
TYPED_IN = Verdict(typed_in=True, untraceable=None)


def _is_number(node: ast.AST) -> bool:
    """A number written in the source, other than 0 (a bound of 0 is a non-emptiness check)."""
    return (
        isinstance(node, ast.Constant)
        and type(node.value) in (int, float, complex)
        and node.value != 0
    )


def _names(target: ast.AST) -> Iterator[str]:
    yield from (node.id for node in ast.walk(target) if isinstance(node, ast.Name))


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
    for decorator in function.decorator_list:
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


class _Bindings:
    """Every binding of every name in one file, keyed by name: a name bound twice keeps both, and
    scopes are not told apart, so a name is judged by every value it takes anywhere in the file."""

    def __init__(self, tree: ast.AST) -> None:
        self.by_name: dict[str, list[Binding]] = {}
        for node in ast.walk(tree):
            self._collect(node)

    def add(self, name: str, binding: Binding) -> None:
        self.by_name.setdefault(name, []).append(binding)

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
            self.add(name, Binding(values=(value,)))

    def _collect(self, node: ast.AST) -> None:
        """The bindings *node* makes by giving a name a value: an assignment, a loop, a ``with``."""
        if isinstance(node, ast.Assign):
            for target in node.targets:
                self._assigned(target, node.value)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign, ast.NamedExpr)):
            if node.value is not None:
                self._assigned(node.target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            self._looped(node.target, node.iter)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    self._assigned(item.optional_vars, item.context_expr)
        else:
            self._declared(node)

    def _declared(self, node: ast.AST) -> None:
        """The bindings *node* makes by declaring a name: a function and its parameters, a lambda's
        parameters, an import, a class, a caught error."""
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self.add(node.name, Binding(function=node))
            self._parameters(node)
        elif isinstance(node, ast.Lambda):
            for argument in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]:
                self.add(argument.arg, Binding(untraceable=PARAMETER))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                self.add((alias.asname or alias.name).split(".")[0], Binding(untraceable=IMPORT))
        elif isinstance(node, (ast.ClassDef, ast.ExceptHandler)) and node.name is not None:
            self.add(node.name, Binding())

    def _looped(self, target: ast.expr, over: ast.expr) -> None:
        """A loop over values written in the file binds its names to them; any other loop binds
        them to values the test made, which the reader cannot see."""
        for name in _names(target):
            if isinstance(over, (ast.Tuple, ast.List, ast.Set)):
                self.add(name, Binding(values=tuple(over.elts)))
            else:
                self.add(name, Binding(untraceable=LOOP))

    def _parameters(self, function: Function) -> None:
        arguments = function.args
        parametrized = _parametrized(function)
        positional = [*arguments.posonlyargs, *arguments.args]
        defaults = dict(
            zip(
                [
                    argument.arg
                    for argument in positional[len(positional) - len(arguments.defaults) :]
                ],
                arguments.defaults,
                strict=True,
            )
        )
        for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
            if default is not None:
                defaults[argument.arg] = default
        extras = [extra for extra in (arguments.vararg, arguments.kwarg) if extra is not None]
        for argument in [*positional, *arguments.kwonlyargs, *extras]:
            if argument.arg in parametrized:
                self.add(argument.arg, Binding(values=tuple(parametrized[argument.arg])))
            elif argument.arg in defaults:
                self.add(argument.arg, Binding(values=(defaults[argument.arg],)))
            else:
                self.add(argument.arg, Binding(untraceable=PARAMETER))


def _called_roots(expression: ast.AST) -> tuple[set[int], set[int]]:
    """The names *expression* calls directly (``f(x)``), and the names that only root a called
    attribute chain (``date.today()``, ``Money.zero(x)``), by node identity."""
    direct: set[int] = set()
    rooted: set[int] = set()
    for node in ast.walk(expression):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            direct.add(id(node.func))
            continue
        root: ast.expr = node.func
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root is not node.func:
            rooted.add(id(root))
    return direct, rooted


class _Judge:
    """Whether an expression's value can be a number typed into the file."""

    def __init__(self, bindings: _Bindings) -> None:
        self.bindings = bindings

    def verdict(self, expression: ast.AST, seen: frozenset[str] = frozenset()) -> Verdict:
        direct, rooted = _called_roots(expression)
        untraceable: tuple[str, str] | None = None
        for node in ast.walk(expression):
            if _is_number(node):
                return TYPED_IN
            if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
                continue
            if id(node) in direct:
                found = self._called(node.id, seen)
            else:
                found = self._used(node.id, seen, rooted=id(node) in rooted)
            if found.typed_in:
                return found
            untraceable = untraceable or found.untraceable
        return Verdict(typed_in=False, untraceable=untraceable)

    def _called(self, name: str, seen: frozenset[str]) -> Verdict:
        """A function this file defines is followed to what it returns; anything else called is
        computation by other code."""
        if name in seen:
            return COMPUTED
        returned = [
            node.value
            for binding in self.bindings.by_name.get(name, [])
            if binding.function is not None
            for node in ast.walk(binding.function)
            if isinstance(node, ast.Return) and node.value is not None
        ]
        return self._any(returned, seen | {name})

    def _used(self, name: str, seen: frozenset[str], *, rooted: bool) -> Verdict:
        """A name used as a value. One that only roots a called attribute chain and is bound only
        as an import, a class or a function is a namespace, not a value."""
        if name in seen:
            return COMPUTED
        bindings = self.bindings.by_name.get(name)
        if bindings is None:
            return COMPUTED if name in BUILTINS else Verdict(False, (name, UNBOUND))
        if rooted and all(
            b.untraceable == IMPORT or (b.untraceable is None and not b.values) for b in bindings
        ):
            return COMPUTED
        untraceable: tuple[str, str] | None = None
        for binding in bindings:
            if binding.untraceable is not None:
                untraceable = untraceable or (name, binding.untraceable)
                continue
            found = self._any(list(binding.values), seen | {name})
            if found.typed_in:
                return found
            untraceable = untraceable or found.untraceable
        return Verdict(typed_in=False, untraceable=untraceable)

    def _any(self, expressions: list[ast.expr], seen: frozenset[str]) -> Verdict:
        untraceable: tuple[str, str] | None = None
        for expression in expressions:
            found = self.verdict(expression, seen)
            if found.typed_in:
                return found
            untraceable = untraceable or found.untraceable
        return Verdict(typed_in=False, untraceable=untraceable)


def _bounds(node: ast.AST, *, negated: bool = False) -> Iterator[tuple[ast.Compare, ast.expr]]:
    """Every comparison under *node* with each side that bounds the other from below. Under an odd
    number of ``not`` a ceiling is a floor: ``not n < 5`` says ``n >= 5``."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        yield from _bounds(node.operand, negated=not negated)
        return
    if isinstance(node, ast.Compare):
        left = node.left
        for operator, right in zip(node.ops, node.comparators, strict=True):
            if isinstance(operator, LOWER):
                yield node, left if negated else right
            elif isinstance(operator, UPPER):
                yield node, right if negated else left
            left = right
    for child in ast.iter_child_nodes(node):
        yield from _bounds(child, negated=negated)


def _floor_constants(tree: ast.AST, judge: _Judge) -> Iterator[tuple[int, str]]:
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
            and judge.verdict(value).typed_in
        ):
            yield node.lineno, f"floor constant {target.id} = {ast.unparse(value)}"


def _rank(verdict: Verdict) -> int:
    """A floor outranks an untraceable name, which outranks a computed bound."""
    return 2 if verdict.typed_in else 1 if verdict.untraceable is not None else 0


def _judged(statement: ast.Assert, judge: _Judge) -> Iterator[tuple[int, str]]:
    """Each comparison in *statement* that a typed-in number bounds from below, or that a name the
    reader cannot trace bounds from below; one finding per comparison, a floor first."""
    verdicts: dict[int, tuple[ast.Compare, Verdict]] = {}
    for comparison, bound in _bounds(statement.test):
        verdict = judge.verdict(bound)
        before = verdicts.get(id(comparison))
        if before is None or _rank(verdict) > _rank(before[1]):
            verdicts[id(comparison)] = (comparison, verdict)
    for comparison, verdict in verdicts.values():
        text = ast.unparse(comparison)
        if verdict.typed_in:
            yield comparison.lineno, f"floor {text}"
        elif verdict.untraceable is not None:
            name, why = verdict.untraceable
            yield comparison.lineno, f"cannot trace {name} ({why}) in {text}"


def read(source: str, path: str) -> Reading:
    """Every literal floor in *source* (the file at *path*), by line, and how many asserts it
    read."""
    try:
        tree = ast.parse(source, path)
    except (SyntaxError, ValueError) as error:
        msg = f"{path}: cannot parse it ({error})"
        raise UnreadableSourceError(msg) from error
    judge = _Judge(_Bindings(tree))
    asserts = [node for node in ast.walk(tree) if isinstance(node, ast.Assert)]
    found = [*_floor_constants(tree, judge)]
    for statement in asserts:
        found.extend(_judged(statement, judge))
    return Reading(
        asserts=len(asserts),
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
