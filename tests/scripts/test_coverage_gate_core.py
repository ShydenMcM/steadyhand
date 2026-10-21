"""The coverage gate's core (#381): every suite's report joined per file into untested counts,
the record those counts must equal, and every changed line run or the pull request fails.

Shyden's rulings: "Ratchet to 100%, unmeasured fails now" (2026-10-21); "Count them as unrun",
"Untested count", "Must be recorded" (2026-10-22, global).
"""

from functools import cache
from typing import Any

import pytest

from coverage_gate import (
    Counts,
    FileCoverage,
    GateError,
    Record,
    changed_lines,
    compare,
    counts,
    failures_on_changed_lines,
    from_istanbul,
    from_python,
    from_workflow,
    ignore_hints,
    join,
    measured_record,
    percentages,
    ratchet,
    renames_in,
)

ROOT = "/work/repo"


def python_report(**files: dict[str, Any]) -> dict[str, Any]:
    """A coverage.py JSON report (format 3) holding *files*."""
    shaped = {
        path: {
            "executed_lines": data.get("executed", []),
            "missing_lines": data.get("missing", []),
            "excluded_lines": data.get("excluded", []),
            "executed_branches": data.get("arms_run", []),
            "missing_branches": data.get("arms_missed", []),
        }
        for path, data in files.items()
    }
    return {"meta": {"format": 3, "branch_coverage": True}, "files": shaped}


def span(first: int, last: int) -> dict[str, Any]:
    return {"start": {"line": first, "column": 0}, "end": {"line": last, "column": 9}}


def istanbul_file(
    path: str, statements: list[tuple[int, int, int]], arms: list[list[tuple[int, int]]]
) -> dict[str, Any]:
    """An istanbul file entry: statements as (first, last, hits); branches as lists of arms,
    each arm (line, hits)."""
    return {
        "path": f"{ROOT}/{path}",
        "statementMap": {
            str(i): span(first, last) for i, (first, last, _) in enumerate(statements)
        },
        "s": {str(i): hits for i, (_, _, hits) in enumerate(statements)},
        "branchMap": {
            str(i): {
                "loc": span(arm[0][0], arm[0][0]),
                "locations": [span(line, line) for line, _ in arm],
            }
            for i, arm in enumerate(arms)
        },
        "b": {str(i): [hits for _, hits in arm] for i, arm in enumerate(arms)},
        "fnMap": {},
        "f": {},
    }


# --- reading each report -----------------------------------------------------------------------


def test_python_counts_a_skipped_line_as_unrun_and_an_arm_by_its_from_line() -> None:
    report = python_report(
        **{
            "scripts/a.py": {
                "executed": [1, 2],
                "missing": [3],
                "excluded": [4],
                "arms_run": [[2, 3]],
                "arms_missed": [[2, 5]],
            }
        }
    )
    found = from_python(report)["scripts/a.py"]
    assert counts(found) == Counts(statements=4, untested_statements=2, arms=2, untested_arms=1)


def test_python_needs_branch_data() -> None:
    report = python_report(**{"a.py": {"executed": [1]}})
    report["meta"]["branch_coverage"] = False
    with pytest.raises(GateError, match="branch"):
        from_python(report)


def test_python_refuses_an_unknown_format() -> None:
    report = python_report(**{"a.py": {"executed": [1]}})
    report["meta"]["format"] = 2
    with pytest.raises(GateError, match="format"):
        from_python(report)


def test_istanbul_reads_statements_and_arms_relative_to_the_root() -> None:
    entry = istanbul_file("extension/a.ts", [(1, 1, 3), (2, 4, 0)], [[(5, 1), (6, 0)]])
    found = from_istanbul({entry["path"]: entry}, ROOT)
    assert list(found) == ["extension/a.ts"]
    assert counts(found["extension/a.ts"]) == Counts(
        statements=2, untested_statements=1, arms=2, untested_arms=1
    )


def test_istanbul_refuses_a_file_outside_the_root() -> None:
    entry = istanbul_file("a.ts", [(1, 1, 1)], [])
    entry["path"] = "/elsewhere/a.ts"
    with pytest.raises(GateError, match="outside"):
        from_istanbul({entry["path"]: entry}, ROOT)


