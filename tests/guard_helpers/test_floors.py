"""The Python reader of the recorded floors (#272), driven with floors files written per test.

No test here writes ``extension/tests/floors.json``: every floor in both languages reads it, from
parallel workers, and a write truncates first (the global floor rules, shyden.co.uk #593).
"""

import json
from pathlib import Path

import pytest
from floors import FLOORS_PATH, RECORD_ADVICE, RECORD_ENV, floor_breach, parse_floors
from population import ROOT

IN_THE_RECORDER = {"GITHUB_WORKFLOW": "record-floors"}
A_TEST = "tests/guards/test_x.py::test_y[a b]"


def floors_file(tmp_path: Path, floors: object) -> Path:
    path = tmp_path / "floors.json"
    path.write_text(json.dumps(floors), encoding="utf-8")
    return path


def test_the_floors_are_the_extension_s_recorded_file() -> None:
    # One file for both languages, so one recorder covers both (AC2).
    assert FLOORS_PATH == ROOT / "extension" / "tests" / "floors.json"


def test_the_record_switch_is_the_one_the_typescript_floors_read() -> None:
    assert RECORD_ENV == "STEADYHAND_FLOORS_RECORD"


def test_the_advice_is_the_one_the_typescript_floors_give() -> None:
    assert (
        RECORD_ADVICE == "label the pull request record-floors, then npm run floors:fetch <run id>"
    )


def test_a_floor_reads_the_recorded_file_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # Out of record mode even inside the recorder, so this test never records a floor of its own.
    monkeypatch.delenv(RECORD_ENV, raising=False)
    assert floor_breach("no.such.floor", 1) == (
        "floor no.such.floor: none recorded, measured 1; " + RECORD_ADVICE
    )


def test_a_floor_reads_the_process_environment_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(RECORD_ENV, str(tmp_path / "m.jsonl"))
    monkeypatch.delenv("GITHUB_WORKFLOW", raising=False)
    with pytest.raises(RuntimeError, match=r"^floors are recorded only by the record-floors"):
        floor_breach("g.files", 9)
    assert not (tmp_path / "m.jsonl").exists()


def test_a_measurement_equal_to_its_record_is_no_breach(tmp_path: Path) -> None:
    assert floor_breach("g.files", 7, {}, floors_file(tmp_path, {"g.files": 7})) is None


def test_growth_is_a_breach_until_it_is_recorded(tmp_path: Path) -> None:
    assert floor_breach("g.files", 9, {}, floors_file(tmp_path, {"g.files": 7})) == (
        "floor g.files: measured 9, recorded 7 (+2); read the growth against the diff, then "
        + RECORD_ADVICE
    )


def test_a_loss_is_a_breach_that_names_a_blind_reader(tmp_path: Path) -> None:
    assert floor_breach("g.files", 4, {}, floors_file(tmp_path, {"g.files": 7})) == (
        "floor g.files: measured 4, recorded 7 (-3); a reader may have gone blind to part of its "
        "population. If it really shrank, lower the figure in extension/tests/floors.json by a "
        "deliberate edit"
    )


def test_a_floor_with_no_record_is_a_breach(tmp_path: Path) -> None:
    assert floor_breach("g.new", 3, {}, floors_file(tmp_path, {"g.files": 7})) == (
        "floor g.new: none recorded, measured 3; " + RECORD_ADVICE
    )


def test_a_floor_of_zero_is_judged_like_any_other(tmp_path: Path) -> None:
    # A deliberately empty fixture takes a floor of 0, so a case quietly added to it is seen.
    assert floor_breach("g.empty", 1, {}, floors_file(tmp_path, {"g.empty": 0})) == (
        "floor g.empty: measured 1, recorded 0 (+1); read the growth against the diff, then "
        + RECORD_ADVICE
    )


def test_recording_appends_the_measurement_with_the_test_that_asserted_it(tmp_path: Path) -> None:
    measurements = tmp_path / "measurements.jsonl"
    measurements.write_text('{"id": "earlier", "measured": 1, "test": "t"}\n', encoding="utf-8")
    env = {
        **IN_THE_RECORDER,
        RECORD_ENV: str(measurements),
        "PYTEST_CURRENT_TEST": f"{A_TEST} (call)",
    }
    assert floor_breach("g.files", 9, env, tmp_path / "no-floors-read.json") is None
    lines = measurements.read_text(encoding="utf-8").splitlines()
    assert [json.loads(line) for line in lines] == [
        {"id": "earlier", "measured": 1, "test": "t"},
        {"id": "g.files", "measured": 9, "test": A_TEST},
    ]


def test_recording_outside_the_recorder_workflow_is_refused(tmp_path: Path) -> None:
    env = {RECORD_ENV: str(tmp_path / "m.jsonl"), "PYTEST_CURRENT_TEST": f"{A_TEST} (call)"}
    with pytest.raises(
        RuntimeError, match=r"^floors are recorded only by the record-floors workflow"
    ):
        floor_breach("g.files", 9, env)
    assert not (tmp_path / "m.jsonl").exists()


@pytest.mark.parametrize("phase", ["setup", "teardown"])
def test_recording_outside_a_test_body_is_refused(tmp_path: Path, phase: str) -> None:
    env = {
        **IN_THE_RECORDER,
        RECORD_ENV: str(tmp_path / "m.jsonl"),
        "PYTEST_CURRENT_TEST": f"{A_TEST} ({phase})",
    }
    with pytest.raises(
        RuntimeError, match=rf"^a floor is asserted inside a test body, not its {phase}"
    ):
        floor_breach("g.files", 9, env)
    assert not (tmp_path / "m.jsonl").exists()


def test_recording_outside_pytest_is_refused(tmp_path: Path) -> None:
    env = {**IN_THE_RECORDER, RECORD_ENV: str(tmp_path / "m.jsonl")}
    with pytest.raises(RuntimeError, match=r"^a floor is asserted inside a test, so the recorder"):
        floor_breach("g.files", 9, env)
    assert not (tmp_path / "m.jsonl").exists()


def test_floors_are_whole_numbers_by_id() -> None:
    assert parse_floors('{"a.b": 0, "c.d": 12}') == {"a.b": 0, "c.d": 12}


@pytest.mark.parametrize(
    ("figure", "shown"),
    [(-1, "-1"), (1.5, "1.5"), (True, "true"), ("3", '"3"'), (None, "null")],
    ids=["negative", "fraction", "boolean", "text", "null"],
)
def test_a_figure_that_is_not_a_whole_number_is_refused_by_id(figure: object, shown: str) -> None:
    with pytest.raises(
        ValueError, match=rf"^floor a\.b: {shown} is not a whole number of zero or more$"
    ):
        parse_floors(json.dumps({"a.b": figure}))


@pytest.mark.parametrize("text", ["[]", "3", "null"], ids=["list", "number", "null"])
def test_a_floors_file_that_is_not_an_object_is_refused(text: str) -> None:
    with pytest.raises(ValueError, match=r"^the floors file is not an object of floor ids$"):
        parse_floors(text)
