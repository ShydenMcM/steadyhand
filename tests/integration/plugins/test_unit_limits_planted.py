"""The unit limits against real slow tests (#323): planted tests run by pytest in its own process,
with the limits plugin loaded by name. A test that spins past 0.1 s of its own CPU is named and
fails the run; one that only waits passes the CPU check and fails on the 1 s wall limit; a
``perf`` test is another suite and is held to neither; under coverage nothing is judged. The
plugin's logic, with planted records, is unit-tested in ``tests/plugins/test_unit_limits.py``."""

import os
import subprocess
import sys
from pathlib import Path

PLUGINS = Path(__file__).resolve().parents[2] / "plugins"

# One line per statement, as the other planted sources are: the test-per-case guard counts each
# line that opens a test, so a plant's own tests must not open a line here.
PLANTED = (
    "import time\n\nimport pytest\n\n\n"
    "def spin(seconds):\n    end = time.thread_time() + seconds\n"
    "    while time.thread_time() < end:\n        pass\n\n\n"
    "def test_spins():\n    spin(0.25)\n\n\n"
    "def test_waits():\n    time.sleep(1.5)\n\n\n"
    "@pytest.mark.perf\ndef test_perf_spins_and_waits():\n    spin(0.25)\n    time.sleep(1.5)\n\n\n"
    "def test_quick():\n    assert True\n"
)

INI = """[pytest]
markers =
    perf: another suite
"""


def run(folder: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    (folder / "test_planted.py").write_text(PLANTED, encoding="utf-8")
    (folder / "pytest.ini").write_text(INI, encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(PLUGINS)}
    return subprocess.run(  # noqa: S603 - this interpreter, running pytest on the planted tests
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "unit_limits",
            "-p",
            "no:cacheprovider",
            "-rA",
            *extra,
        ],
        cwd=folder,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def outcomes(output: str) -> dict[str, str]:
    """Each planted test's outcome from pytest's short summary (``-rA``)."""
    found: dict[str, str] = {}
    for line in output.splitlines():
        word, _, rest = line.partition(" ")
        if word in {"PASSED", "FAILED"} and rest.startswith("test_planted.py::"):
            found[rest.split("::")[1].split(" ")[0]] = word
    return found


def test_a_spinning_test_is_named_and_a_waiting_one_fails_on_the_wall(tmp_path: Path) -> None:
    result = run(tmp_path)
    assert result.returncode == 1, result.stdout
    assert outcomes(result.stdout) == {
        "test_spins": "PASSED",
        "test_waits": "FAILED",
        "test_perf_spins_and_waits": "PASSED",
        "test_quick": "PASSED",
    }
    assert "Timeout (>1.0s) from pytest-timeout." in result.stdout
    named = [line for line in result.stdout.splitlines() if line.startswith("CPU LIMIT: ")]
    assert len(named) == 1, result.stdout
    assert named[0].startswith("CPU LIMIT: test_planted.py::test_spins took ")
    assert "own CPU and wall per unit test (limits 100000 us of CPU, 1 s of wall), 3 tests" in (
        result.stdout
    )


def test_under_coverage_nothing_is_judged(tmp_path: Path) -> None:
    result = run(tmp_path, "--cov", "--cov-report=")
    assert result.returncode == 0, result.stdout
    assert set(outcomes(result.stdout).values()) == {"PASSED"}
    assert len(outcomes(result.stdout)) == 4
    assert "CPU LIMIT: " not in result.stdout
    assert "coverage traced this run, so no test is judged" in result.stdout
