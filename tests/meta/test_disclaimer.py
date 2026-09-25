"""The disclaimer is written once and shown everywhere it must be (spec §9.8)."""

from pathlib import Path

from steadyhand.disclaimer import DISCLAIMER

ROOT = Path(__file__).resolve().parents[2]


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, with quote markers removed."""
    lines = (line.strip().removeprefix(">").strip() for line in markdown.splitlines())
    return " ".join(" ".join(lines).split())


def test_disclaimer_text_is_pinned() -> None:
    assert DISCLAIMER == (
        "steadyhand is example software that you run yourself, on your own account, and you "
        "make your own decisions with it. It is not financial advice. You can lose money."
    )


def test_normalising_joins_wrapped_quoted_lines() -> None:
    assert normalised("> one\n> two  three\n") == "one two three"


def test_every_readme_carries_the_disclaimer() -> None:
    assert len(DISCLAIMER.split()) >= 10  # an empty disclaimer is "in" every file
    readmes = [ROOT / "README.md", *sorted(ROOT.glob("packages/*/README.md"))]
    assert len(readmes) == 3
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in readmes
        if DISCLAIMER not in normalised(path.read_text(encoding="utf-8"))
    ]
    assert missing == []
