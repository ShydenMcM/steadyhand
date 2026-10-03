"""The legal line is structural (T1 spec §5): the level changes how much is explained, never what
the tool suggests trading.

1. Only the output layer may import training. No module of either package outside the two
   training packages and the CLI's output layer, ``steadyhand_idx.output``, imports either of them
   (M5 spec §5.7). This covers any new module, a strategy or a broker say, without anyone listing
   it. The output layer is also where ``[training]`` is parsed (T1 spec §5 item 3), so the
   configuration and the command modules stay outside the exception.
2. Training imports nothing that decides: only the standard library and a short allowlist.
4. The advice-phrase backstop over every lesson's title, summary and body.

Imports are read from the AST, relative ones resolved, so a comment or a docstring that names a
module is never a finding.
"""

import ast
import re
import shutil
import sys
from pathlib import Path

import pytest
from key_walk import ENGINE, IDX
from lesson_rules import ADVICE_PHRASES, advice_findings, advice_phrases
from population import searched, tracked
from source_tree import UnreadableSourceError, parse

from steadyhand.training import Catalogue

TRAINING = ("steadyhand.training", "steadyhand_idx.training")
OUTPUT_LAYER = "steadyhand_idx.output"
MAY_IMPORT_TRAINING = (*TRAINING, OUTPUT_LAYER)
ENGINE_TRAINING_MAY_IMPORT = ("steadyhand.notes", "steadyhand.terms", "steadyhand._validate")
IDX_TRAINING_MAY_IMPORT = (
    *ENGINE_TRAINING_MAY_IMPORT,
    "steadyhand.training",
    "steadyhand_idx.notes",
)
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/training"
RAW_IMPORT = re.compile(r"^[ \t]*(?:import[ \t]+[\w.]+|from[ \t]+[\w.]+[ \t]+import\b)", re.M)

# Measured on 2026-10-03 (#178): 57 modules in both packages, 489 import statements outside the
# modules that may import training, and 21 inside the training packages. Lower each only by a
# deliberate edit when the packages shrink.
MODULES_FLOOR = 56
IMPORTS_FLOOR = 488
TRAINING_IMPORTS_FLOOR = 20

type Statement = tuple[str, tuple[str, ...]]
"""One import statement: the module it names, and for ``from`` imports the names it takes."""


def module_name(path: Path) -> str:
    """The dotted name of a source file of either package."""
    for package in (ENGINE, IDX):
        if package in path.parents:
            parts = path.relative_to(package.parent).with_suffix("").parts
            return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)
    msg = f"{path} is not in either package"
    raise ValueError(msg)


