"""Supply-chain rules (spec §10.1): pinned actions and a complete, develop-targeted Dependabot.

YAML is parsed, so a comment can never satisfy a rule. The one rule that is about comments
(the ``# vX.Y.Z`` after each pin) reads raw lines, and it cross-checks those lines against the
parsed values so that no ``uses`` can hide from it.
"""

import json
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from population import searched, tracked

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
DEPENDABOT = ROOT / ".github" / "dependabot.yml"

PINNED = re.compile(r"[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}")
USES_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(?P<value>\S+)(?P<tail>.*)$")
VERSION_COMMENT = re.compile(r"\s+# v\d+\.\d+\.\d+\s*")
SUB_PATH_PATTERN = re.compile(r"[\w.-]+/[\w.-]+\*")

# Measured on 2026-10-03 (#178): 13 `uses` in 2 workflow files. Lower it only by a deliberate edit
# when the workflows shrink.
USES_FLOOR = 12


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


def npm_locks() -> list[Path]:
    """Every npm lock file git lists, outside node_modules (#220)."""
    return [path for path in tracked(ROOT, "package-lock.json") if "node_modules" not in path.parts]


def ecosystems_present() -> set[str]:
    present: set[str] = set()
    if (ROOT / "uv.lock").is_file():
        present.add("uv")
    if workflow_files():
        present.add("github-actions")
    if npm_locks():
        present.add("npm")
    return present


def update_for(ecosystem: str, directory: str) -> dict[str, Any]:
    found = [
        update
        for update in dependabot()["updates"]
        if update["package-ecosystem"] == ecosystem and update["directory"] == directory
    ]
    assert len(found) == 1, (ecosystem, directory, found)
    update: dict[str, Any] = found[0]
    return update


def test_the_workflows_read_are_the_ones_git_lists() -> None:
    # Independent of the walk: the workflow files as git lists them.
    listed = sorted([*tracked(WORKFLOWS, ".yml"), *tracked(WORKFLOWS, ".yaml")])
    assert workflow_files() == listed
    assert len(listed) >= 1


def test_every_action_is_pinned_to_a_full_commit_sha() -> None:
    values = [
        value
        for path in workflow_files()
        for value in uses_values(yaml.safe_load(path.read_text(encoding="utf-8")))
    ]
    assert len(values) >= USES_FLOOR, values
    unpinned = [v for v in values if not v.startswith("./") and PINNED.fullmatch(v) is None]
    assert searched(unpinned, of=len(values), what="uses") == []


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
    assert len(parsed) >= USES_FLOOR, parsed
    # Every parsed `uses` was seen on a line of its own, so none escapes the comment check.
    assert sorted(value for value, _ in raw) == sorted(parsed)
    missing = [
        value
        for value, tail in raw
        if not value.startswith("./") and VERSION_COMMENT.fullmatch(tail) is None
    ]
    assert searched(missing, of=len(raw), what="uses lines") == []


def test_dependabot_covers_every_ecosystem_in_the_repo() -> None:
    present = ecosystems_present()
    assert present == {"uv", "github-actions", "npm"}
    configured = {update["package-ecosystem"] for update in dependabot()["updates"]}
    assert present <= configured


def test_the_npm_locks_are_the_extension_workspace_alone() -> None:
    assert [path.relative_to(ROOT).as_posix() for path in npm_locks()] == [
        "extension/package-lock.json"
    ]


@pytest.mark.parametrize("lock", npm_locks(), ids=lambda path: path.relative_to(ROOT).as_posix())
def test_every_npm_lock_has_its_own_dependabot_update(lock: Path) -> None:
    update = update_for("npm", f"/{lock.parent.relative_to(ROOT).as_posix()}")
    assert update["target-branch"] == "develop"


def exact_peers(lock: Path) -> list[tuple[str, str]]:
    """Each pair of direct dependencies where one's peer range is the other's exact version, as
    the lock records it: a Dependabot PR moving one alone cannot install (#220)."""
    packages: dict[str, dict[str, Any]] = json.loads(lock.read_text(encoding="utf-8"))["packages"]
    direct = {
        name
        for path, entry in packages.items()
        if not path.startswith("node_modules/")
        for field in ("dependencies", "devDependencies")
        for name in entry.get(field, {})
        if not name.startswith("@steadyhand/")
    }
    return sorted(
        (name, peer)
        for name in direct
        for peer, spec in packages[f"node_modules/{name}"].get("peerDependencies", {}).items()
        if peer in direct and re.fullmatch(r"\d+\.\d+\.\d+", spec)
    )


