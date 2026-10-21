"""The CLI seed rebuilt by its recorder from the recorded data equals the committed one (#374):
the recorder's real run (0.3 s of CPU, too much for a unit test), and a check that the seed the
CLI tests start from is still what the recorder makes."""

from pathlib import Path

import record_cli_seed


def test_the_recorder_rebuilds_the_committed_seed_byte_for_byte(tmp_path: Path) -> None:
    rebuilt = record_cli_seed.record(tmp_path / "cli-seed.sql")
    assert rebuilt.read_text(encoding="utf-8") == record_cli_seed.SEED.read_text(encoding="utf-8")
