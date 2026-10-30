"""steadyhand runs the versions every project runs, each pinned in one place (#382).

Shyden's rule (2026-10-21, every project): the same version of everything the projects share,
the newest any of them runs. On 2026-10-26 he ruled steadyhand runs exactly Python 3.13.15 and
nothing else. What git does not pin, this guard pins:

- every workflow job runs on ``ubuntu-26.04``, the newest runner image any project uses;
- no step runs Python except through ``uv run``, after ``astral-sh/setup-uv``, so no step runs
  the runner image's own ``python3``, which changes with the image;
- the one Python pin is ``.python-version``, an exact patch version. uv reads it, so no workflow
  names a Python, and every minor version a workflow, a package or a tool names must match it.

To move Python: write the new exact version in ``.python-version`` and in
``test_python_is_pinned_once_to_an_exact_patch_version`` below, then run this file in CI; each
place still naming the old minor (``requires-python``, ruff's ``target-version``, mypy's
``python_version``, the ``(pyX.Y)`` job names) is listed by name. Those job names are required
checks, so the old names are swapped in branch protection, which is Shyden's click. The readers
are in ``workflow_versions.py``, their plants in ``tests/guard_helpers/test_workflow_versions.py``.
"""

import tomllib
from pathlib import Path
from typing import Any

import pytest
import yaml
from tracked_files import tracked
from workflow_versions import (
    NAMED_MINOR,
    SETUP_UV,
    exact_version,
    pyproject_findings,
    python_version_keys,
    runner_findings,
    step_findings,
    strings,
)

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"

# Measured on 2026-10-30 (#446 removed two workflows and a job): 13 jobs in 2 workflow files, 12 of
# them setting up uv, 4 job names carrying a Python minor, 3 pyproject files. Lower each only by a
# deliberate edit when the workflows or packages shrink.
JOBS_FLOOR = 13
SETUP_UV_FLOOR = 12
NAMED_MINORS_FLOOR = 4
PYPROJECTS_FLOOR = 3


def workflow_files() -> list[Path]:
    """Every workflow git lists, in either spelling GitHub reads."""
    return sorted([*tracked(WORKFLOWS, ".yml"), *tracked(WORKFLOWS, ".yaml")])


def load(path: Path) -> dict[Any, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), path
    return loaded


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


FILES = workflow_files()


def pinned() -> tuple[int, int, int]:
    return exact_version((ROOT / ".python-version").read_text(encoding="utf-8"))


def test_every_workflow_git_lists_is_read() -> None:
    on_disk = [*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")]
    assert [relative(path) for path in FILES] == sorted(relative(path) for path in on_disk)
    jobs = sum(len(load(path)["jobs"]) for path in FILES)
    assert jobs >= JOBS_FLOOR, f"read {jobs} jobs"


@pytest.mark.parametrize("path", FILES, ids=[relative(path) for path in FILES])
def test_every_job_runs_on_the_one_runner_image(path: Path) -> None:
    workflow = load(path)
    assert runner_findings(workflow) == []


@pytest.mark.parametrize("path", FILES, ids=[relative(path) for path in FILES])
def test_no_step_runs_python_outside_the_pinned_one(path: Path) -> None:
    workflow = load(path)
    assert step_findings(workflow) == []


def test_python_is_pinned_once_to_an_exact_patch_version() -> None:
    assert pinned() == (3, 13, 15)


def test_no_workflow_names_a_python_for_an_action() -> None:
    """uv reads ``.python-version``; a ``python-version`` beside it would be a second pin."""
    loaded = {relative(path): load(path) for path in FILES}
    set_up = [
        step
        for workflow in loaded.values()
        for job in workflow["jobs"].values()
        for step in job.get("steps", [])
        if str(step.get("uses", "")).lower().startswith(SETUP_UV)
    ]
    keys = [f"{name}{key}" for name, wf in loaded.items() for key in python_version_keys(wf)]
    assert keys == []
    assert len(set_up) >= SETUP_UV_FLOOR, f"read {len(set_up)} setup-uv steps"


def test_every_minor_a_workflow_names_is_the_pinned_one() -> None:
    major, minor, _ = pinned()
    named = [
        found
        for path in FILES
        for text in strings(load(path))
        for found in NAMED_MINOR.findall(text)
    ]
    wrong = [found for found in named if found != f"{major}.{minor}"]
    assert wrong == []
    assert len(named) >= NAMED_MINORS_FLOOR, f"read {len(named)} named minors"


def test_every_package_and_tool_names_the_pinned_minor() -> None:
    major, minor, _ = pinned()
    files = tracked(ROOT, "pyproject.toml")
    found = [
        finding
        for path in files
        for finding in pyproject_findings(
            relative(path), tomllib.loads(path.read_text(encoding="utf-8")), major, minor
        )
    ]
    assert found == []
    assert len(files) >= PYPROJECTS_FLOOR, f"read {len(files)} pyproject files"