GROUP_KEYS = frozenset({"patterns", "exclude-patterns", "update-types"})


def wildcard_match(pattern: str, name: str) -> bool:
    """Dependabot's ``WildcardMatcher``: ``*`` is any run of characters, and case is ignored."""
    regex = ".*".join(re.escape(part) for part in pattern.lower().split("*"))
    return re.fullmatch(regex, name.lower()) is not None


def holders(name: str, groups: dict[str, dict[str, Any]]) -> list[str]:
    """Every group that can hold *name*, read as dependabot-core's ``DependencyGroup#contains?``.

    A group with no patterns holds every name it does not exclude. When more than one group holds a
    name, Dependabot scores them, and a group with no patterns outranks any wildcard pattern (#349),
    so the order of the groups does not decide where a package goes.
    """
    found: list[str] = []
    for group, spec in groups.items():
        unmodelled = sorted(set(spec) - GROUP_KEYS)
        assert not unmodelled, f"group {group} sets {unmodelled}, which holders() does not model"
        if any(wildcard_match(pattern, name) for pattern in spec.get("exclude-patterns", [])):
            continue
        if "patterns" not in spec or any(wildcard_match(p, name) for p in spec["patterns"]):
            found.append(group)
    return found


@pytest.mark.parametrize(
    ("name", "groups", "held"),
    [
        (
            "@vitest/x",
            {"v": {"patterns": ["@vitest/*"]}, "all": {"update-types": ["patch"]}},
            ["v", "all"],
        ),
        (
            "@vitest/x",
            {"v": {"patterns": ["@vitest/*"]}, "all": {"exclude-patterns": ["@vitest/*"]}},
            ["v"],
        ),
        ("Vitest", {"v": {"patterns": ["vitest"]}}, ["v"]),
        ("vitest-x", {"v": {"patterns": ["vitest"]}}, []),
        ("axb", {"v": {"patterns": ["a.b"]}}, []),
    ],
    ids=[
        "no-patterns-holds-all",
        "exclusion-drops",
        "case-ignored",
        "exact-is-exact",
        "dot-is-literal",
    ],
)
def test_holders_reads_groups_as_dependabot_does(
    name: str, groups: dict[str, dict[str, Any]], held: list[str]
) -> None:
    assert holders(name, groups) == held


def test_holders_refuses_a_group_rule_it_does_not_model() -> None:
    with pytest.raises(AssertionError, match=r"group dev sets \['dependency-type'\]"):
        holders("vitest", {"dev": {"dependency-type": "development"}})


NPM_LOCK = ROOT / "extension/package-lock.json"


def test_the_exact_peer_pairs_are_the_ones_measured() -> None:
    # Measured on 2026-10-06 (#220): vitest and @vitest/coverage-v8 each pin the other.
    assert exact_peers(NPM_LOCK) == [
        ("@vitest/coverage-v8", "vitest"),
        ("vitest", "@vitest/coverage-v8"),
    ]


@pytest.mark.parametrize(("name", "peer"), exact_peers(NPM_LOCK))
def test_packages_pinned_to_each_other_move_in_one_group(name: str, peer: str) -> None:
    groups: dict[str, dict[str, Any]] = update_for("npm", "/extension")["groups"]
    # Held by one group alone, Dependabot's group scoring has nowhere else to put it (#349).
    held = holders(name, groups)
    assert len(held) == 1, f"{name} can go to {held}, so it can move without {peer}"
    assert holders(peer, groups) == held


def pattern_groups() -> list[tuple[str, str, str]]:
    """``(ecosystem, directory, group)`` for every Dependabot group that names its packages."""
    return [
        (update["package-ecosystem"], update["directory"], name)
        for update in dependabot()["updates"]
        for name, spec in update.get("groups", {}).items()
        if "patterns" in spec
    ]


def test_the_pattern_groups_are_the_ones_measured() -> None:
    # Read from dependabot.yml on 2026-10-20 (#349).
    assert pattern_groups() == [
        ("github-actions", "/", "actions-cache"),
        ("npm", "/extension", "vitest"),
    ]


