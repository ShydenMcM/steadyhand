"""Markdown as a reader sees it, for the guards that look for a sentence in a document."""

import re

_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


def normalised(markdown: str) -> str:
    """Join a Markdown file into one line of single spaces, quote markers and comments removed.

    A sentence inside an HTML comment is never shown to a reader, so it does not count.
    """
    shown = _COMMENT.sub(" ", markdown)
    lines = (line.strip().removeprefix(">").strip() for line in shown.splitlines())
    return " ".join(" ".join(lines).split())