def test_istanbul_takes_an_arm_without_a_location_from_its_branch() -> None:
    entry = istanbul_file("a.ts", [(1, 1, 1)], [[(5, 1), (6, 0)]])
    entry["branchMap"]["0"]["locations"][1] = {}
    found = from_istanbul({entry["path"]: entry}, ROOT)["a.ts"]
    assert sorted(unit.first for unit in found.arms.values()) == [5, 5]


def test_a_workflow_report_holds_lines_only() -> None:
    report = {
        "files": {".github/workflows/ci.yml": {"executed_lines": [1, 2], "missing_lines": [3]}}
    }
    found = from_workflow(report)[".github/workflows/ci.yml"]
    assert counts(found) == Counts(statements=3, untested_statements=1, arms=0, untested_arms=0)


# --- joining -----------------------------------------------------------------------------------


def test_a_line_either_python_ran_is_run() -> None:
    py312 = from_python(
        python_report(**{"a.py": {"executed": [1], "missing": [2], "arms_missed": [[1, 2]]}})
    )
    py313 = from_python(python_report(**{"a.py": {"executed": [1, 2], "arms_run": [[1, 2]]}}))
    assert counts(join([py312, py313])["a.py"]) == Counts(
        statements=2, untested_statements=0, arms=1, untested_arms=0
    )


def test_a_statement_two_reports_place_differently_is_refused() -> None:
    first = from_istanbul({f"{ROOT}/a.ts": istanbul_file("a.ts", [(1, 1, 1)], [])}, ROOT)
    second = from_istanbul({f"{ROOT}/a.ts": istanbul_file("a.ts", [(1, 2, 1)], [])}, ROOT)
    with pytest.raises(GateError, match=r"a\.ts"):
        join([first, second])


# --- the record --------------------------------------------------------------------------------


def coverage_of(**files: dict[str, Any]) -> dict[str, FileCoverage]:
    return from_python(python_report(**files))


def test_the_record_names_files_with_untested_code_and_unmeasured_code_files() -> None:
    measured = coverage_of(**{"a.py": {"executed": [1], "missing": [2]}, "b.py": {"executed": [1]}})
    record = measured_record(measured, code_files=["a.py", "b.py", "c.ts"], carried={})
    assert record == Record(files={"a.py": (1, 0)}, unmeasured=("c.ts",))


def test_a_carried_file_keeps_its_recorded_entry() -> None:
    measured = coverage_of(**{"a.py": {"executed": [1]}})
    record = measured_record(measured, code_files=["a.py", "w.yml"], carried={"w.yml": (11, 0)})
    assert record == Record(files={"w.yml": (11, 0)}, unmeasured=())


def test_an_equal_record_has_no_difference() -> None:
    record = Record(files={"a.py": (1, 0)}, unmeasured=("c.ts",))
    assert compare(record, record) == []


@pytest.mark.parametrize(
    ("recorded", "measured", "said"),
    [
        (
            Record({"a.py": (1, 0)}, ()),
            Record({"a.py": (2, 0)}, ()),
            "a.py: untested statements rose from 1 to 2",
        ),
        (
            Record({"a.py": (2, 0)}, ()),
            Record({"a.py": (1, 0)}, ()),
            "a.py: untested statements fell from 2 to 1: record it",
        ),
        (
            Record({"a.py": (0, 1)}, ()),
            Record({"a.py": (0, 3)}, ()),
            "a.py: untested branch arms rose from 1 to 3",
        ),
        (
            Record({}, ()),
            Record({"a.py": (1, 0)}, ()),
            "a.py: untested statements rose from 0 to 1",
        ),
        (
            Record({"a.py": (1, 0)}, ()),
            Record({}, ()),
            "a.py: untested statements fell from 1 to 0: record it",
        ),
        (Record({}, ("c.ts",)), Record({}, ()), "c.ts: now measured: record it"),
        (Record({}, ()), Record({}, ("c.ts",)), "c.ts: no suite measures it"),
    ],
    ids=["rise", "fall", "arms-rise", "new-file", "to-zero", "now-measured", "lost-measurement"],
)
def test_every_difference_from_the_record_is_named(
    recorded: Record, measured: Record, said: str
) -> None:
    assert compare(recorded, measured) == [said]


def test_a_record_naming_a_file_git_no_longer_lists_is_refused() -> None:
    measured = coverage_of(**{"a.py": {"executed": [1]}})
    with pytest.raises(GateError, match=r"gone\.py"):
        measured_record(measured, code_files=["a.py"], carried={"gone.py": (1, 0)})