@pytest.mark.parametrize(("ecosystem", "directory", "group"), pattern_groups())
def test_no_group_without_patterns_can_take_a_pattern_groups_packages(
    ecosystem: str, directory: str, group: str
) -> None:
    groups: dict[str, dict[str, Any]] = update_for(ecosystem, directory)["groups"]
    patterns = set(groups[group]["patterns"])
    # A group with no patterns outranks every wildcard in Dependabot's scoring (#349), so it
    # excludes the pattern group's packages by the very same patterns.
    takers = [
        name
        for name, spec in groups.items()
        if "patterns" not in spec and not patterns <= set(spec.get("exclude-patterns", []))
    ]
    assert takers == []


def test_every_dependabot_update_targets_develop_weekly() -> None:
    updates = dependabot()["updates"]
    assert len(updates) >= 3
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
    # Above the patch group, as the global rule asks. The order alone does not keep the sub-paths
    # out of the patch group; its exclusion does (#349).
    assert names.index(sub_path[0]) < names.index(patch[0])


SETUP_NODE = "actions/setup-node@"
PACKAGE_JSON = ROOT / "extension/package.json"
MAJOR = re.compile(r"(?P<major>\d+)(?:\.[\dx]+)*")


def major_of(version: object, *, where: str) -> int:
    """The major version in *version*; ``lts/*``, a range or none is refused by name."""
    found = MAJOR.fullmatch(version) if isinstance(version, str) else None
    if found is None:
        msg = f"{where}: cannot read a major version from {version!r}"
        raise AssertionError(msg)
    return int(found["major"])


def setup_node_versions() -> list[tuple[str, object]]:
    """``(where, node-version)`` for each ``actions/setup-node`` step of each job (#270)."""
    versions: list[tuple[str, object]] = []
    for path in workflow_files():
        jobs = yaml.safe_load(path.read_text(encoding="utf-8")).get("jobs", {})
        for job_name, job in jobs.items():
            for step in job.get("steps", []):
                if str(step.get("uses", "")).startswith(SETUP_NODE):
                    where = f"{path.name} job {job_name}"
                    versions.append((where, step.get("with", {}).get("node-version")))
    return versions


def test_every_setup_node_step_names_its_node_version() -> None:
    # Counted another way: every `uses` anywhere in the workflows, so a step the job walk missed
    # (a reusable workflow, a new nesting) makes the two counts differ.
    uses = [
        value
        for path in workflow_files()
        for value in uses_values(yaml.safe_load(path.read_text(encoding="utf-8")))
        if value.startswith(SETUP_NODE)
    ]
    versions = setup_node_versions()
    assert len(versions) == len(uses), (versions, uses)
    unnamed = [where for where, version in versions if version is None]
    assert searched(unnamed, of=len(versions), what="setup-node steps") == []


def test_types_node_follows_the_node_that_ci_runs() -> None:
    # Types for a newer Node than CI runs let tsc accept an API that then fails on CI (#268).
    pinned = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))["devDependencies"]["@types/node"]
    types_major = major_of(pinned, where="@types/node")
    versions = setup_node_versions()
    other = [
        (where, version)
        for where, version in versions
        if major_of(version, where=where) != types_major
    ]
    assert searched(other, of=len(versions), what="setup-node steps") == []


def test_dependabot_never_moves_types_node_past_the_runtime() -> None:
    ignored = update_for("npm", "/extension").get("ignore", [])
    rule = [entry for entry in ignored if entry.get("dependency-name") == "@types/node"]
    assert rule == [
        {"dependency-name": "@types/node", "update-types": ["version-update:semver-major"]}
    ]


# A version as a sortable (major, minor, patch), and a range of them as [low, high).
Triple = tuple[int, int, int]
EVERY_VERSION: tuple[Triple, Triple] = ((0, 0, 0), (10**9, 0, 0))
COMPARATOR = re.compile(r"(?P<op>\^|~|>=|<=|>|<|=)?(?P<version>[^-]*)(?P<pre>-[0-9A-Za-z.-]+)?")
VERSION_PART = re.compile(r"\d+|[xX*]")


def _known(version: str) -> list[int]:
    """The leading numbers of *version* (``8.x`` is ``[8]``); ``v``, build metadata or a hyphen
    range is refused by name, so no form this does not read is ever judged (#350)."""
    parts = version.split(".") if version else ["*"]
    if len(parts) > 3 or not all(VERSION_PART.fullmatch(part) for part in parts):
        msg = f"cannot read an npm version from {version!r}"
        raise AssertionError(msg)
    known: list[int] = []
    for part in parts:
        if not part.isdigit():
            break
        known.append(int(part))
    return known


