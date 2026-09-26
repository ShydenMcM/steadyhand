"""Supply-chain rules (spec §10.1): pinned actions and a complete, develop-targeted Dependabot.

YAML is parsed, so a comment can never satisfy a rule. The one rule that is about comments
(the ``# vX.Y.Z`` after each pin) reads raw lines, and it cross-checks those lines against the
parsed values so that no ``uses`` can hide from it.
"""

import re
import shlex
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"

PINNED = re.compile(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}")
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<value>\S+)(?P<tail>.*)$")
VERSION_COMMENT = re.compile(r"\s+# v\d+\.\d+\.\d+\s*")
SUB_PATH_PATTERN = re.compile(r"[\w.-]+/[\w.-]+\*")


def workflow_files() -> list[Path]:
    return sorted([*WORKFLOWS.glob("*.yml"), *WORKFLOWS.glob("*.yaml")])


def uses_values(node: Any) -> Iterator[str]:  # noqa: ANN401 - parsed YAML is untyped
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield value
            else:
                yield from uses_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from uses_values(item)


def dependabot() -> dict[str, Any]:
    loaded = yaml.safe_load(DEPENDABOT.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def ecosystems_present() -> set[str]:
    present: set[str] = set()
    if (ROOT / "uv.lock").is_file():
        present.add("uv")
    if workflow_files():
        present.add("github-actions")
    return present


def test_every_action_is_pinned_to_a_full_commit_sha() -> None:
    values = [
        value
        for path in workflow_files()
        for value in uses_values(yaml.safe_load(path.read_text(encoding="utf-8")))
    ]
    assert len(values) >= 8, values  # four CI jobs, each with checkout and setup-uv
    unpinned = [v for v in values if not v.startswith("./") and PINNED.fullmatch(v) is None]
    assert unpinned == []


def test_every_pin_carries_its_release_version_as_a_comment() -> None:
    parsed: list[str] = []
    raw: list[tuple[str, str]] = []
    for path in workflow_files():
        text = path.read_text(encoding="utf-8")
        parsed.extend(uses_values(yaml.safe_load(text)))
        for line in text.splitlines():
            match = USES_LINE.match(line)
            if match is not None:
                raw.append((match["value"], match["tail"]))
    assert len(parsed) >= 8, parsed
    # Every parsed `uses` was seen on a line of its own, so none escapes the comment check.
    assert sorted(value for value, _ in raw) == sorted(parsed)
    missing = [
        value
        for value, tail in raw
        if not value.startswith("./") and VERSION_COMMENT.fullmatch(tail) is None
    ]
    assert missing == []


def test_dependabot_covers_every_ecosystem_in_the_repo() -> None:
    present = ecosystems_present()
    assert present == {"uv", "github-actions"}
    configured = {update["package-ecosystem"] for update in dependabot()["updates"]}
    assert present <= configured


def test_every_dependabot_update_targets_develop_weekly() -> None:
    updates = dependabot()["updates"]
    assert len(updates) >= 2
    wrong = [
        (u["package-ecosystem"], u.get("target-branch"), u.get("schedule", {}).get("interval"))
        for u in updates
        if u.get("target-branch") != "develop" or u.get("schedule", {}).get("interval") != "weekly"
    ]
    assert wrong == []


def test_sub_path_actions_are_grouped_above_the_patch_group() -> None:
    actions = next(u for u in dependabot()["updates"] if u["package-ecosystem"] == "github-actions")
    groups: dict[str, dict[str, Any]] = actions["groups"]
    names = list(groups)
    sub_path = [
        name
        for name in names
        if any(SUB_PATH_PATTERN.fullmatch(p) for p in groups[name].get("patterns", []))
    ]
    patch = [name for name in names if "patch" in groups[name].get("update-types", [])]
    assert sub_path, "no group gathers the sub-paths of one action repo"
    assert patch, "no patch group"
    # Dependabot puts an update in the first group that matches, so order matters.
    assert names.index(sub_path[0]) < names.index(patch[0])


INDEX_FLAGS = ("--index", "--default-index", "--index-url", "--extra-index-url", "-i")


def shell_words(script: str) -> list[str]:
    """A ``run`` script as the shell splits it: continuations joined, ``--flag=value`` split."""
    words = shlex.split(script.replace("\\\n", " "))
    return [part for word in words for part in (word.split("=", 1) if word[:2] == "--" else [word])]


def index_flags(words: list[str]) -> list[tuple[str, str]]:
    return [(flag, value) for flag, value in pairwise(words) if flag in INDEX_FLAGS]


def test_the_testpypi_check_takes_every_dependency_from_pypi_first() -> None:
    """Anyone can upload to TestPyPI, and a ``yfinance`` that is not the real one lives there.

    PyPI is searched first, so a name PyPI carries never comes from TestPyPI; only steadyhand's
    own dev builds, which PyPI does not have, fall through to it (#57). No strategy flag may
    widen that to a best-match across both indexes.
    """
    ci = yaml.safe_load((WORKFLOWS / "ci.yml").read_text())
    steps = [
        step
        for step in ci["jobs"]["publish-dev"]["steps"]
        if step.get("name") == "Verify both packages install from TestPyPI"
    ]
    assert len(steps) == 1, steps
    scopes = (ci, ci["jobs"]["publish-dev"], steps[0])
    # UV_INDEX, UV_DEFAULT_INDEX, UV_INDEX_STRATEGY, PIP_INDEX_URL...: all spell INDEX.
    assert [name for scope in scopes for name in scope.get("env", {}) if "INDEX" in name] == []
    words = shell_words(steps[0]["run"])
    assert index_flags(words) == [
        ("--index", "https://pypi.org/simple/"),
        ("--default-index", "https://test.pypi.org/simple/"),
    ]
    assert "--index-strategy" not in words