def test_the_whole_project_percentages_are_shown() -> None:
    measured = coverage_of(
        **{
            "a.py": {
                "executed": [1, 2, 3],
                "missing": [4],
                "arms_run": [[1, 2]],
                "arms_missed": [[1, 3]],
            }
        }
    )
    assert percentages(measured) == "statements 75.00% (3 of 4), branch arms 50.00% (1 of 2)"


# --- changed lines -----------------------------------------------------------------------------

DIFF = """\
diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -1,0 +2,2 @@
+x = 1
+y = 2
@@ -9 +11 @@
-old
+new
diff --git a/gone.py b/gone.py
--- a/gone.py
+++ /dev/null
@@ -1 +0,0 @@
-z
diff --git a/b.ts b/c.ts
similarity index 90%
rename from b.ts
rename to c.ts
--- a/b.ts
+++ b/c.ts
@@ -3,0 +4 @@
+let q = 1;
"""


def test_the_changed_lines_are_each_files_added_lines() -> None:
    assert changed_lines(DIFF) == {"a.py": {2, 3, 11}, "c.ts": {4}}


def test_a_quoted_path_is_refused_not_misread() -> None:
    with pytest.raises(GateError, match="quoted"):
        changed_lines('diff --git "a/x y" "b/x y"\n--- "a/x y"\n+++ "b/x\\ty"\n@@ -0,0 +1 @@\n+a\n')


def test_a_hunk_header_that_does_not_parse_is_refused() -> None:
    with pytest.raises(GateError, match="hunk"):
        changed_lines("--- a/a.py\n+++ b/a.py\n@@ nonsense @@\n+a\n")


@cache
def measured() -> dict[str, FileCoverage]:
    """a.py and b.ts measured (read on first use, never at import: a red phase collects)."""
    return {
        **coverage_of(
            **{
                "a.py": {
                    "executed": [1, 2],
                    "missing": [3],
                    "excluded": [4],
                    "arms_missed": [[2, 5]],
                    "arms_run": [[2, 3]],
                }
            }
        ),
        **from_istanbul(
            {f"{ROOT}/b.ts": istanbul_file("b.ts", [(1, 1, 1), (2, 4, 0)], [[(5, 1), (6, 0)]])},
            ROOT,
        ),
    }


@pytest.mark.parametrize(
    ("changed", "said"),
    [
        ({"a.py": {3}}, ["a.py:3: changed, but no test ran it"]),
        ({"a.py": {4}}, ["a.py:4: changed, but no test ran it"]),
        ({"a.py": {2}}, ["a.py:2: changed, and a branch arm it begins no test took"]),
        ({"b.ts": {3}}, ["b.ts:3: changed, but no test ran it"]),
        ({"b.ts": {6}}, ["b.ts:6: changed, and a branch arm it begins no test took"]),
        (
            {"c.ts": {1, 2}},
            [
                "c.ts:1: changed in a file no suite measures",
                "c.ts:2: changed in a file no suite measures",
            ],
        ),
        ({"a.py": {1}, "b.ts": {1, 5}}, []),
        ({"README.md": {1}}, []),
    ],
    ids=[
        "unrun",
        "skipped-line",
        "untaken-arm",
        "ts-unrun",
        "ts-arm",
        "unmeasured",
        "all-run",
        "not-code",
    ],
)
def test_a_changed_line_no_test_ran_fails(changed: dict[str, set[int]], said: list[str]) -> None:
    texts = {"c.ts": "let a = 1;\nlet b = 2;\n"}
    assert (
        failures_on_changed_lines(
            measured(), ["a.py", "b.ts", "c.ts"], changed, texts, carried=set()
        )
        == said
    )


def test_a_blank_line_added_to_an_unmeasured_file_is_not_code() -> None:
    texts = {"c.ts": "let a = 1;\n\n"}
    assert (
        failures_on_changed_lines(measured(), ["c.ts"], {"c.ts": {2}}, texts, carried=set()) == []
    )


def test_a_changed_line_in_a_carried_workflow_fails_as_unmeasured() -> None:
    """A hand-started workflow the pull request changes must have been read from its runs."""
    texts = {"w.yml": "name: w\n"}
    said = failures_on_changed_lines(
        measured(), ["w.yml"], {"w.yml": {1}}, texts, carried={"w.yml"}
    )
    assert said == ["w.yml:1: changed in a file no suite measures"]


