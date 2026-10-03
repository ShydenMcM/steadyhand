"""The one reader of Python source for the guards in ``tests/meta`` (#190).

Shyden's rule (2026-10-02), control (d): a reader refuses what it cannot classify by name, and
never skips it. ``ast.parse`` alone raises a ``SyntaxError`` that names ``<unknown>``, so a guard
calling it directly refused a broken module without saying which one. ``parse`` names the file.
``test_source_tree.py`` keeps it the only place in ``tests/`` that parses source.
"""

import ast


class UnreadableSourceError(Exception):
    """Source a guard cannot read: refused by name, never skipped."""


def parse(source: str, name: str) -> ast.Module:
    """The module *source* holds; *name* names the file in errors."""
    try:
        return ast.parse(source)
    except SyntaxError as error:
        msg = f"{name}: {error}"
        raise UnreadableSourceError(msg) from error
