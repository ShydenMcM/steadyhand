"""No test reads a file on CI's docs-only fast path, judged from what the run opened (#218).

``scripts/ci_scope.py`` lets a pull request that only adds or edits ``HANDOVER.md`` and
``docs/superpowers/**`` skip the tests. That is safe only while no test reads those files, so
the recorder installed by ``tests/conftest.py`` notes every repository file the run opens, and
this guard, moved to the end of the run, judges them against the classifier's own allowlist.
A partial run has not opened what the whole suite opens, so it fails by name; run the whole
suite. Some CLI journeys run the installed console script in its own process
(``tests/cli/cli_world.py``), which the hook cannot see, so a static check covers what that code
could name.
"""

import pytest
from file_reads import RECORDER
from population import ROOT, searched, tracked
from test_disclaimer import user_docs

from ci_scope import on_fast_path

# Measured on 2026-10-06 (#218): the whole run opened 250 of the files git lists, the same with a
# warm bytecode cache and a cold one, and the packages hold 57 Python sources. Lower each only by a
# deliberate edit when the repo shrinks.
OPENED_FLOOR = 249
PACKAGE_SOURCES_FLOOR = 56
WHOLE_SUITE = "run the whole suite: this guard judges what every other test opened"


@pytest.mark.last
def test_the_run_opened_no_file_on_the_docs_only_fast_path(request: pytest.FixtureRequest) -> None:
    items = request.session.items
    last = [item for item in items if item.get_closest_marker("last")]
    assert items[-len(last) :] == last, "a guard marked last ran before other tests"
    # The files git lists, the only ones a diff can name: caches under the root (.venv, bytecode,
    # .hypothesis) come and go with the machine, not with what the tests read.
    listed = {path.relative_to(ROOT).as_posix() for path in tracked(ROOT, "")}
    opened = RECORDER.opened & listed
    on_it = sorted(path for path in opened if on_fast_path(path))
    assert searched(on_it, of=len(opened), what="repository files the run opened") == []
    assert RECORDER.unread == ()
    expected = {path.relative_to(ROOT).as_posix() for path in user_docs(ROOT / "docs")}
    assert "docs/lq45-members.md" in expected
    assert sorted(expected - opened) == [], WHOLE_SUITE
    assert len(opened) >= OPENED_FLOOR


def test_no_package_code_names_a_file_on_the_fast_path() -> None:
    sources = tracked(ROOT / "packages", ".py")
    assert ROOT / "packages/steadyhand/src/steadyhand/__init__.py" in sources
    assert len(sources) >= PACKAGE_SOURCES_FLOOR
    naming = [
        path.relative_to(ROOT).as_posix()
        for path in sources
        if any(name in path.read_text(encoding="utf-8") for name in ("HANDOVER", "superpowers"))
    ]
    assert searched(naming, of=len(sources), what="package sources") == []
