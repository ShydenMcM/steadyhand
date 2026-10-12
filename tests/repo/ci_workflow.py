"""``ci.yml``, parsed once per run for the tests that read it (#285).

Each of them parsed it at import with PyYAML's pure-Python loader, 51-87 ms of load CPU apiece
(measured 2026-10-12); libyaml's C loader reads the same YAML with the same resolver, and the
cache shares one reading. A PyYAML built without libyaml is refused by name, never silently slow.
"""

from functools import cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / ".github/workflows/ci.yml"


class NoLibyamlError(RuntimeError):
    """PyYAML without its C loader: the workflow tests would load slower than a unit file may."""


def parse(text: str) -> Any:  # noqa: ANN401 - parsed YAML is untyped
    """*text* read by libyaml's safe loader."""
    loader = getattr(yaml, "CSafeLoader", None)
    if loader is None:
        msg = "PyYAML has no CSafeLoader: install a PyYAML built with libyaml"
        raise NoLibyamlError(msg)
    return yaml.load(text, Loader=loader)  # noqa: S506 - CSafeLoader is the safe loader


@cache
def ci() -> dict[str | bool, Any]:
    """The CI workflow, parsed on first use and shared after."""
    parsed: dict[str | bool, Any] = parse(CI.read_text(encoding="utf-8"))
    return parsed
