"""Every key and string value of a parsed configuration file: a workflow's YAML or a TOML table.

Shared by the guards that look for a word wherever a workflow or ``pyproject.toml`` could carry
it (the floors recorder, #285; a raised test limit, #323), so each reads every run line, env name
and input the same way.
"""

from collections.abc import Iterator
from typing import Any


def strings_in(node: Any) -> Iterator[str]:  # noqa: ANN401 - parsed YAML and TOML are untyped
    """Every key and every string value in a parsed workflow: a run line, an env name, an input."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from strings_in(value)
    elif isinstance(node, list):
        for item in node:
            yield from strings_in(item)
    elif isinstance(node, str):
        yield node
