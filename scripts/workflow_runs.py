"""The hand-started workflows a pull request changes, read from their runs on its commit (#384).

Shyden's rulings of 2026-10-22: workflow code that never runs on a pull request is run on the pull
request's commit ("Run them on the PR commit"), started on a scratch branch ("Scratch branch"):
GitHub refuses to start a workflow on a ``refs/floors/*`` ref, and a push to ``coverage/<branch>``
starts no CI, since ci.yml runs on pushes to develop and main only. So, before the pull request is
pushed, its commit goes to that branch, each hand-started workflow it changes is started there and
waited for. CI's coverage job then reads each changed workflow (other than ci.yml, which its own
run measures) from those runs, and fails naming the commands when one is missing.

Usage: workflow_runs.py --event NAME --repo OWNER/NAME --branch coverage/<branch> --sha HEAD
       --out DIR
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from run_tool import ToolError, run_tool
from workflow_coverage import (
    RunError,
    TraceError,
    WorkflowError,
    judge,
    layout,
    require_traced,
    results_from,
    traces_in,
)

WORKFLOWS = ".github/workflows/"
OWN = ".github/workflows/ci.yml"


class RunsError(Exception):
    """A changed workflow that cannot be read from a run on the commit."""


def changed_workflows(repo: Path) -> list[str]:
    """The workflows other than ci.yml the pull request's merge commit adds or changes."""
    span = ("--diff-filter=d", "-z", "HEAD^1", "HEAD", "--", WORKFLOWS)
    raw = run_tool(repo, "git", "diff", "--name-only", *span)
    names = [name for name in raw.decode("utf-8").split("\0") if name]
    return [name for name in names if name != OWN and name.endswith((".yml", ".yaml"))]


def _json(raw: bytes) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(raw)
    return loaded


def _runs(repo: Path, slug: str, workflow: str, branch: str, sha: str) -> list[int]:
    name = Path(workflow).name
    query = f"branch={branch}&head_sha={sha}&status=completed&per_page=100"
    listing = _json(
        run_tool(repo, "gh", "api", f"repos/{slug}/actions/workflows/{name}/runs?{query}")
    )
    runs = listing["workflow_runs"]
    if listing["total_count"] != len(runs):
        counted = listing["total_count"]
        msg = f"the listing of {workflow} counts {counted} runs but {len(runs)} were read"
        raise RunsError(msg)
    if not runs:
        msg = (
            f"{workflow} changed, but there is no completed run of {workflow} on {branch} at {sha}."
            f" Push the commit and start it, then wait for it:\n"
            f"  git push origin HEAD:refs/heads/{branch}\n"
            f"  gh workflow run {name} --ref {branch}"
        )
        raise RunsError(msg)
    return sorted(int(run["id"]) for run in runs)


def _report(repo: Path, slug: str, workflow: str, branch: str, sha: str) -> dict[str, Any]:
    text = (repo / workflow).read_text(encoding="utf-8")
    own = run_tool(repo, "git", "show", f"{sha}:{workflow}").decode("utf-8")
    if own != text:
        msg = f"{workflow} on the merge commit differs from the pull request's own at {sha}"
        raise RunsError(msg)
    require_traced(text)
    flow = layout(text)
    run_ids = _runs(repo, slug, workflow, branch, sha)
    executed: set[int] = set()
    judged: set[int] = set()
    with tempfile.TemporaryDirectory() as scratch:
        for run_id in run_ids:
            jobs_path = f"repos/{slug}/actions/runs/{run_id}/jobs?per_page=100"
            jobs = results_from(_json(run_tool(repo, "gh", "api", jobs_path)))
            target = Path(scratch) / str(run_id)
            pattern = ("--pattern", "workflow-trace-*", "--dir", str(target))
            run_tool(repo, "gh", "run", "download", str(run_id), "--repo", slug, *pattern)
            verdict = judge(flow, jobs, traces_in([target]), sha)
            executed.update(verdict.executed)
            judged.update(verdict.executed, verdict.missing)
    return {
        "meta": {"sha": sha, "workflow": workflow, "runs": run_ids},
        "files": {
            workflow: {
                "executed_lines": sorted(executed),
                "missing_lines": sorted(judged - executed),
            }
        },
    }


def main(argv: Sequence[str], repo: Path) -> int:
    parser = argparse.ArgumentParser(prog="workflow_runs.py")
    parser.add_argument("--event", required=True)
    parser.add_argument("--repo", required=True, dest="slug")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.event != "pull_request":
        print(f"{args.event}: no pull request, so no hand-started workflow to read")
        return 0
    try:
        for workflow in changed_workflows(repo):
            report = _report(repo, args.slug, workflow, args.branch, args.sha)
            args.out.mkdir(parents=True, exist_ok=True)
            path = args.out / f"{Path(workflow).stem}.json"
            path.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
            lines = report["files"][workflow]
            print(f"{workflow}: runs {report['meta']['runs']}; unrun: {lines['missing_lines']}")
    except (RunsError, ToolError, WorkflowError, TraceError, RunError) as error:
        print(f"workflow runs: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:], Path.cwd()))
