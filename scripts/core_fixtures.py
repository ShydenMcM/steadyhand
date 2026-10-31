"""Write what the extension's core reads from Python (#223, spec §4.1, §4.2).

The rule files become JSON in ``extension/packages/core/rules/``, each read and checked by
Python's own reader first, so a file Python refuses is never converted. Whole numbers and dates
are written as strings: core never holds a ``number``, and reads each as a ``bigint`` or a date.
The ratio fixture holds Python's digits for seeded inputs, which core's ratios must give exactly.

Run from the repository root: ``uv run --locked python scripts/core_fixtures.py``. CI runs it again
and fails if a committed file differs (tests/integration/scripts/test_core_fixtures.py).
"""

import argparse
import json
import random
from collections.abc import Callable
from datetime import date
from decimal import ROUND_HALF_EVEN, Context, Decimal
from pathlib import Path

from steadyhand._ratio import ratio_down
from steadyhand.metrics import _rounded
from steadyhand_idx._datafile import Row, load_shipped
from steadyhand_idx.bands import BANDS_FILE, parse_bands
from steadyhand_idx.calendar import HOLIDAYS_FILE, parse_holidays
from steadyhand_idx.fees import FEES_FILE, parse_fees
from steadyhand_idx.ticks import TICKS_FILE, parse_settlement, parse_ticks

ROOT = Path(__file__).resolve().parents[1]
RULES = Path("extension/packages/core/rules")
RATIOS = Path("extension/packages/core/test/ratios.json")

# Each rule file and the Python readers that must accept it before it is converted.
READERS: dict[str, tuple[Callable[[Row], object], ...]] = {
    TICKS_FILE: (parse_ticks, parse_settlement),
    BANDS_FILE: (parse_bands,),
    HOLIDAYS_FILE: (parse_holidays,),
    FEES_FILE: (parse_fees,),
}

SEED = 223
CASES = 200
# Fifty significant digits, half-even: the context the engine's ratios are worked out in.
WIDE = Context(prec=50, rounding=ROUND_HALF_EVEN)


def plain(value: object) -> object:
    """*value* with every whole number and date written as a string, keys in order."""
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [plain(item) for item in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    return value


def rule_files() -> dict[Path, object]:
    """Each rule file as JSON, once every reader of it accepts it."""
    written: dict[Path, object] = {}
    for name, readers in READERS.items():
        document = load_shipped(name)
        for reader in readers:
            reader(document)
        written[RULES / name.replace(".toml", ".json")] = plain(document)
    return written


def ratio_cases() -> dict[str, list[list[str]]]:
    """Python's ``ratio_down`` and its eight-place rounding on seeded inputs and their edges."""
    draw = random.Random(SEED)  # noqa: S311 - seeded test inputs, not secrets
    pairs = [(0, 1), (1, 3), (2, 3), (-1, 3), (5, 0), (10**15, 7), (1, 10**15), (7, 7)]
    pairs += [(draw.randrange(10**15), draw.randrange(1, 10**15)) for _ in range(CASES)]
    down = [[str(part), str(whole), str(ratio_down(part, whole))] for part, whole in pairs]
    values = [Decimal(text) for text in ("0.000000005", "0.000000015", "-0.000000025", "1e30")]
    values += [Decimal("123456789012345678901234567890.123456785")]
    values += [WIDE.divide(Decimal(part), Decimal(whole)) for part, whole in pairs if whole]
    rounded = [[str(value), str(_rounded(value))] for value in values]
    return {"ratio_down": down, "rounded": rounded}


def text(value: object) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False) + "\n"


def outputs() -> dict[Path, str]:
    """Every file this script writes, by its path from the repository root."""
    files = {path: text(document) for path, document in rule_files().items()}
    files[RATIOS] = text(ratio_cases())
    return files


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT, help="where to write the files")
    root: Path = parser.parse_args(argv).root
    for path, content in outputs().items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
