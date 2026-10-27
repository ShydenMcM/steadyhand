"""BBRI's whole recording, 2014 to 2026, restored in full (moved out of unit by #292).

Each reads and restores the whole recording, over the unit limit of 0.07 s of its own CPU in its
heaviest measured run (develop, 2026-10-13: 125 ms and 92 ms; CI py3.13 up to 114 ms with the
collector frozen, #302). The unit suite keeps the rules on short made-up histories in
``tests/idx/test_yahoo.py``: a row whose volume is not whole stays refused though its prices
count (``test_a_row_whose_volume_is_not_whole_stays_refused_though_its_prices_count``), a flat
row with no volume is no evidence
(``test_a_flat_row_with_no_volume_inside_a_proven_run_is_restored_though_it_is_no_evidence``) and
the proof reads every row priced off whole rupiah
(``test_the_proof_reads_every_row_with_a_price_off_whole_rupiah_and_nothing_else``); and the
other thirteen recordings' pinned answers in ``tests/idx/test_yahoo_answers.py``.
"""

from datetime import date, timedelta
from functools import cache
from pathlib import Path

import pytest
from test_yahoo_answers import PINNED, WHOLE_BBRI, answers

from steadyhand import IDR, Instrument
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.factor import find_runs
from steadyhand_idx.yahoo import UnrecoverablePricesError, evidence, history_from_json, unadjust

BBRI = Instrument("BBRI", "IDX", IDR)


@cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


def test_bbri_s_golden_years_are_restored_except_where_a_volume_is_not_whole() -> None:
    # #160 spec §9.2: 1,103 days from 2017-01-31 to 2021-09-07 are evidence, a price off whole
    # rupiah on a day that is not a flat row with no volume (57 flat days there have one too); the
    # 153 before the 5-for-1 split of 2017-11-10 also have a volume that is not whole (#162).
    history = history_from_json(WHOLE_BBRI)
    found = evidence(history)
    runs = find_runs(found)
    span = (date(2017, 1, 31), date(2021, 9, 7))
    every_day = {span[0] + timedelta(days=n) for n in range((span[1] - span[0]).days + 1)}
    assert len([row for row in found if row.day in every_day]) == 1_103
    with pytest.raises(UnrecoverablePricesError) as refused:
        unadjust(history, BBRI, calendar(), span, runs)
    assert (len(refused.value.days), refused.value.days[-1]) == (153, date(2017, 11, 9))
    bars, _ = unadjust(history, BBRI, calendar(), (date(2017, 11, 10), span[1]), runs)
    assert len(bars) == len(calendar().trading_days(date(2017, 11, 10), span[1]))


@pytest.mark.parametrize("path", [WHOLE_BBRI], ids=lambda path: path.stem)
def test_a_recording_restores_to_its_pinned_answers(path: Path) -> None:
    assert answers(path) == PINNED[path.name]