def _past(known: list[int], places: int) -> Triple:
    """The first version after every one sharing *known*'s first *places* numbers."""
    head = [*known[: places - 1], known[places - 1] + 1]
    return _floor(head)


def _floor(known: list[int]) -> Triple:
    padded = [*known, 0, 0, 0]
    return padded[0], padded[1], padded[2]


def interval(comparator: str) -> tuple[Triple, Triple]:
    """The versions one npm comparator admits, as ``[low, high)``, by node-semver's rules."""
    found = COMPARATOR.fullmatch(comparator)
    assert found is not None, f"cannot read {comparator!r}"
    op, known = found["op"] or "=", _known(found["version"])
    # Only releases are judged, and a pre-release sorts below its release: ``>1.2.3-rc`` admits
    # 1.2.3 itself and ``=1.2.3-rc`` admits no release at all.
    assert not found["pre"] or len(known) == 3, f"cannot read {comparator!r}"
    if not known:
        assert op == "=", f"cannot read {comparator!r}"
        return EVERY_VERSION
    places = len(known)
    nonzero = [index + 1 for index, number in enumerate(known) if number]
    low, high = EVERY_VERSION
    after = _floor(known) if found["pre"] else _past(known, places)
    bounds = {
        "^": (_floor(known), _past(known, nonzero[0] if nonzero else places)),
        "~": (_floor(known), _past(known, min(places, 2))),
        ">=": (_floor(known), high),
        ">": (after, high),
        "<": (low, _floor(known)),
        "<=": (low, after),
        "=": (_floor(known), after),
    }
    return bounds[op]


def admits(npm_range: str, low: Triple, high: Triple) -> bool:
    """Whether *npm_range* admits any version in ``[low, high)``."""
    for alternative in npm_range.split("||"):
        start, end = low, high
        for comparator in alternative.split() or ["*"]:
            floor, ceiling = interval(comparator)
            start, end = max(start, floor), min(end, ceiling)
        if start < end:
            return True
    return False


@pytest.mark.parametrize(
    ("comparator", "admitted"),
    [
        ("^1.2.3", ((1, 2, 3), (2, 0, 0))),
        ("^0.2.3", ((0, 2, 3), (0, 3, 0))),
        ("^0.0.3", ((0, 0, 3), (0, 0, 4))),
        ("^0.0", ((0, 0, 0), (0, 1, 0))),
        ("~1.2.3", ((1, 2, 3), (1, 3, 0))),
        ("~1", ((1, 0, 0), (2, 0, 0))),
        (">=4.8.4", ((4, 8, 4), EVERY_VERSION[1])),
        (">1.2", ((1, 3, 0), EVERY_VERSION[1])),
        ("<6.1.0", ((0, 0, 0), (6, 1, 0))),
        ("<=1.2", ((0, 0, 0), (1, 3, 0))),
        ("5.0.5", ((5, 0, 5), (5, 0, 6))),
        ("8.x", ((8, 0, 0), (9, 0, 0))),
        ("*", EVERY_VERSION),
        ("^5.0.0-beta.5", ((5, 0, 0), (6, 0, 0))),
        (">1.2.3-rc.1", ((1, 2, 3), EVERY_VERSION[1])),
        ("<=1.2.3-rc.1", ((0, 0, 0), (1, 2, 3))),
        ("1.2.3-rc.1", ((1, 2, 3), (1, 2, 3))),
    ],
)
def test_interval_reads_a_comparator_as_npm_does(
    comparator: str, admitted: tuple[Triple, Triple]
) -> None:
    assert interval(comparator) == admitted


@pytest.mark.parametrize("comparator", ["1.0-rc.1", "-", "v1", "1.2.3.4", ">=*", "1.2.3+b1"])
def test_interval_refuses_a_form_it_does_not_read(comparator: str) -> None:
    with pytest.raises(AssertionError, match="cannot read"):
        interval(comparator)


@pytest.mark.parametrize(
    ("npm_range", "line"),
    [
        (">=4.8.4 <6.1.0", ((6, 0, 0), (7, 0, 0))),
        ("^8.57.0 || ^9.0.0 || ^10.0.0", ((10, 0, 0), (11, 0, 0))),
    ],
)
def test_admits_a_line_a_range_reaches(npm_range: str, line: tuple[Triple, Triple]) -> None:
    assert admits(npm_range, *line)