def statements(source: str, module: str, *, is_package: bool) -> list[Statement]:
    """Every import statement in *source*, each module resolved to its absolute name. Errors
    name the file *module* lives in."""
    package = module if is_package else module.rpartition(".")[0]
    path = module.replace(".", "/") + ("/__init__" if is_package else "")
    found: list[Statement] = []
    for node in ast.walk(parse(source, f"{path}.py")):
        if isinstance(node, ast.Import):
            found += [(alias.name, ()) for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parent = package.rsplit(".", node.level - 1)[0] if node.level > 1 else package
                base = f"{parent}.{base}" if base else parent
            found.append((base, tuple(alias.name for alias in node.names)))
    return found


def _within(name: str, modules: tuple[str, ...]) -> bool:
    return any(name == module or name.startswith(f"{module}.") for module in modules)


def imports_training(statement: Statement) -> bool:
    base, names = statement
    return _within(base, TRAINING) or any(_within(f"{base}.{name}", TRAINING) for name in names)


def allowed(statement: Statement, allowlist: tuple[str, ...], own: str) -> bool:
    def ok(name: str) -> bool:
        return name.split(".", maxsplit=1)[0] in sys.stdlib_module_names or _within(
            name, (*allowlist, own)
        )

    base, names = statement
    return ok(base) or (bool(names) and all(ok(f"{base}.{name}") for name in names))


def sources() -> list[tuple[str, bool, str]]:
    """Every module of both packages: (dotted name, is a package, source)."""
    paths = sorted([*ENGINE.rglob("*.py"), *IDX.rglob("*.py")])
    return [(module_name(p), p.name == "__init__.py", p.read_text(encoding="utf-8")) for p in paths]


@pytest.mark.parametrize(
    ("module", "is_package", "file"),
    [
        ("broken", False, r"broken\.py"),
        ("steadyhand.broken", True, r"steadyhand/broken/__init__\.py"),
    ],
    ids=["module", "package"],
)
def test_statements_names_the_file_it_cannot_parse(
    module: str, file: str, *, is_package: bool
) -> None:
    with pytest.raises(UnreadableSourceError, match=rf"^{file}: "):
        statements("def (:\n", module, is_package=is_package)


def test_the_module_names_are_resolved_from_paths() -> None:
    assert module_name(ENGINE / "__init__.py") == "steadyhand"
    assert module_name(ENGINE / "broker/simulated.py") == "steadyhand.broker.simulated"
    assert module_name(IDX / "training/__init__.py") == "steadyhand_idx.training"
    with pytest.raises(ValueError, match="is not in either package"):
        module_name(Path("/elsewhere/x.py"))


def test_the_training_import_detector() -> None:
    source = (
        "import steadyhand.training\n"
        "from steadyhand import training\n"
        "from steadyhand.training.render import explain\n"
        "from steadyhand_idx.training import COURSE\n"
        "import steadyhand.trainingx\n"
        "from steadyhand import Money\n"
        '"""import steadyhand.training"""\n'
        "def lazy():\n"
        "    import steadyhand_idx.training\n"
    )
    found = statements(source, "steadyhand.engine", is_package=False)
    assert [imports_training(statement) for statement in found] == [
        True,
        True,
        True,
        True,
        False,
        False,
        True,
    ]


def test_relative_imports_are_resolved() -> None:
    assert statements("from .training import explain\n", "steadyhand", is_package=True) == [
        ("steadyhand.training", ("explain",))
    ]
    assert statements("from . import training\n", "steadyhand", is_package=True) == [
        ("steadyhand", ("training",))
    ]
    assert statements(
        "from ..training import x\n", "steadyhand.broker.simulated", is_package=False
    ) == [("steadyhand.training", ("x",))]
    assert statements(
        "from . import catalogue\n", "steadyhand.training.render", is_package=False
    ) == [("steadyhand.training", ("catalogue",))]
    both = statements(
        "from . import training\nfrom .training import e\n", "steadyhand", is_package=True
    )
    assert len(both) == 2
    assert all(imports_training(s) for s in both)  # runtime population: the statements parsed


@pytest.mark.parametrize(
    ("line", "ok"),
    [
        ("import re", True),
        ("from __future__ import annotations", True),
        ("from collections.abc import Iterable", True),
        ("from steadyhand.notes import Note", True),
        ("from steadyhand import notes", True),
        ("from steadyhand._validate import require_type", True),
        ("from steadyhand.training.catalogue import Catalogue", True),
        ("from . import catalogue", True),
        ("from steadyhand.risk import RiskLimits", False),
        ("from steadyhand import Money", False),
        ("from steadyhand import notes, risk", False),
        ("import steadyhand", False),
        ("import yaml", False),
        ("from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP", False),
    ],
)
def test_the_engine_training_allowlist(line: str, *, ok: bool) -> None:
    (statement,) = statements(line, "steadyhand.training.render", is_package=False)
    assert allowed(statement, ENGINE_TRAINING_MAY_IMPORT, "steadyhand.training") is ok


@pytest.mark.parametrize(
    ("line", "ok"),
    [
        ("from steadyhand.training import Catalogue", True),
        ("from steadyhand_idx.notes import UNIVERSE_SURVIVORSHIP_GAP", True),
        ("from importlib.resources import files", True),
        ("from steadyhand_idx.universe import Lq45Universe", False),
        ("from steadyhand_idx import Lq45Universe", False),
        ("from steadyhand.backtest import backtest", False),
    ],
)
def test_the_idx_training_allowlist(line: str, *, ok: bool) -> None:
    (statement,) = statements(line, "steadyhand_idx.training", is_package=True)
    assert allowed(statement, IDX_TRAINING_MAY_IMPORT, "steadyhand_idx.training") is ok


def test_only_training_and_the_output_layer_import_training() -> None:
    modules = sources()
    # Independent of the walk: both packages' modules as git lists them.
    listed = [*tracked(ENGINE, ".py"), *tracked(IDX, ".py")]
    assert sorted(name for name, _, _ in modules) == sorted(module_name(p) for p in listed)
    assert len(modules) >= MODULES_FLOOR, f"read {len(modules)} modules"
    inside = [name for name, _, _ in modules if _within(name, MAY_IMPORT_TRAINING)]
    assert {"steadyhand.training", "steadyhand_idx.training", OUTPUT_LAYER} <= set(inside)
    judged = [
        (name, statement)
        for name, is_package, source in modules
        if not _within(name, MAY_IMPORT_TRAINING)
        for statement in statements(source, name, is_package=is_package)
    ]
    assert len(judged) >= IMPORTS_FLOOR, f"judged {len(judged)} import statements"
    found = [f"{name}: {base}" for name, (base, names) in judged if imports_training((base, names))]
    assert searched(found, of=len(judged), what="import statements") == []


@pytest.mark.parametrize("module", [name for name, _, _ in sources()])
def test_the_module_is_read_as_every_import_its_text_holds(module: str) -> None:
    # Independent of the AST reader: a raw count of the lines that open an import.
    ((is_package, source),) = [(p, text) for name, p, text in sources() if name == module]
    assert len(statements(source, module, is_package=is_package)) >= len(RAW_IMPORT.findall(source))


def test_the_output_layer_is_the_exception_it_is_listed_as() -> None:
    (source,) = [text for name, _, text in sources() if name == OUTPUT_LAYER]
    found = statements(source, OUTPUT_LAYER, is_package=False)
    assert [base for base, names in found if imports_training((base, names))] == [
        "steadyhand.training",
        "steadyhand_idx.training",
    ]


@pytest.mark.parametrize("module", ["steadyhand_idx.config", "steadyhand_idx.cli"])
def test_the_configuration_and_the_commands_stay_outside_the_exception(module: str) -> None:
    assert module in [name for name, _, _ in sources()]
    assert not _within(module, MAY_IMPORT_TRAINING)


def test_training_imports_nothing_that_decides() -> None:
    checked = 0
    found: list[str] = []
    for name, is_package, source in sources():
        for own, allowlist in zip(
            TRAINING, (ENGINE_TRAINING_MAY_IMPORT, IDX_TRAINING_MAY_IMPORT), strict=True
        ):
            if not _within(name, (own,)):
                continue
            for statement in statements(source, name, is_package=is_package):
                checked += 1
                if not allowed(statement, allowlist, own):
                    found.append(f"{name}: {statement[0]}")
    assert checked >= TRAINING_IMPORTS_FLOOR, f"read {checked} imports of the training modules"
    assert searched(found, of=checked, what="imports of the training modules") == []


@pytest.mark.parametrize("phrase", ADVICE_PHRASES)
def test_each_advice_phrase_is_found_in_any_case(phrase: str) -> None:
    assert advice_phrases(f"Here {phrase.upper()} it is.") == [phrase]


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("BBCA is a buy.", ["BBCA is a buy"]),
        ("Then TLKM, you sell.", ["TLKM, you sell"]),
        ("ASII looks cheap, BUY", ["ASII looks cheap, BUY"]),
        ("UNVR one two three sell", []),
        ("Stock A is one you might buy.", []),
        ("The IDX lets you buy in lots.", []),
        ("BBCAX is a buy.", []),
        ("bbca is a buy.", []),
        ("BBCA is a buyer.", []),
    ],
)
def test_a_ticker_followed_by_buy_or_sell_is_found(text: str, found: list[str]) -> None:
    assert advice_phrases(text) == found


