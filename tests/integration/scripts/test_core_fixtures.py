"""The files core reads from Python are current (#223): scripts/core_fixtures.py, run again, writes
every committed rule JSON and the ratio fixture byte for byte. Its real run reads every rule file
through Python's readers (too much for a unit test)."""

from pathlib import Path

import core_fixtures
import pytest

OUTPUTS = core_fixtures.outputs()


@pytest.mark.parametrize("path", sorted(OUTPUTS), ids=str)
def test_the_committed_file_is_what_the_script_writes(path: Path) -> None:
    committed = (core_fixtures.ROOT / path).read_text(encoding="utf-8")
    assert committed == OUTPUTS[path], (
        f"run: uv run --locked python scripts/core_fixtures.py ({path})"
    )


def test_the_script_writes_every_file_under_the_root_it_is_given(tmp_path: Path) -> None:
    core_fixtures.main(["--root", str(tmp_path)])
    written = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert written == sorted(OUTPUTS)
    assert [(tmp_path / path).read_text(encoding="utf-8") for path in written] == [
        OUTPUTS[path] for path in written
    ]
