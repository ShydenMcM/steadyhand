"""Nothing raises a unit test's limit (#323).

Shyden's rule (2026-10-07, every project): every unit test runs in under 1 s of wall and at or
under 0.1 s of its own thread CPU, and no limit is ever raised. Both limits are set in one place,
``tests/plugins/unit_limits.py``, for a unit run coverage is not tracing; the other suites keep one
limit at their CI step and none inside. So no test, helper, config or workflow may set a limit of
its own (#323 AC 2, AC 3):

* a ``timeout`` marker or option, however it is reached (``pytest.mark.timeout``, ``mark`` imported
  or renamed, ``getattr`` on a ``mark``, the marker's name as a string, ``config.option.timeout``);
* a pytest-timeout flag, ini key or environment variable in ``pyproject.toml`` or a workflow, or
  vitest's limit flags in a workflow;
* a clock read in a unit file, which is how a test would hold a time budget of its own: the clock
  modules imported in any form, ``.now()`` and ``.utcnow()``, and ``.today()`` on anything but a
  ``date`` (a calendar day cannot time a test).

The one carve-out is ``tests/perf``'s product budgets (Shyden, "Keep them"): those files may import
a clock, one import each, pinned below. The two clocks themselves (``load_clock.py``,
``unit_limits.py``) are pinned site by site. Python floors are literal at their measured figure
until #272 records them (Shyden, 2026-10-15: "Literal now, #272 converts").
"""

import ast
import io
import re
import tokenize
import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from config_strings import strings_in
from floors import floor_breach
from population import searched, tracked
from source_tree import UnreadableSourceError, parse
from suites import suite_of

ROOT = Path(__file__).resolve().parents[2]
TESTS = ROOT / "tests"
WORKFLOWS = ROOT / ".github/workflows"
LIMITS_HOME = TESTS / "plugins/unit_limits.py"
CLOCKS = (TESTS / "plugins/load_clock.py", LIMITS_HOME)
PERF = TESTS / "perf"


CLOCK_MODULES = frozenset({"time", "timeit", "resource"})
FLAG = re.compile(
    r"--timeout\b|--session-timeout|-o\s*(?:session_)?timeout"
    r"|--override-ini[= ]?(?:session_)?timeout|PYTEST_TIMEOUT"
    r"|--(?:test|hook|teardown)-?[Tt]imeout\b"
)


def _sorted(found: list[tuple[ast.expr | ast.stmt, str]]) -> list[str]:
    ordered = sorted(found, key=lambda pair: (pair[0].lineno, pair[0].col_offset))
    return [f"line {node.lineno}: {what}" for node, what in ordered]


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}


def _is_mark(node: ast.expr) -> bool:
    """``mark`` or ``<anything>.mark``: the object pytest's markers hang from."""
    return (isinstance(node, ast.Name) and node.id == "mark") or (
        isinstance(node, ast.Attribute) and node.attr == "mark"
    )