def test_a_phrase_is_found_across_lines_quotes_and_curly_apostrophes() -> None:
    assert advice_phrases("You should\n> buy it.") == ["you should buy"]
    assert advice_phrases("You can" + chr(0x2019) + "t lose.") == ["can't lose"]
    assert advice_phrases("<!-- we recommend it -->") == ["we recommend"]


def test_the_fixture_lessons_carry_no_advice() -> None:
    catalogue = Catalogue.load([FIXTURE / "engine/en", FIXTURE / "idx/en"], FIXTURE / "course.toml")
    assert len(catalogue.lessons()) == 3
    assert advice_findings(catalogue) == []


PLANTED_ADVICE = {
    "body": ("A fixture lesson in the other package's folder.\n", "You should buy lots.\n"),
    "title": ('title = "Lots"\n', 'title = "Lots you should buy"\n'),
    "summary": ('size."\n', 'size, which you should buy."\n'),
}


@pytest.mark.parametrize("field", PLANTED_ADVICE)
def test_an_advice_finding_names_the_file_and_the_phrase(tmp_path: Path, field: str) -> None:
    copy = Path(shutil.copytree(FIXTURE, tmp_path / "training"))
    lesson = copy / "idx/en/fixture.lots.md"
    old, new = PLANTED_ADVICE[field]
    text = lesson.read_text(encoding="utf-8")
    assert text.count(old) == 1
    lesson.write_text(text.replace(old, new), "utf-8")
    catalogue = Catalogue.load([copy / "engine/en", copy / "idx/en"], copy / "course.toml")
    assert advice_findings(catalogue) == [f"{lesson}: you should buy"]
