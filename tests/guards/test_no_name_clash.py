"""No workflow job reports a required check's name on a run that is not a pull request's (#444).

Branch protection matches a required check by name, and a run started by hand on
``coverage/<branch>`` runs on the pull request's head: under a pull-request job's name it stands
beside the pull request's own run (PR #415's head carried two ``mutations`` checks). The reader is
``check_names.py``; ``tests/guard_helpers/test_check_names.py`` plants every form it must find.
"""

from check_names import clashes
from ci_workflow import parse
from population import ROOT, searched, tracked

WORKFLOWS = ROOT / ".github/workflows"


def workflow_files() -> list[str]:
    found = [*tracked(WORKFLOWS, ".yml"), *tracked(WORKFLOWS, ".yaml")]
    return sorted(path.relative_to(ROOT).as_posix() for path in found)


def test_every_workflow_file_on_disk_is_one_the_guard_reads() -> None:
    """The walk, checked against the folder itself, so a narrowed listing cannot pass unseen."""
    on_disk = sorted(
        path.relative_to(ROOT).as_posix()
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )
    assert workflow_files() == on_disk


def test_no_job_reports_a_pull_request_name_on_any_other_event() -> None:
    names = workflow_files()
    workflows = {name: parse((ROOT / name).read_text(encoding="utf-8")) for name in names}
    assert searched(clashes(workflows), of=len(workflows), what="workflow files") == []
