"""The recorded floors, read by the Python tests (#272): one measured figure per population a guard
judges.

Shyden's rule (2026-10-02): a floor is the measured figure, checked for EQUALITY, so a guard that
goes blind to part of its population fails, and so does growth until it is recorded. A floor typed
into a test drifts the day after it is measured, so every figure lives in one file for both
languages, ``extension/tests/floors.json`` (EXT S3a #221), written only by its recorder. The
recorder runs every TypeScript and Python suite in the ``record-floors`` workflow, and raises a
figure but never lowers one; ``npm run floors:fetch <run id>`` brings its record to the laptop for
a commit (#285: CI records, the laptop commits). This module is the Python twin of
``extension/tests/lib/floors.ts``: the same file, the same messages, the same record format.
"""

import json
import os
from collections.abc import Mapping
from pathlib import Path

from population import ROOT

FLOORS_PATH = ROOT / "extension" / "tests" / "floors.json"

# Set by the recorder only: each floor then appends its measurement there instead of judging.
RECORD_ENV = "STEADYHAND_FLOORS_RECORD"

RECORD_ADVICE = "label the pull request record-floors, then npm run floors:fetch <run id>"

# pytest names the running test and its phase in this variable: "<node id> (<phase>)".
CURRENT_TEST = "PYTEST_CURRENT_TEST"


def parse_floors(text: str) -> dict[str, int]:
    """The floors in *text*; anything but whole numbers of zero or more is refused by id."""
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        msg = "the floors file is not an object of floor ids"
        raise ValueError(msg)  # noqa: TRY004 - one refusal for every malformed file, as in floors.ts
    for floor_id, figure in parsed.items():
        # A JSON true reads as a Python int, so a boolean is refused by its own type.
        if type(figure) is not int or figure < 0:
            msg = f"floor {floor_id}: {json.dumps(figure)} is not a whole number of zero or more"
            raise ValueError(msg)
    return parsed


def _current_test(env: Mapping[str, str]) -> str:
    """The test asserting a floor right now, by its node id; a floor asserted outside a test body
    is refused, so the recorder can tell who owns each one."""
    running = env.get(CURRENT_TEST)
    if running is None:
        msg = "a floor is asserted inside a test, so the recorder can tell who owns it"
        raise RuntimeError(msg)
    node_id, _, phase = running.rpartition(" (")
    if phase != "call)":
        msg = f"a floor is asserted inside a test body, not its {phase.removesuffix(')')}"
        raise RuntimeError(msg)
    return node_id


def floor_breach(
    floor_id: str,
    measured: int,
    env: Mapping[str, str] | None = None,
    floors_path: Path = FLOORS_PATH,
) -> str | None:
    """Why *measured* breaks floor *floor_id*, or ``None`` when it equals the recorded figure. Use
    it as ``assert floor_breach(floor_id, len(population)) is None``, after the verdict, in the test
    whose search judged that population."""
    env = os.environ if env is None else env
    recording = env.get(RECORD_ENV)
    if recording is not None:
        if env.get("GITHUB_WORKFLOW") != "record-floors":
            msg = (
                "floors are recorded only by the record-floors workflow, never on a laptop or in "
                "the checks they feed"
            )
            raise RuntimeError(msg)
        line = {"id": floor_id, "measured": measured, "test": _current_test(env)}
        with Path(recording).open("a", encoding="utf-8") as measurements:
            measurements.write(json.dumps(line) + "\n")
        return None
    recorded = parse_floors(floors_path.read_text(encoding="utf-8")).get(floor_id)
    if recorded is None:
        return f"floor {floor_id}: none recorded, measured {measured}; {RECORD_ADVICE}"
    if measured > recorded:
        return (
            f"floor {floor_id}: measured {measured}, recorded {recorded} (+{measured - recorded}); "
            f"read the growth against the diff, then {RECORD_ADVICE}"
        )
    if measured < recorded:
        return (
            f"floor {floor_id}: measured {measured}, recorded {recorded} ({measured - recorded}); "
            "a reader may have gone blind to part of its population. If it really shrank, lower "
            "the figure in extension/tests/floors.json by a deliberate edit"
        )
    return None
