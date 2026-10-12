"""The Hypothesis profile of the properties suite, the only suite that draws cases (#290).

Shyden's rules (2026-10-12, every project, yawelo-idle #543): a property moved out of unit runs
at its original count and draws fresh cases every run. On GitHub Actions Hypothesis turns
``derandomize`` on by itself, and a registered profile inherits it (measured on 6.168.5,
2026-10-13), so every CI run repeated the same cases until this profile turned it off by name. A
red here is a real defect, never a re-run: file it, reproduce it from the printed blob, fix it,
and keep the shrunk case as a named stand-in in unit.

No deadline: a per-example deadline times the machine as well as the code, and a busy laptop
turned it into a red the next run could not reproduce (#30).
"""

from hypothesis import settings


def load() -> None:
    """Make the properties profile every test's default; tests/conftest.py calls it before a
    properties run collects anything."""
    settings.register_profile(
        "properties", max_examples=500, deadline=None, print_blob=True, derandomize=False
    )
    settings.load_profile("properties")