@pytest.mark.parametrize(
    ("npm_range", "line"),
    [
        (">=4.8.4 <6.1.0", ((7, 0, 0), (8, 0, 0))),
        ("^8.57.0 || ^9.0.0 || ^10.0.0", ((11, 0, 0), (12, 0, 0))),
        ("^0.27.0 || ^0.28.0", ((0, 29, 0), (0, 30, 0))),
    ],
)
def test_refuses_a_line_a_range_does_not_reach(npm_range: str, line: tuple[Triple, Triple]) -> None:
    assert not admits(npm_range, *line)


def locked_packages() -> dict[str, dict[str, Any]]:
    packages: dict[str, dict[str, Any]] = json.loads(NPM_LOCK.read_text(encoding="utf-8"))[
        "packages"
    ]
    return packages


def direct_versions() -> dict[str, str]:
    """Each direct dependency of the extension workspace and the version the lock installs."""
    names = {name for name, _ in exact_peers(NPM_LOCK)} | {
        name
        for path, entry in locked_packages().items()
        if not path.startswith("node_modules/")
        for field in ("dependencies", "devDependencies")
        for name in entry.get(field, {})
        if not name.startswith("@steadyhand/")
    }
    return {name: locked_packages()[f"node_modules/{name}"]["version"] for name in sorted(names)}


def breaking_line(version: str) -> tuple[Triple, Triple]:
    """The next release line npm's caret counts as breaking after *version*, as [low, high)."""
    found = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    assert found is not None, f"cannot read an installed version from {version!r}"
    major, minor = int(found[1]), int(found[2])
    if major:
        return (major + 1, 0, 0), (major + 2, 0, 0)
    return (0, minor + 1, 0), (0, minor + 2, 0)


def held_back(name: str, version: str) -> dict[str, Any]:
    """The ignore entry that keeps Dependabot off *name*'s next breaking line. Dependabot reads
    0.28 to 0.29 as a minor update, so a 0.x line is held back by version, not update type."""
    low, _ = breaking_line(version)
    if low[0]:
        return {"dependency-name": name, "update-types": ["version-update:semver-major"]}
    return {"dependency-name": name, "versions": [f">=0.{low[1]}.0"]}


def ceilings(name: str) -> list[str]:
    """Each locked package whose peer range refuses *name*'s next breaking line, so a pull request
    moving to it cannot install (#350). A peer moving with *name* in one group that takes every
    update type is left out, because Dependabot moves the two together (#349)."""
    groups: dict[str, dict[str, Any]] = update_for("npm", "/extension")["groups"]
    direct = direct_versions()
    line = breaking_line(direct[name])
    found: list[str] = []
    for path, entry in locked_packages().items():
        npm_range = entry.get("peerDependencies", {}).get(name)
        if npm_range is None or admits(npm_range, *line):
            continue
        owner = path.rpartition("node_modules/")[2]
        held = holders(name, groups)
        together = owner in direct and len(held) == 1 and holders(owner, groups) == held
        if together and "update-types" not in groups[held[0]]:
            continue
        found.append(f"{owner} ({npm_range})")
    return found


# Ignored for a reason of their own, not a peer's range: @types/node moves with CI's Node (#270).
OWN_IGNORES = {"@types/node": [held_back("@types/node", "24.0.0")]}


def test_the_peer_ceilings_are_the_ones_measured() -> None:
    # Measured on 2026-10-20 (#350): none of the four next lines is released yet but TypeScript 7.
    assert [name for name in direct_versions() if ceilings(name)] == [
        "esbuild",
        "eslint",
        "typescript",
        "vite",
    ]


@pytest.mark.parametrize("name", list(direct_versions()))
def test_dependabot_holds_back_exactly_the_lines_a_peer_refuses(name: str) -> None:
    ignored = update_for("npm", "/extension").get("ignore", [])
    rules = [entry for entry in ignored if entry.get("dependency-name") == name]
    blockers = ceilings(name)
    expected = OWN_IGNORES.get(name) or (
        [held_back(name, direct_versions()[name])] if blockers else []
    )
    # A peer that widens its range turns this red: the entry goes, and the update can land.
    assert rules == expected, blockers


def test_every_ignore_names_a_direct_dependency() -> None:
    ignored = update_for("npm", "/extension").get("ignore", [])
    stale = [
        entry["dependency-name"]
        for entry in ignored
        if entry["dependency-name"] not in direct_versions()
    ]
    assert searched(stale, of=len(ignored), what="npm ignore entries") == []
