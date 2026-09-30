"""The SQLite cache and the cached data source, on real recorded Yahoo data."""

import functools
import sqlite3
from collections.abc import Iterator
from contextlib import closing
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from steadyhand import (
    IDR,
    Bar,
    CashDividend,
    CorporateAction,
    DataSource,
    DataUnavailableError,
    Instrument,
    Money,
    OtherAction,
    Split,
)
from steadyhand_idx.cache import (
    MIGRATIONS,
    BarCache,
    CacheConflictError,
    CachedDataSource,
    CacheSchemaError,
    jakarta_today,
)
from steadyhand_idx.calendar import IdxCalendar
from steadyhand_idx.yahoo import (
    YahooDataSource,
    YahooHistory,
    YahooRow,
    history_from_json,
    unadjust,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "yahoo"
BBCA = Instrument("BBCA", "IDX", IDR)
BBRI = Instrument("BBRI", "IDX", IDR)


@functools.cache
def calendar() -> IdxCalendar:
    return IdxCalendar.shipped()


SEP = (date(2021, 9, 1), date(2021, 9, 30))
OCT = (date(2021, 10, 1), date(2021, 10, 29))


def bbca(start: date, end: date) -> tuple[list[Bar], list[CorporateAction]]:
    history = history_from_json(FIXTURES / "BBCA.JK_2021-09-01_2021-11-30.json")
    return unadjust(history, BBCA, calendar(), start, end)


@pytest.fixture
def cache(tmp_path: Path) -> Iterator[BarCache]:
    with BarCache(tmp_path / "cache.sqlite") as opened:
        yield opened


def test_a_new_cache_runs_every_migration(tmp_path: Path) -> None:
    with BarCache(tmp_path / "c.sqlite") as fresh:
        assert fresh.schema_version == len(MIGRATIONS)
    with BarCache(tmp_path / "c.sqlite") as reopened:
        assert reopened.schema_version == len(MIGRATIONS)


def test_a_cache_from_a_newer_release_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "c.sqlite"
    with closing(sqlite3.connect(path)) as raw:
        raw.execute(f"PRAGMA user_version = {len(MIGRATIONS) + 1}")
    with pytest.raises(
        CacheSchemaError,
        match=r"c\.sqlite is at cache schema 3, newer than this steadyhand-idx knows \(2\);",
    ):
        BarCache(path)


def test_an_older_cache_is_upgraded_in_place(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.sqlite"
    with BarCache(path) as old:
        old.store(BBCA, SEP, *bbca(*SEP))
    extra = "CREATE TABLE notes (text TEXT NOT NULL) STRICT;"
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", (*MIGRATIONS, extra))
    with BarCache(path) as upgraded:
        assert upgraded.schema_version == len(MIGRATIONS) + 1
        assert len(upgraded.bars(BBCA, *SEP)) == len(calendar().trading_days(*SEP))


def test_bars_and_actions_round_trip(cache: BarCache) -> None:
    bars, actions = bbca(date(2021, 10, 1), date(2021, 11, 30))
    other = OtherAction(BBCA, date(2021, 11, 1), "rights issue, entered by hand")
    cache.store(BBCA, (date(2021, 10, 1), date(2021, 11, 30)), bars, [*actions, other])
    assert cache.bars(BBCA, date(2021, 10, 1), date(2021, 11, 30)) == bars
    assert cache.actions(BBCA, date(2021, 10, 1), date(2021, 11, 30)) == [
        Split(BBCA, date(2021, 10, 13), 1, 5),
        other,
        CashDividend(BBCA, date(2021, 11, 17), Decimal("25.0")),
    ]


def test_storing_the_same_data_twice_changes_nothing(cache: BarCache) -> None:
    span = (date(2021, 10, 1), date(2021, 11, 30))
    cache.store(BBCA, span, *bbca(*span))
    cache.store(BBCA, span, *bbca(*span))
    assert cache.bars(BBCA, *span) == bbca(*span)[0]
    assert cache.actions(BBCA, *span) == bbca(*span)[1]


def test_a_conflicting_fetch_stores_nothing(cache: BarCache) -> None:
    bars, actions = bbca(*SEP)
    cache.store(BBCA, (SEP[0], date(2021, 9, 15)), bars[:11], [])
    kept = bars[3]
    changed = replace(kept, close=Money(kept.close.amount + 25, IDR))
    cached = (kept.open.amount, kept.high.amount, kept.low.amount, kept.close.amount, kept.volume)
    expected = rf"^BBCA {kept.day.isoformat()}: cached bar \({', '.join(map(str, cached))}\)"
    with pytest.raises(CacheConflictError, match=expected + " differs from fetched"):
        cache.store(BBCA, SEP, [*bars[:3], changed, *bars[4:]], actions)
    assert len(cache.bars(BBCA, *SEP)) == 11  # the later bars in that fetch were not written
    assert cache.fetched(BBCA) == [(SEP[0], date(2021, 9, 15))]


def test_a_conflicting_action_stores_nothing(cache: BarCache) -> None:
    dividend = CashDividend(BBCA, date(2021, 11, 17), Decimal("25.0"))
    cache.store(BBCA, (date(2021, 11, 17), date(2021, 11, 17)), [], [dividend])
    with pytest.raises(CacheConflictError, match=r"^BBCA 2021-11-17: cached dividend"):
        cache.store(
            BBCA,
            (date(2021, 11, 17), date(2021, 11, 17)),
            [],
            [replace(dividend, per_share=Decimal(26))],
        )


def test_rows_outside_the_range_or_for_another_stock_are_refused(cache: BarCache) -> None:
    bars, _ = bbca(*SEP)
    with pytest.raises(
        ValueError, match=r"^BBCA 2021-09-01 is not BBCA in 2021-09-02 to 2021-09-30$"
    ):
        cache.store(BBCA, (date(2021, 9, 2), SEP[1]), bars, [])
    with pytest.raises(ValueError, match=r"^BBCA 2021-09-01 is not BBRI in"):
        cache.store(BBRI, SEP, bars, [])
    with pytest.raises(ValueError, match=r"^this cache holds IDX IDR stocks, not X on ASX$"):
        cache.bars(Instrument("X", "ASX", IDR), *SEP)


def test_fetched_ranges_merge_where_they_touch(cache: BarCache) -> None:
    cache.store(BBCA, (date(2021, 9, 1), date(2021, 9, 10)), [], [])
    cache.store(BBCA, (date(2021, 9, 11), date(2021, 9, 20)), [], [])
    cache.store(BBCA, (date(2021, 9, 15), date(2021, 9, 17)), [], [])
    cache.store(BBCA, (date(2021, 10, 1), date(2021, 10, 5)), [], [])
    assert cache.fetched(BBCA) == [
        (date(2021, 9, 1), date(2021, 9, 20)),
        (date(2021, 10, 1), date(2021, 10, 5)),
    ]


def test_missing_skips_stored_ranges_and_non_trading_gaps(cache: BarCache) -> None:
    for span in [
        (date(2021, 9, 1), date(2021, 9, 10)),
        (date(2021, 9, 20), date(2021, 9, 24)),
        (date(2021, 10, 1), date(2021, 10, 5)),
        (date(2021, 11, 1), date(2021, 11, 5)),
        (date(2021, 11, 8), date(2021, 11, 12)),
    ]:
        cache.store(BBCA, span, [], [])
    source = CachedDataSource(YahooDataSource(calendar()), cache, calendar())
    assert source.missing(BBCA, date(2021, 9, 13), date(2021, 10, 15)) == [
        (date(2021, 9, 13), date(2021, 9, 17)),  # a hole between two stored ranges
        (date(2021, 9, 27), date(2021, 9, 30)),  # 25-26 Sep is a weekend
        (date(2021, 10, 6), date(2021, 10, 15)),  # after the last range that overlaps
    ]
    # A hole holding no trading day at all (6-7 Nov is a weekend) is not missing.
    assert source.missing(BBCA, date(2021, 11, 1), date(2021, 11, 12)) == []


class Counting:
    """A real YahooDataSource on a recording, counting what reaches it."""

    def __init__(self, name: str) -> None:
        self.history = history_from_json(FIXTURES / name)
        self.asked: list[tuple[date, date]] = []
        self.source = YahooDataSource(calendar(), download=self._download, sleep=lambda _: None)

    def _download(self, ticker: str, start: date, end: date) -> YahooHistory:
        self.asked.append((start, end))
        return self.history


def source_for(cache: BarCache, name: str, today: date) -> tuple[CachedDataSource, Counting]:
    counting = Counting(name)
    return CachedDataSource(counting.source, cache, calendar(), today=lambda: today), counting


def test_a_range_is_fetched_once_then_served_from_the_cache(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    assert isinstance(source, DataSource)
    first = source.bars(BBCA, *OCT)
    assert source.corporate_actions(BBCA, *OCT) == [Split(BBCA, date(2021, 10, 13), 1, 5)]
    assert source.bars(BBCA, *OCT) == first
    assert counting.asked == [OCT]


def test_only_the_missing_trading_days_are_fetched(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    source.bars(BBCA, date(2021, 9, 1), date(2021, 9, 24))  # ends on a Friday
    assert source.missing(BBCA, date(2021, 9, 1), date(2021, 9, 26)) == []  # only a weekend left
    source.bars(BBCA, date(2021, 9, 1), date(2021, 10, 8))
    assert counting.asked == [
        (date(2021, 9, 1), date(2021, 9, 24)),
        (date(2021, 9, 27), date(2021, 10, 8)),
    ]


def test_today_is_always_fetched_and_never_stored(cache: BarCache) -> None:
    today = date(2021, 10, 13)
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", today)
    bars = source.bars(BBCA, date(2021, 10, 11), today)
    assert [bar.day for bar in bars] == [date(2021, 10, 11), date(2021, 10, 12), today]
    source.bars(BBCA, date(2021, 10, 11), today)
    assert counting.asked == [(date(2021, 10, 11), date(2021, 10, 12)), (today, today)]
    assert source.corporate_actions(BBCA, date(2021, 10, 11), today) == [Split(BBCA, today, 1, 5)]
    assert cache.fetched(BBCA) == [(date(2021, 10, 11), date(2021, 10, 12))]
    assert [bar.day for bar in source.bars(BBCA, today, today)] == [today]  # nothing to fill
    assert source.corporate_actions(BBCA, today, today) == [Split(BBCA, today, 1, 5)]
    assert len(counting.asked) == 2


def test_a_request_past_today_or_reversed_is_refused(cache: BarCache) -> None:
    source, _ = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2021, 10, 13))
    with pytest.raises(
        ValueError, match=r"^no bars exist yet after today \(2021-10-13\); asked for 2021-10-14$"
    ):
        source.bars(BBCA, date(2021, 10, 1), date(2021, 10, 14))
    with pytest.raises(ValueError, match=r"^end 2021-10-01 is before start 2021-10-02$"):
        source.bars(BBCA, date(2021, 10, 2), date(2021, 10, 1))


def test_unrecoverable_prices_are_never_cached(cache: BarCache) -> None:
    source, _ = source_for(cache, "BBRI.JK_2021-08-02_2021-09-30.json", date(2026, 9, 25))
    with pytest.raises(DataUnavailableError, match="cannot be recovered"):
        source.bars(BBRI, date(2021, 9, 1), date(2021, 9, 30))
    assert cache.fetched(BBRI) == []
    assert len(source.bars(BBRI, date(2021, 9, 8), date(2021, 9, 30))) == 17


def test_the_default_clock_is_jakartas_date() -> None:
    assert abs((jakarta_today() - date.today()).days) <= 1  # noqa: DTZ011 - comparing two clocks


LOOK_BACK = (date(2017, 1, 31), date(2021, 9, 30))
"""BBRI's years before a run: its prices up to 2021-09-07 cannot be recovered."""


def test_a_cache_from_before_m6_is_upgraded_and_keeps_its_ranges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.sqlite"
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS[:1])
    with BarCache(path) as old:
        old.store(BBCA, SEP, *bbca(*SEP))
        assert old.schema_version == 1
    monkeypatch.setattr("steadyhand_idx.cache.MIGRATIONS", MIGRATIONS)
    with BarCache(path) as upgraded:
        assert upgraded.schema_version == 2
        assert upgraded.fetched_actions(BBCA) == [SEP]
        upgraded.store_actions(BBCA, OCT, [Split(BBCA, date(2021, 10, 13), 1, 5)])
        assert upgraded.fetched_actions(BBCA) == [(date(2021, 9, 1), date(2021, 10, 29))]
        assert upgraded.fetched(BBCA) == [SEP]


def test_actions_stored_alone_leave_their_bars_missing(cache: BarCache) -> None:
    split = Split(BBCA, date(2021, 10, 13), 1, 5)
    cache.store_actions(BBCA, OCT, [split])
    assert cache.actions(BBCA, *OCT) == [split]
    assert cache.fetched_actions(BBCA) == [OCT]
    assert cache.fetched(BBCA) == []
    cache.store_actions(BBCA, OCT, [split])  # the same again changes nothing
    assert cache.actions(BBCA, *OCT) == [split]


def test_actions_stored_alone_are_all_or_nothing_and_stay_in_their_range(cache: BarCache) -> None:
    dividend = CashDividend(BBCA, date(2021, 10, 5), Decimal(25))
    cache.store_actions(BBCA, OCT, [dividend])
    changed = CashDividend(BBCA, date(2021, 10, 5), Decimal(30))
    later = CashDividend(BBCA, date(2021, 11, 17), Decimal(25))
    with pytest.raises(CacheConflictError, match=r"^BBCA 2021-10-05: cached dividend"):
        cache.store_actions(BBCA, (date(2021, 10, 1), date(2021, 11, 30)), [later, changed])
    assert cache.actions(BBCA, date(2021, 10, 1), date(2021, 11, 30)) == [dividend]
    assert cache.fetched_actions(BBCA) == [OCT]
    with pytest.raises(ValueError, match=r"^BBCA 2021-11-17 is not BBCA in 2021-10-01 to"):
        cache.store_actions(BBCA, OCT, [later])
    with pytest.raises(ValueError, match=r"^BBRI 2021-10-05 is not BBCA in 2021-10-01 to"):
        cache.store_actions(BBCA, OCT, [CashDividend(BBRI, date(2021, 10, 5), Decimal(1))])


def test_missing_actions_skips_ranges_stored_either_way(cache: BarCache) -> None:
    cache.store(BBCA, (date(2021, 9, 1), date(2021, 9, 10)), [], [])
    cache.store_actions(BBCA, (date(2021, 9, 20), date(2021, 9, 24)), [])
    source = CachedDataSource(YahooDataSource(calendar()), cache, calendar())
    assert source.missing_actions(BBCA, date(2021, 9, 1), date(2021, 9, 30)) == [
        (date(2021, 9, 13), date(2021, 9, 17)),  # 11-12 Sep is a weekend
        (date(2021, 9, 27), date(2021, 9, 30)),
    ]
    # The bars of the range stored for its actions alone are still missing.
    assert source.missing(BBCA, date(2021, 9, 20), date(2021, 9, 24)) == [
        (date(2021, 9, 20), date(2021, 9, 24))
    ]
    # A gap reaching into a year the calendar does not cover is asked for whole.
    assert source.missing_actions(BBCA, date(2015, 1, 1), date(2021, 9, 10)) == [
        (date(2015, 1, 1), date(2021, 8, 31))
    ]


def test_a_look_back_is_fetched_once_without_its_prices(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBRI.JK_2017-01-31_2022-01-31.json", date(2026, 9, 25))
    first = source.corporate_actions(BBRI, *LOOK_BACK)
    assert [(a.ex_date, a.per_share) for a in first if isinstance(a, CashDividend)] == [
        (date(2017, 3, 23), Decimal("389.63463")),
        (date(2018, 4, 2), Decimal("97.04093")),
        (date(2019, 5, 24), Decimal("120.15633")),
        (date(2020, 2, 27), Decimal("152.90845")),
        (date(2021, 4, 6), Decimal("89.91268")),
    ]
    in_2019 = [action for action in first if action.ex_date.year == 2019]
    assert source.corporate_actions(BBRI, date(2019, 1, 1), date(2019, 12, 31)) == in_2019
    assert counting.asked == [LOOK_BACK]
    assert cache.fetched(BBRI) == []
    with pytest.raises(DataUnavailableError, match="cannot be recovered"):
        source.bars(BBRI, *LOOK_BACK)


def test_a_refused_look_back_is_not_stored(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    counting.history = YahooHistory("X.JK", (), ((date(2021, 10, 13), Decimal("0.3333")),))
    for _ in range(2):
        with pytest.raises(DataUnavailableError, match=r"^BBCA: Yahoo's split ratio 0\.3333 on"):
            source.corporate_actions(BBCA, *OCT)
    # One download, which the Yahoo source keeps for its next call; nothing reaches the cache.
    assert counting.asked == [OCT]
    assert cache.fetched_actions(BBCA) == []
    assert cache.actions(BBCA, *OCT) == []


def test_a_look_back_before_the_calendar_is_asked_for_whole(cache: BarCache) -> None:
    source, counting = source_for(cache, "BBCA.JK_2021-09-01_2021-11-30.json", date(2026, 9, 25))
    row = YahooRow(date(2015, 6, 1), *(Decimal(1000),) * 4, volume=100, dividend=Decimal(50))
    counting.history = YahooHistory("BBCA.JK", (row,), ())
    span = (date(2015, 1, 1), date(2016, 1, 3))
    assert source.corporate_actions(BBCA, *span) == [
        CashDividend(BBCA, date(2015, 6, 1), Decimal(50))
    ]
    assert counting.asked == [span]
    assert cache.fetched_actions(BBCA) == [span]
