"""The declared types of our code's objects, from one mypy run (#272): the literal-floor reader
matches an attribute or method by the type of the object it is read from, never by its name alone
(Shyden, 2026-10-20). mypy already checks every file of ours in CI, so its types are the ones the
code declares.

mypy is compiled, so no visitor of ours can walk its trees; its own ``NameAndMemberCollector``
gathers every attribute read, and each is matched to the parse tree by its exact place in the
file. A place mypy gave no type (an annotation, ``super()``, code it does not check) is a type the
check cannot work out.
"""

import ast
from collections.abc import Iterable
from pathlib import Path

from literal_floors import LIBRARY, UNKNOWN, Owners, UnreadableSourceError
from mypy import build
from mypy.main import process_options
from mypy.nodes import MypyFile, SymbolTableNode, TypeInfo
from mypy.traverser import NameAndMemberCollector
from mypy.types import (
    CallableType,
    Instance,
    LiteralType,
    NoneType,
    Overloaded,
    ProperType,
    TupleType,
    Type,
    TypeType,
    TypeVarType,
    UnionType,
    get_proper_type,
)

# The folders mypy checks, as [tool.mypy] files names them.
CHECKED = ("packages", "tests", "scripts")

type Place = tuple[str, int, int, int, int, str]


class MypyTypes:
    """``literal_floors.Types``, answered from one mypy run over the tree at *root*, each file
    named by its path from *root*."""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        folders = [str(self._root / folder) for folder in CHECKED]
        files, options = process_options(
            [*folders, "--config-file", str(self._root / "pyproject.toml")]
        )
        options.export_types = True
        options.incremental = False
        options.preserve_asts = True
        result = build.build(files, options)
        if result.errors:
            msg = f"mypy found {len(result.errors)} errors, first: {result.errors[0]}"
            raise UnreadableSourceError(msg)
        self._types = result.types
        self._files = {
            name: key for name, tree in result.files.items() if (key := self._key(tree)) is not None
        }
        self._owners: dict[Place, Owners] = {}
        infos: dict[str, TypeInfo] = {}
        for name, key in self._files.items():
            tree = result.files[name]
            collector = NameAndMemberCollector()
            tree.accept(collector)
            for read in collector.member_exprs:
                if read.end_line is None or read.end_column is None:
                    continue  # one mypy made itself (an f-string's format call), not in the file
                place = (key, read.line, read.column, read.end_line, read.end_column, read.name)
                self._owners[place] = self._of(self._types.get(read.expr), infos)
            _named_classes(tree.names.values(), infos)
        self._classes: dict[tuple[str, int, str], str] = {}
        self._related: dict[str, frozenset[str] | None] = {}
        for info in infos.values():
            key = self._files.get(info.module_name)
            if key is not None:
                self._classes[(key, info.defn.line, info.defn.name)] = info.fullname
                self._relate(info)

    def _key(self, tree: MypyFile) -> str | None:
        """The file *tree* was read from, by its path from the root; ``None`` when not ours."""
        path = Path(tree.path).resolve()
        if not path.is_relative_to(self._root):
            return None
        relative = path.relative_to(self._root)
        return relative.as_posix() if relative.parts[0] in CHECKED else None

    def _relate(self, info: TypeInfo) -> None:
        """*info* and each ancestor of ours are related both ways; a protocol to any class."""
        if info.is_protocol:
            self._related[info.fullname] = None
            return
        for ancestor in info.mro:
            if ancestor.module_name not in self._files:
                continue
            for one, other in ((info, ancestor), (ancestor, info)):
                known = self._related.get(one.fullname, frozenset({one.fullname}))
                if known is not None:
                    self._related[one.fullname] = known | {other.fullname}

    def _of(self, given: Type | None, infos: dict[str, TypeInfo]) -> Owners:
        """Whose an object of type *given* is: a function's, ``None``'s or an outside library's
        class's passes; one of a union is each member's; anything else is not worked out."""
        found = None if given is None else _unwrapped(given)
        if isinstance(found, (CallableType, Overloaded)) and found.is_type_obj():
            found = found.type_object()
        if isinstance(found, TypeInfo):
            return self._class(found, infos)
        if isinstance(found, UnionType):
            parts = [self._of(item, infos) for item in found.items]
            ours = frozenset[str]().union(*(part for part in parts if isinstance(part, frozenset)))
            return UNKNOWN if UNKNOWN in parts else ours or LIBRARY
        return LIBRARY if isinstance(found, (CallableType, Overloaded, NoneType)) else UNKNOWN

    def _class(self, info: TypeInfo, infos: dict[str, TypeInfo]) -> Owners:
        """An object of class *info*: ours by its full name, or an outside library's."""
        for one in info.mro:
            infos.setdefault(one.fullname, one)
        return frozenset({info.fullname}) if info.module_name in self._files else LIBRARY

    def owners(self, module: str, node: ast.Attribute) -> Owners:
        if node.end_lineno is None or node.end_col_offset is None:
            return UNKNOWN
        place = (module, node.lineno, node.col_offset, node.end_lineno, node.end_col_offset)
        return self._owners.get((*place, node.attr), UNKNOWN)

    def class_name(self, module: str, node: ast.ClassDef) -> str:
        return self._classes.get((module, node.lineno, node.name), UNKNOWN)

    def related(self, name: str) -> frozenset[str] | None:
        return self._related.get(name, frozenset({name}))


def _unwrapped(given: Type) -> ProperType | TypeInfo:
    """The type an object of type *given* is read as: a class object as its class, a tuple, a
    literal or a type variable as the type it stands on, an instance as its class."""
    found = get_proper_type(given)
    while isinstance(found, (TypeType, TupleType, LiteralType, TypeVarType)):
        if isinstance(found, TypeType):
            found = get_proper_type(found.item)
        elif isinstance(found, TupleType):
            found = found.partial_fallback
        elif isinstance(found, LiteralType):
            found = found.fallback
        else:
            found = get_proper_type(found.upper_bound)
    return found.type if isinstance(found, Instance) else found


def _named_classes(symbols: Iterable[SymbolTableNode], infos: dict[str, TypeInfo]) -> None:
    """Every class *symbols* name, and the classes inside each, into *infos*."""
    for symbol in symbols:
        if isinstance(symbol.node, TypeInfo) and symbol.node.fullname not in infos:
            infos[symbol.node.fullname] = symbol.node
            _named_classes(symbol.node.names.values(), infos)
