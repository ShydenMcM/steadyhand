"""The disclaimer is written once and shown everywhere it must be (spec §9.8)."""

import re
from pathlib import Path

from steadyhand.disclaimer import DISCLAIMER

ROOT = Path(__file__).resolve().parents[2]
# Plans, specs and research notes are for the people building steadyhand, not its users.
INTERNAL = frozenset({"superpowers", "research"})
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, quote markers and comments removed.

    A disclaimer inside an HTML comment is never shown to a reader, so it does not count.
    """
    shown = _COMMENT.sub(" ", markdown)
    lines = (line.strip().removeprefix(">").strip() for line in shown.splitlines())
    return " ".join(" ".join(lines).split())


def user_docs(docs: Path) -> list[Path]:
    """Every Markdown file under *docs* except the internal folders, found on disk."""
    return sorted(
        path for path in docs.rglob("*.md") if path.relative_to(docs).parts[0] not in INTERNAL
    )


def missing_disclaimer(paths: list[Path]) -> list[str]:
    return [
        path.relative_to(ROOT).as_posix()
        for path in paths
        if DISCLAIMER not in normalised(path.read_text(encoding="utf-8"))
    ]


def test_disclaimer_text_is_pinned() -> None:
    assert DISCLAIMER == (
        "steadyhand is example software that you run yourself, on your own account, and you "
        "make your own decisions with it. It is not financial advice. You can lose money."
    )


def test_normalising_joins_wrapped_quoted_lines() -> None:
    assert normalised("> one\n> two  three\n") == "one two three"


def test_normalising_drops_html_comments() -> None:
    assert normalised("one <!-- hidden\nstill hidden --> two") == "one two"


def test_user_docs_skip_only_the_internal_folders(tmp_path: Path) -> None:
    for name in ("guide.md", "strategies/a.md", "superpowers/plan.md", "research/t.md", "x.txt"):
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_text("text", encoding="utf-8")
    found = [path.relative_to(tmp_path).as_posix() for path in user_docs(tmp_path)]
    assert found == ["guide.md", "strategies/a.md"]


def test_every_readme_carries_the_disclaimer() -> None:
    assert len(DISCLAIMER.split()) >= 10  # an empty disclaimer is "in" every file
    readmes = [ROOT / "README.md", *sorted(ROOT.glob("packages/*/README.md"))]
    assert len(readmes) == 3
    assert missing_disclaimer(readmes) == []


def test_every_user_facing_doc_carries_the_disclaimer() -> None:
    docs = user_docs(ROOT / "docs")
    assert ROOT / "docs/lq45-members.md" in docs
    assert missing_disclaimer(docs) == []
