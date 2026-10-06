"""Develop's deploy is the extension zip, its build provenance attested and verified (#220).

Spec §12.1: the Python TestPyPI ``publish-dev`` job is retired, and so is the daily
``yahoo-shape`` schedule, which checks a data source the extension does not use (decision 21).
"""

import shlex
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github/workflows"
# PyYAML reads the bare key `on` as the boolean True, so a key may be a bool.
CI: dict[str | bool, Any] = yaml.safe_load((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))
JOBS: dict[str, dict[str, Any]] = CI["jobs"]
GATED = sorted(name for name, job in JOBS.items() if "environment" not in job)


def deploy() -> dict[str, Any]:
    """The deploy job, looked up per test so its absence fails each test by name."""
    assert "deploy-dev" in JOBS, sorted(JOBS)
    job: dict[str, Any] = JOBS["deploy-dev"]
    return job


def step(name: str) -> dict[str, Any]:
    found: list[dict[str, Any]] = [s for s in deploy()["steps"] if s.get("name") == name]
    assert len(found) == 1, (name, found)
    return found[0]


def test_the_deploy_runs_on_a_push_to_develop_after_every_gated_job() -> None:
    assert deploy()["if"] == "github.event_name == 'push' && github.ref == 'refs/heads/develop'"
    assert sorted(deploy()["needs"]) == GATED
    assert "extension" in GATED


def test_the_deploy_holds_only_the_permissions_an_attestation_needs() -> None:
    assert deploy()["permissions"] == {
        "contents": "read",
        "id-token": "write",
        "attestations": "write",
    }


def test_the_deploy_builds_the_zip_from_a_clean_install() -> None:
    runs = [s.get("run") for s in deploy()["steps"] if s.get("working-directory") == "extension"]
    assert runs == ["npm ci --ignore-scripts", "npm run build"]
    zipped = step("Zip the built extension")
    assert zipped["working-directory"] == "extension/dist"
    assert 'zip -X -r -q "${ZIP}" .' in zipped["run"]


def test_the_zip_is_attested_then_verified_as_this_workflow_on_develop() -> None:
    names = [s.get("name") for s in deploy()["steps"]]
    attest = step("Attest the zip's build provenance")
    assert attest["uses"].startswith("actions/attest@")
    assert attest["with"] == {"subject-path": "${{ steps.zip.outputs.path }}"}
    verify = step("Verify the attestation")
    assert verify["env"]["ZIP"] == "${{ steps.zip.outputs.path }}"
    lines = verify["run"].splitlines()
    assert shlex.split(lines[0]) == [
        "gh",
        "attestation",
        "verify",
        "${ZIP}",
        "--repo",
        "${GITHUB_REPOSITORY}",
        "--signer-workflow",
        "${GITHUB_REPOSITORY}/.github/workflows/ci.yml",
        "--source-ref",
        "refs/heads/develop",
        "--format",
        "json",
        ">",
        "${RUNNER_TEMP}/verified.json",
    ]
    # The verdict names this zip: its own digest is among the subjects verified.
    assert lines[1] == 'read -r digest _ < <(sha256sum "${ZIP}")'
    assert shlex.split(lines[2]) == [
        "jq",
        "-e",
        "--arg",
        "digest",
        "${digest}",
        "any(.[].verificationResult.statement.subject[]; .digest.sha256 == $digest)",
        "${RUNNER_TEMP}/verified.json",
    ]
    assert names.index("Attest the zip's build provenance") < names.index("Verify the attestation")


def test_the_verified_zip_is_kept_as_it_is_not_zipped_again() -> None:
    names = [s.get("name") for s in deploy()["steps"]]
    upload = step("Keep the zip")
    assert upload["uses"].startswith("actions/upload-artifact@")
    assert upload["with"]["archive"] is False
    assert upload["with"]["path"] == "${{ steps.zip.outputs.path }}"
    assert upload["with"]["if-no-files-found"] == "error"
    assert names.index("Verify the attestation") < names.index("Keep the zip")


def test_nothing_publishes_to_testpypi_any_more() -> None:
    texts = {path.name: path.read_text(encoding="utf-8") for path in WORKFLOWS.glob("*.yml")}
    assert len(texts) >= 2
    assert "publish-dev" not in JOBS
    assert [name for name, text in texts.items() if "pypi" in text.lower()] == []


def test_the_yahoo_shape_check_runs_only_by_hand() -> None:
    shape: dict[str | bool, Any] = yaml.safe_load(
        (WORKFLOWS / "yahoo-shape.yml").read_text(encoding="utf-8")
    )
    assert shape[True] == {"workflow_dispatch": None}
