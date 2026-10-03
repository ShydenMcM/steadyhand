"""No retry anywhere in the packages (#179).

Shyden's rule (2026-10-02): a retry is not a fix. It turns a real failure into a pass and hides
the cause; where the cause is outside our control, fail fast and say so by name. A *retry* here
is a loop holding a ``try`` whose handler swallows the failure (no ``raise``) while the ``try``
body uses nothing that changes from one pass to the next: neither the loop's target nor a name
the loop assigns outside the ``try``. So the same call is simply made again. A loop that
handles each item in turn (a refused stock noted, the next one read) uses its target, and passes.
"""

import ast
import re
from pathlib import Path

import pytest
from population import tracked
from source_tree import UnreadableSourceError, parse

ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ROOT / "packages"
LOOP = ast.For | ast.AsyncFor | ast.While
RAW_FOR = re.compile(r"^[ \t]*(?:async[ \t]+)?for[ \t].*[ \t]in[ \t].*:[ \t]*(?:#.*)?$", re.M)
RAW_WHILE = re.compile(r"^[ \t]*while[ \t(].*:[ \t]*(?:#.*)?$", re.M)

# Measured on 2026-10-03 after #179: 180 loops read in 57 files. Lower it only by a deliberate
# edit when the packages shrink.
LOOPS_READ_FLOOR = 179


def _stored(nodes: list[ast.stmt]) -> set[str]:
    return {
        node.id
        for statement in nodes
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)
    }


def _loaded(nodes: list[ast.stmt]) -> set[str]:
    return {
        node.id
        for statement in nodes
        for node in ast.walk(statement)
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
    }


def _tries(statements: list[ast.stmt]) -> list[ast.Try]:
    """The ``try`` statements in *statements* whose nearest loop is the one holding them: the
    walk stops at a nested loop or function, which judge their own."""
    found: list[ast.Try] = []
    stack: list[ast.AST] = list(statements)
    while stack:
        node = stack.pop()
        if isinstance(node, LOOP | ast.FunctionDef | ast.AsyncFunctionDef | ast.Lambda):
            continue
        if isinstance(node, ast.Try):
            found.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return found


def _swallows(handler: ast.ExceptHandler) -> bool:
    return not any(isinstance(node, ast.Raise) for node in ast.walk(handler))


def read(source: str, name: str) -> tuple[int, int, list[str]]:
    """``(for loops, while loops, retries)`` in *source*; *name* names the file in errors."""
    tree = parse(source, name)
    fors = whiles = 0
    retries: list[str] = []
    for loop in ast.walk(tree):
        if not isinstance(loop, LOOP):
            continue
        if isinstance(loop, ast.While):
            whiles += 1
            changing: set[str] = set()
        else:
            fors += 1
            changing = _stored([ast.Expr(loop.target)])
        tries = _tries(loop.body)
        inside = [statement for found in tries for statement in found.body]
        changing |= _stored(loop.body) - _stored(inside)
        retries.extend(
            f"line {loop.lineno}"
            for found in tries
            if any(_swallows(handler) for handler in found.handlers)
            and not _loaded(found.body) & changing
        )
    return fors, whiles, sorted(set(retries))


PLANTED = {
    "a for over range": "for _ in range(3):\n    try:\n        f()\n    except E:\n        pass\n",
    "a for that continues": (
        "for attempt in range(3):\n    try:\n        f()\n    except E:\n        continue\n"
    ),
    "a while True": (
        "while True:\n    try:\n        f()\n        break\n    except E:\n        pass\n"
    ),
    "an async for": (
        "async def g():\n    async for _ in tries():\n        try:\n            await f()\n"
        "        except E:\n            pass\n"
    ),
    "a try that assigns and returns": (
        "def g():\n    for _ in range(3):\n        try:\n            got = f()\n"
        "            return got\n        except E:\n            pass\n"
    ),
    "a backoff, as Yahoo's was": (
        "def g(policy):\n    failure = None\n    for attempt in range(policy.attempts):\n"
        "        if attempt:\n            sleep(2 ** attempt)\n        try:\n"
        "            return download(ticker)\n        except E as error:\n"
        "            failure = error\n    raise E(failure)\n"
    ),
}


@pytest.mark.parametrize("form", PLANTED)
def test_each_form_of_retry_is_found(form: str) -> None:
    source = PLANTED[form]
    first = next(n for n in ast.walk(parse(source, "planted.py")) if isinstance(n, LOOP))
    assert read(source, "planted.py")[2] == [f"line {first.lineno}"]


ALLOWED = {
    "a loop over items that notes each refusal": (
        "for stock in stocks:\n    try:\n        f(stock)\n    except E as error:\n"
        "        refused[stock] = str(error)\n"
    ),
    "a handler that re-raises": (
        "for _ in range(3):\n    try:\n        f()\n    except E as error:\n"
        "        raise F from error\n"
    ),
    "a while over a queue": (
        "while queue:\n    item = queue.pop()\n    try:\n        f(item)\n    except E:\n"
        "        pass\n"
    ),
    "a per-item try inside a per-day loop": (
        "for day in days:\n    for stock in stocks:\n        try:\n            f(stock)\n"
        "        except E:\n            pass\n"
    ),
    "a try in no loop": "try:\n    f()\nexcept E:\n    pass\n",
}


@pytest.mark.parametrize("form", ALLOWED)
def test_what_is_not_a_retry(form: str) -> None:
    assert read(ALLOWED[form], "allowed.py")[2] == []


def test_a_retry_inside_a_loop_over_items_is_named_by_its_own_loop() -> None:
    # Each try is judged by its nearest loop, so the loop over items is not blamed as well.
    source = (
        "for stock in stocks:\n    while True:\n        try:\n            f()\n"
        "            break\n        except E:\n            pass\n"
    )
    assert read(source, "nested.py")[2] == ["line 2"]


def test_a_module_that_does_not_parse_is_refused_by_name() -> None:
    with pytest.raises(UnreadableSourceError, match=r"^broken\.py: "):
        read("for x in:\n", "broken.py")


def package_files() -> list[Path]:
    """Every module of both packages, found on disk."""
    return sorted(PACKAGES.rglob("*.py"))


FILES = package_files()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_every_loop_in_the_packages_is_read() -> None:
    names = {rel(path) for path in FILES}
    assert {
        "packages/steadyhand/src/steadyhand/backtest.py",
        "packages/steadyhand-idx/src/steadyhand_idx/yahoo.py",
    } <= names
    # Independent of the walk: the packages' modules as git lists them (#178).
    assert names == {rel(path) for path in tracked(PACKAGES, ".py")}
    total = sum(sum(read(path.read_text(encoding="utf-8"), rel(path))[:2]) for path in FILES)
    assert total >= LOOPS_READ_FLOOR, f"read {total} loops in {len(FILES)} files"


@pytest.mark.parametrize("path", FILES, ids=rel)
def test_the_module_holds_no_retry(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    fors, whiles, retries = read(source, rel(path))
    # Independent of the AST reader: every line that opens a loop block is read as a loop.
    assert fors >= len(RAW_FOR.findall(source))
    assert whiles >= len(RAW_WHILE.findall(source))
    assert retries == [], "fail fast, by name: a retry is not a fix (#179)"