def limits(source: str, name: str) -> list[str]:
    """Each place *source* sets, or names, a test limit: ``line N: what``.

    The marker's name as a bare string is refused everywhere but as the operand of a comparison,
    which cannot set a marker: passed, assigned or collected, it can (``add_marker("timeout")``).
    """
    tree = parse(source, name)
    parents = _parents(tree)
    found: list[tuple[ast.expr | ast.stmt, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "timeout":
            found.append((node, ".timeout"))
        elif isinstance(node, ast.ImportFrom) and any(a.name == "timeout" for a in node.names):
            found.append((node, "timeout imported by name"))
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and node.args
            and _is_mark(node.args[0])
        ):
            found.append((node, "getattr on a mark"))
        elif (
            isinstance(node, ast.Constant)
            and node.value == "timeout"
            and not isinstance(parents[node], ast.Compare | ast.Expr)
        ):
            found.append((node, "the marker name 'timeout' as a string"))
    return _sorted(found)


def _imports_by_call(func: ast.expr) -> bool:
    """``__import__(...)`` and ``import_module(...)``, however ``importlib`` is reached."""
    return (isinstance(func, ast.Name) and func.id in {"__import__", "import_module"}) or (
        isinstance(func, ast.Attribute) and func.attr == "import_module"
    )


def _clock_call(node: ast.Call) -> str | None:
    if _imports_by_call(node.func):
        module = node.args[0] if node.args else None
        if not (isinstance(module, ast.Constant) and isinstance(module.value, str)):
            return "a module imported by a name not written"
        top = module.value.split(".")[0]
        return f"the clock module {top} imported" if top in CLOCK_MODULES else None
    if not isinstance(node.func, ast.Attribute):
        return None
    if node.func.attr in {"now", "utcnow"}:
        return f".{node.func.attr}() reads a clock"
    on_a_date = isinstance(node.func.value, ast.Name) and node.func.value.id == "date"
    return ".today() reads a clock" if node.func.attr == "today" and not on_a_date else None


def clocks(source: str, name: str) -> list[str]:
    """Each clock *source* reads: ``line N: what``. ``date.today()`` is a calendar day, which
    cannot time a test, so it is no clock read."""
    found: list[tuple[ast.expr | ast.stmt, str]] = []
    for node in ast.walk(parse(source, name)):
        if isinstance(node, ast.Import):
            tops = [alias.name.split(".")[0] for alias in node.names]
            found.extend(
                (node, f"the clock module {top} imported") for top in tops if top in CLOCK_MODULES
            )
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
            top = node.module.split(".")[0]
            if top in CLOCK_MODULES:
                found.append((node, f"the clock module {top} imported"))
        elif isinstance(node, ast.Call) and (what := _clock_call(node)) is not None:
            found.append((node, what))
    return _sorted(found)


def flags(text: str) -> list[str]:
    """Each limit flag or variable in one key or value of a workflow or ``pyproject.toml``."""
    return [match.group(0) for match in FLAG.finditer(text)]


def ini_limits(pyproject: dict[str, Any]) -> list[str]:
    """Each pytest ini key in *pyproject* that sets a limit: pytest-timeout's every key."""
    options = pyproject.get("tool", {}).get("pytest", {}).get("ini_options", {})
    return [f"[tool.pytest.ini_options] {key}" for key in options if "timeout" in key]


def attributes(source: str, name: str) -> int:
    """How many attribute reads the parse tree of *source* holds."""
    return sum(isinstance(node, ast.Attribute) for node in ast.walk(parse(source, name)))


def _tokens(source: str) -> list[tokenize.TokenInfo]:
    skipped = {tokenize.NL, tokenize.COMMENT}
    stream = tokenize.generate_tokens(io.StringIO(source).readline)
    return [token for token in stream if token.type not in skipped]


def attributes_by_tokens(source: str) -> int:
    """The same count from the token stream: a name after a dot, outside an import statement
    (``import a.b`` and ``from c.d import e`` name modules: the tree holds no attribute there)."""
    count = 0
    in_import = False
    previous: tokenize.TokenInfo | None = None
    for token in _tokens(source):
        starts = (
            previous is None
            or previous.type
            in {
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
            }
            or previous.string == ";"
        )
        if starts:
            in_import = token.string in {"import", "from"}
        if (
            token.type == tokenize.NAME
            and previous is not None
            and previous.string == "."
            and not in_import
        ):
            count += 1
        previous = token
    return count


def imports(source: str, name: str) -> int:
    """How many import statements the parse tree of *source* holds."""
    tree = parse(source, name)
    return sum(isinstance(node, ast.Import | ast.ImportFrom) for node in ast.walk(tree))


def imports_by_tokens(source: str) -> int:
    """The same count from the token stream: each ``import`` keyword."""
    return sum(
        token.type == tokenize.NAME and token.string == "import" for token in _tokens(source)
    )


LIMITS = {
    "a decorator": ("@pytest.mark.timeout(5)\ndef test_a():\n    pass\n", 1, [".timeout"]),
    "a module mark": ("pytestmark = pytest.mark.timeout(5)\n", 1, [".timeout"]),
    "a mark in a list": (
        "pytestmark = [pytest.mark.perf, pytest.mark.timeout(5)]\n",
        1,
        [".timeout"],
    ),
    "a param's marks": (
        "CASES = [pytest.param(1, marks=pytest.mark.timeout(5))]\n",
        1,
        [".timeout"],
    ),
    "mark imported": (
        "from pytest import mark\n\n\n@mark.timeout(5)\ndef test_a():\n    pass\n",
        4,
        [".timeout"],
    ),
    "mark renamed": (
        "from pytest import mark as m\n\n\n@m.timeout(5)\ndef test_a():\n    pass\n",
        4,
        [".timeout"],
    ),
    "a marker added in a hook": (
        (
            "def pytest_collection_modifyitems(items):\n    for item in items:\n"
            "        item.add_marker(pytest.mark.timeout(5))\n"
        ),
        3,
        [".timeout"],
    ),
    "a marker applied by its name": (
        'def test_a(request):\n    request.applymarker("timeout")\n',
        2,
        ["the marker name 'timeout' as a string"],
    ),
    "a marker by getattr": ("LIMIT = getattr(pytest.mark, name)(5)\n", 1, ["getattr on a mark"]),
    "a marker by getattr and its name": (
        'LIMIT = getattr(mark, "timeout")(5)\n',
        1,
        ["getattr on a mark", "the marker name 'timeout' as a string"],
    ),
    "the marker name held": ('NAME = "timeout"\n', 1, ["the marker name 'timeout' as a string"]),
    "the marker name in a list": (
        'MARKS = ["perf", "timeout"]\n',
        1,
        ["the marker name 'timeout' as a string"],
    ),
    "an option set": (
        "def pytest_configure(config):\n    config.option.timeout = 5\n",
        2,
        [".timeout"],
    ),
    "timeout imported": ("from pytest_timeout import timeout\n", 1, ["timeout imported by name"]),
    "timeout imported renamed": ("from x import timeout as t\n", 1, ["timeout imported by name"]),
}


@pytest.mark.parametrize("form", LIMITS)
def test_each_form_of_a_limit_is_found(form: str) -> None:
    source, line, what = LIMITS[form]
    assert limits(source, "planted.py") == [f"line {line}: {w}" for w in what]


ALLOWED_LIMITS = {
    "another marker": "@pytest.mark.perf\ndef test_a():\n    pass\n",
    "a marker added": "item.add_marker(pytest.mark.last)\n",
    "a call's own timeout": "asyncio.wait_for(job, timeout=1)\n",
    "an option read": 'config.getoption("suite")\n',
    "a docstring naming it": '"""timeout"""\n',
    "a comparison with the name": 'if marker.name == "timeout":\n    pass\n',
    "a longer string": 'TEXT = "a timeout marker"\n',
}


@pytest.mark.parametrize("form", ALLOWED_LIMITS)
def test_what_sets_no_limit(form: str) -> None:
    assert limits(ALLOWED_LIMITS[form], "allowed.py") == []


CLOCK_READS = {
    "import time": ("import time\n", "the clock module time imported"),
    "import time renamed": ("import time as t\n", "the clock module time imported"),
    "a clock from time": ("from time import perf_counter\n", "the clock module time imported"),
    "timeit": ("import timeit\n", "the clock module timeit imported"),
    "resource": ("from resource import getrusage\n", "the clock module resource imported"),
    "import_module": (
        'clock = importlib.import_module("time")\n',
        "the clock module time imported",
    ),
    "__import__": ('clock = __import__("time")\n', "the clock module time imported"),
    "an import not written": (
        "module = importlib.import_module(name)\n",
        "a module imported by a name not written",
    ),
    "datetime.now": ("started = datetime.now()\n", ".now() reads a clock"),
    "datetime.now(UTC)": ("started = datetime.now(UTC)\n", ".now() reads a clock"),
    "utcnow": ("started = datetime.utcnow()\n", ".utcnow() reads a clock"),
    "datetime.today": ("started = datetime.today()\n", ".today() reads a clock"),
    "a renamed datetime": ("started = dt.now()\n", ".now() reads a clock"),
}


@pytest.mark.parametrize("form", CLOCK_READS)
def test_each_clock_read_is_found(form: str) -> None:
    source, what = CLOCK_READS[form]
    assert clocks(source, "planted.py") == [f"line 1: {what}"]


ALLOWED_CLOCKS = {
    "today's date": "today = date.today()\n",
    "a fixed clock of the test's own": "world = World(lambda: self.now)\n",
    "a fixed datetime": "AT = datetime(2026, 10, 15, 9, tzinfo=UTC)\n",
    "datetime imported": "from datetime import UTC, date, datetime\n",
    "a module by its written name": 'module = importlib.import_module("steadyhand.cli")\n',
}


@pytest.mark.parametrize("form", ALLOWED_CLOCKS)
def test_what_reads_no_clock(form: str) -> None:
    assert clocks(ALLOWED_CLOCKS[form], "allowed.py") == []


FLAGS = {
    "--timeout=": ("pytest --timeout=5", "--timeout"),
    "--timeout ": ("pytest --timeout 5", "--timeout"),
    "-o timeout": ("pytest -o timeout=5", "-o timeout"),
    "-otimeout": ("pytest -otimeout=5", "-otimeout"),
    "--override-ini": ("pytest --override-ini=timeout=5", "--override-ini=timeout"),
    "--session-timeout": ("pytest --session-timeout=60", "--session-timeout"),
    "-o session_timeout": ("pytest -o session_timeout=60", "-o session_timeout"),
    "an env name": ("PYTEST_TIMEOUT", "PYTEST_TIMEOUT"),
    "in PYTEST_ADDOPTS": ("--timeout=5", "--timeout"),
    "--testTimeout": ("npx vitest run --testTimeout=5000", "--testTimeout"),
    "--test-timeout": ("npx vitest run --test-timeout 5000", "--test-timeout"),
    "--hookTimeout": ("npx vitest run --hookTimeout=5000", "--hookTimeout"),
    "--hook-timeout": ("npx vitest run --hook-timeout=5000", "--hook-timeout"),
    "--teardownTimeout": ("npx vitest run --teardownTimeout=5000", "--teardownTimeout"),
}


@pytest.mark.parametrize("form", FLAGS)
def test_each_limit_flag_is_found(form: str) -> None:
    text, flag = FLAGS[form]
    assert flags(text) == [flag]


ALLOWED_FLAGS = {
    "a step's limit": "timeout-minutes",
    "the dependency": "pytest-timeout>=2.4.0",
    "a suite run": "uv run --locked pytest -W error --suite properties -p no:cacheprovider",
    "the limits run": "npm run test:limits",
}


@pytest.mark.parametrize("form", ALLOWED_FLAGS)
def test_what_is_no_limit_flag(form: str) -> None:
    assert flags(ALLOWED_FLAGS[form]) == []


@pytest.mark.parametrize(
    "line",
    [
        "timeout = 5",
        "session_timeout = 60",
        'timeout_method = "thread"',
        "timeout_func_only = true",
    ],
)
def test_each_pytest_timeout_ini_key_is_found(line: str) -> None:
    pyproject = tomllib.loads(
        f'[tool.pytest.ini_options]\naddopts = "-p no:cacheprovider"\n{line}\n'
    )
    assert ini_limits(pyproject) == [f"[tool.pytest.ini_options] {line.split(' ', maxsplit=1)[0]}"]


def test_a_pyproject_with_no_pytest_table_sets_no_limit() -> None:
    assert ini_limits({"project": {"name": "x"}}) == []


def test_a_module_that_does_not_parse_is_refused_by_name() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^broken\.py: "):
        limits("def f(:\n", "broken.py")


# The one place a limit is set (AC 2), pinned by literal.
def test_unit_limits_is_the_one_place_a_limit_is_set_and_it_is_a_second() -> None:
    source = LIMITS_HOME.read_text(encoding="utf-8")
    assert [re.sub(r"^line \d+: ", "", f) for f in limits(source, "unit_limits.py")] == [".timeout"]
    assert "item.add_marker(pytest.mark.timeout(WALL_LIMIT_SECONDS))" in source
    constants = {
        target.id: node.value.value
        for node in parse(source, "unit_limits.py").body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    assert constants["WALL_LIMIT_SECONDS"] == 1
    assert constants["CPU_LIMIT_MICROSECONDS"] == 100_000


@pytest.mark.parametrize("path", CLOCKS, ids=lambda path: path.name)
def test_each_clock_reads_only_the_time_module(path: Path) -> None:
    found = clocks(path.read_text(encoding="utf-8"), path.name)
    assert [re.sub(r"^line \d+: ", "", f) for f in found] == ["the clock module time imported"]


# The carve-out (Shyden, "Keep them"), bound file by file: perf's product budgets, one clock each.
PERF_CLOCKS = {
    "tests/perf/synthetic.py": 0,
    "tests/perf/test_cli_startup.py": 1,
    "tests/perf/test_factor_performance.py": 1,
    "tests/perf/test_paper_performance.py": 1,
    "tests/perf/test_performance.py": 1,
}


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_perf_reads_the_clocks_its_budgets_need_and_no_more() -> None:
    files = tracked(PERF, ".py")
    read = {rel(path): len(clocks(path.read_text(encoding="utf-8"), rel(path))) for path in files}
    assert read == PERF_CLOCKS


FILES = sorted(path for path in TESTS.rglob("*.py") if "__pycache__" not in path.parts)
UNIT_FILES = [path for path in FILES if suite_of(path) == "unit"]


def test_the_files_judged_are_the_ones_git_lists() -> None:
    assert [rel(path) for path in FILES] == [rel(path) for path in tracked(TESTS, ".py")]
    assert LIMITS_HOME in FILES
    assert floor_breach("python.no-raised-limit.files", len(FILES)) is None


def test_no_test_or_helper_sets_a_limit_outside_the_one_place() -> None:
    judged = [path for path in FILES if path != LIMITS_HOME]
    found = [
        f"{rel(path)} {finding}"
        for path in judged
        for finding in limits(path.read_text(encoding="utf-8"), rel(path))
    ]
    assert searched(found, of=len(judged), what="test files") == [], (
        "a unit test's limit is set in tests/plugins/unit_limits.py alone, and never raised (#323)"
    )
    assert floor_breach("python.no-raised-limit.limit-files", len(judged)) is None


def test_no_unit_file_reads_a_clock_outside_the_clocks_and_perf() -> None:
    judged = [path for path in UNIT_FILES if path not in CLOCKS and PERF not in path.parents]
    found = [
        f"{rel(path)} {finding}"
        for path in judged
        for finding in clocks(path.read_text(encoding="utf-8"), rel(path))
    ]
    assert searched(found, of=len(judged), what="unit files") == [], (
        "a unit test holds no time budget of its own: the limits are the runner's (#323)"
    )
    assert floor_breach("python.no-raised-limit.unit-files", len(judged)) is None


def test_no_workflow_sets_a_limit() -> None:
    every = sorted([*tracked(WORKFLOWS, ".yml"), *tracked(WORKFLOWS, ".yaml")])
    read = [text for path in every for text in strings_in(yaml.safe_load(path.read_text()))]
    found = [flag for text in read for flag in flags(text)]
    assert searched(found, of=len(read), what="workflow keys and values") == []
    assert floor_breach("python.no-raised-limit.workflow-strings", len(read)) is None


def test_pyproject_sets_no_limit() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    read = list(strings_in(pyproject))
    found = [flag for text in read for flag in flags(text)] + ini_limits(pyproject)
    assert searched(found, of=len(read), what="pyproject keys and values") == []
    assert floor_breach("python.no-raised-limit.pyproject-strings", len(read)) is None


# Independent of the parse tree: the token stream counts what the readers judge, file by file.
@pytest.mark.parametrize("path", FILES, ids=rel)
def test_every_attribute_and_import_is_read(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    assert attributes(source, rel(path)) == attributes_by_tokens(source)
    assert imports(source, rel(path)) == imports_by_tokens(source)


def test_the_token_counts_see_a_planted_attribute_and_import() -> None:
    source = "import a\nfrom b import c\nx = a.d.e\n"
    assert (attributes_by_tokens(source), imports_by_tokens(source)) == (2, 2)
    assert (attributes(source, "planted.py"), imports(source, "planted.py")) == (2, 2)


def test_a_dotted_import_is_no_attribute_to_either_count() -> None:
    source = "import a.b\nfrom c.d import e\nfrom . import f\n"
    assert (attributes_by_tokens(source), attributes(source, "planted.py")) == (0, 0)