# --- ignore hints ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "/* v8 ignore next */",
        "// c8 ignore start",
        "/* istanbul ignore else */",
        "/*v8 ignore next 3*/",
    ],
    ids=["v8", "c8", "istanbul", "no-space"],
)
def test_a_coverage_ignore_hint_is_refused(line: str) -> None:
    assert ignore_hints({"extension/a.ts": f"let a = 1;\n{line}\n"}) == [
        f"extension/a.ts:2: {line}"
    ]


def test_a_file_without_hints_passes() -> None:
    assert (
        ignore_hints({"extension/a.ts": "// the v8 engine ignores nothing here\nlet a = 1;\n"})
        == []
    )


def test_a_statement_with_no_lines_is_refused() -> None:
    entry = istanbul_file("a.ts", [(1, 1, 1)], [])
    entry["statementMap"]["0"] = {}
    with pytest.raises(GateError, match="statement 0 has no lines"):
        from_istanbul({entry["path"]: entry}, ROOT)


def test_an_arm_with_no_lines_anywhere_is_refused() -> None:
    entry = istanbul_file("a.ts", [(1, 1, 1)], [[(5, 1)]])
    entry["branchMap"]["0"] = {"loc": {}, "locations": [{}]}
    with pytest.raises(GateError, match="branch 0 arm 0 has no lines"):
        from_istanbul({entry["path"]: entry}, ROOT)


def test_a_changed_line_past_the_files_end_is_refused() -> None:
    with pytest.raises(GateError, match="does not have"):
        failures_on_changed_lines(
            measured(), ["c.ts"], {"c.ts": {9}}, {"c.ts": "a\n"}, carried=set()
        )


def test_a_carried_file_recorded_as_unmeasured_stays_unmeasured() -> None:
    measured = coverage_of(**{"a.py": {"executed": [1]}})
    record = measured_record(measured, code_files=["a.py", "w.yml"], carried={"w.yml": None})
    assert record == Record(files={}, unmeasured=("w.yml",))


# --- the ratchet against the base -------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "new", "said"),
    [
        (Record({"a.py": (2, 1)}, ()), Record({"a.py": (2, 1)}, ()), []),
        (Record({"a.py": (2, 1)}, ()), Record({"a.py": (1, 0)}, ()), []),
        (
            Record({"a.py": (2, 1)}, ()),
            Record({"a.py": (3, 1)}, ()),
            ["a.py: untested statements would rise from 2 to 3"],
        ),
        (
            Record({"a.py": (2, 1)}, ()),
            Record({"a.py": (2, 2)}, ()),
            ["a.py: untested branch arms would rise from 1 to 2"],
        ),
        (
            Record({}, ()),
            Record({"n.py": (1, 0)}, ()),
            ["n.py: untested statements would rise from 0 to 1"],
        ),
        (Record({}, ()), Record({}, ("c.ts",)), ["c.ts: would become unmeasured"]),
        (Record({}, ("c.ts",)), Record({}, ("c.ts",)), []),
        (Record({}, ("c.ts",)), Record({}, ()), []),
    ],
    ids=[
        "equal",
        "fall",
        "statements-rise",
        "arms-rise",
        "new-file",
        "newly-unmeasured",
        "still-unmeasured",
        "now-measured",
    ],
)
def test_no_files_count_rises_above_the_bases(base: Record, new: Record, said: list[str]) -> None:
    assert ratchet(base, new, renames={}) == said


def test_a_renamed_file_keeps_its_bases_counts() -> None:
    base = Record({"old.py": (2, 0)}, ("old.ts",))
    new = Record({"new.py": (2, 0)}, ("new.ts",))
    assert ratchet(base, new, renames={"old.py": "new.py", "old.ts": "new.ts"}) == []


def test_a_renamed_file_may_not_rise_either() -> None:
    base = Record({"old.py": (2, 0)}, ())
    new = Record({"new.py": (3, 0)}, ())
    assert ratchet(base, new, renames={"old.py": "new.py"}) == [
        "new.py: untested statements would rise from 2 to 3"
    ]


def test_the_renames_are_read_from_a_name_status_listing() -> None:
    listing = "R087\0old.py\0new.py\0M\0a.py\0C100\0x.ts\0y.ts\0D\0gone.py\0"
    assert renames_in(listing) == {"old.py": "new.py"}


def test_a_name_status_listing_that_does_not_parse_is_refused() -> None:
    with pytest.raises(GateError, match="name-status"):
        renames_in("R087\0only-one\0")
