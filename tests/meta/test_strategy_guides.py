"""Every registered strategy has a complete plain-English guide (core spec §8, §10.1), shipped
inside the package (M5 spec §5.6), whose *Settings you can change* names each of the strategy's
registered settings (M6 spec §7).

The guide is read with its HTML comments removed, so a section commented out is missing.
"""

import re
from pathlib import Path

import pytest
from population import searched, tracked

from steadyhand.strategies import STRATEGIES, Setting, Strategy

ROOT = Path(__file__).resolve().parents[2]
GUIDES = ROOT / "packages/steadyhand/src/steadyhand/strategies/guides"
SECTIONS = (
    "What it does",
    "Why people use it",
    "When it tends to do badly",
    "Risks",
    "How often it trades",
    "Settings you can change",
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def sections(markdown: str) -> dict[str, str]:
    """Each ``## `` heading's text, mapped to the words under it, comments removed."""
    found: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in _COMMENT.sub("", markdown).splitlines():
        if line.startswith("## "):
            current = found.setdefault(line.removeprefix("## ").strip(), [])
        elif current is not None:
            current.append(line)
    return {heading: " ".join(" ".join(lines).split()) for heading, lines in found.items()}


def problems(name: str, markdown: str, settings: tuple[Setting, ...] = ()) -> list[str]:
    found = sections(markdown)
    wrong = [f"missing or empty: {section}" for section in SECTIONS if not found.get(section)]
    named = found.get("Settings you can change", "")
    wrong += [
        f"Settings you can change must name `{setting.name}`"
        for setting in settings
        if f"`{setting.name}`" not in named
    ]
    risks = found.get("Risks", "").lower()
    wrong += [
        f"Risks must say {phrase!r}"
        for phrase in ("you can lose money", "fee")
        if phrase not in risks
    ]
    if not markdown.startswith(f"# {name}\n"):
        wrong.append(f"the first line must be '# {name}'")
    return wrong


def complete(name: str) -> str:
    body = "".join(f"## {section}\nWords. You can lose money. Fee drag.\n" for section in SECTIONS)
    return f"# {name}\n{body}"


ROUNDS = Setting("rounds", 3, 1, 9, "How many rounds to play.")


def test_a_complete_guide_has_no_problems() -> None:
    assert problems("x", complete("x")) == []
    named = complete("x").replace(
        "## Settings you can change\nWords.", "## Settings you can change\n`rounds`."
    )
    assert problems("x", named, (ROUNDS,)) == []


@pytest.mark.parametrize(
    "settings_text",
    [
        "Words.",
        "rounds, written without its backticks.",
        "<!-- `rounds` -->",
    ],
)
def test_the_checker_wants_each_setting_named_in_its_section(settings_text: str) -> None:
    guide = complete("x").replace(
        "## Settings you can change\nWords.", f"## Settings you can change\n{settings_text}"
    )
    # Named elsewhere does not count: only the settings section says what can be changed.
    guide = guide.replace("## Risks\nWords.", "## Risks\nWords. `rounds`.")
    assert guide.count("## Settings you can change\n") == 1
    assert "Settings you can change must name `rounds`" in problems("x", guide, (ROUNDS,))


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        (("## Risks\n", "## Risk\n"), "missing or empty: Risks"),
        (
            ("## Why people use it\nWords.", "<!-- ## Why people use it -->\nWords."),
            "missing or empty: Why people use it",
        ),
        (
            (
                "## How often it trades\nWords. You can lose money. Fee drag.\n",
                "## How often it trades\n<!-- hidden -->\n",
            ),
            "missing or empty: How often it trades",
        ),
        (
            ("You can lose money. Fee drag.\n## How", "Fee drag.\n## How"),
            "Risks must say 'you can lose money'",
        ),
        (("# x\n", "# y\n"), "the first line must be '# x'"),
    ],
)
def test_the_checker_finds_each_problem(change: tuple[str, str], problem: str) -> None:
    guide = complete("x")
    assert guide.count(change[0]) >= 1
    assert problem in problems("x", guide.replace(change[0], change[1], 1))


def test_every_registered_strategy_has_a_complete_guide() -> None:
    assert "buy-and-hold" in STRATEGIES
    missing = [name for name in STRATEGIES if not (GUIDES / f"{name}.md").is_file()]
    assert missing == []
    found = {
        name: wrong
        for name, entry in STRATEGIES.items()
        if (
            wrong := problems(
                name, (GUIDES / f"{name}.md").read_text(encoding="utf-8"), entry.settings
            )
        )
    }
    assert found == {}


def test_every_guide_is_for_a_registered_strategy() -> None:
    guides = sorted(path.stem for path in GUIDES.glob("*.md"))
    assert "buy-and-hold" in guides
    # Independent of the walk: the guides as git lists them.
    assert guides == [path.stem for path in tracked(GUIDES, ".md")]
    stray = [name for name in guides if name not in STRATEGIES]
    assert searched(stray, of=len(guides), what="guides") == []


@pytest.mark.parametrize("name", STRATEGIES)
def test_each_registered_name_is_the_strategys_own(name: str) -> None:
    strategy = STRATEGIES[name]()
    assert isinstance(strategy, Strategy)
    assert strategy.name == name
