"""A test run removes its temporary folders when it ends, pass or fail (#602).

pytest keeps every ``tmp_path`` folder of the last three runs by default, so the golden, CLI and
paper tests would leave their caches and home folders in the system temp folder.
"""

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pytest_removes_every_tmp_path_folder_when_the_run_ends() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    options = pyproject["tool"]["pytest"]["ini_options"]
    assert options.get("tmp_path_retention_policy") == "none"
