"""Session clock, opening range, VWAP and OBV."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.engine.bars import Bar
from app.engine.errors import EngineError
from app.engine.indicators.session import (
    SESSION_TIMEZONES,
    OpeningRange,
    SessionClock,
    minutes_of_day,
    resolve_zone,
)
from app.engine.indicators.volume import (
    OnBalanceVolume,
    RollingVwap,
    SessionVwap,
    typical_price,
)
from tests.unit.engine.indicators.conftest import bar, closes, feed

KOLKATA = ZoneInfo("Asia/Kolkata")


def local_bars(
    *,
    start_local: datetime,
    count: int,
    minutes: int = 5,
    price: float = 100.0,
    volume: float = 1_000.0,
) -> list[Bar]:
    """Bars stamped from an exchange-local wall clock, stored as UTC epoch ms."""
    bars: list[Bar] = []
    moment = start_local
    for _ in range(count):
        bars.append(
            Bar(
                ts=int(moment.timestamp() * 1000),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=volume,
            )
        )
        moment += timedelta(minutes=minutes)
    return bars


# -- session clock ---------------------------------------------------------


def test_minutes_of_day_parses_a_validated_time_string():
    assert minutes_of_day("09:15") == 9 * 60 + 15
    assert minutes_of_day("00:00") == 0
    assert minutes_of_day("23:59") == 23 * 60 + 59


def test_resolve_zone_rejects_an_unknown_timezone_as_an_engine_error():
    with pytest.raises(EngineError, match="Unknown session timezone"):
        resolve_zone("Mars/Olympus_Mons")


def test_every_offered_session_timezone_resolves():
    # The parameter editor renders these as a dropdown, so an unresolvable one
    # would be a runtime failure a trader could select.
    for name, _label in SESSION_TIMEZONES:
        assert resolve_zone(name) is not None


def test_session_clock_converts_utc_bars_to_exchange_local_time():
    clock = SessionClock("Asia/Kolkata")
    bars = local_bars(start_local=datetime(2024, 3, 1, 9, 15, tzinfo=KOLKATA), count=1)
    clock.advance(bars[0])
    assert clock.minutes_into_day == 9 * 60 + 15
    assert clock.session_date == "2024-03-01"


def test_session_clock_flags_the_first_bar_of_each_local_session():
    clock = SessionClock("Asia/Kolkata")
    day_one = local_bars(start_local=datetime(2024, 3, 1, 9, 15, tzinfo=KOLKATA), count=3)
    day_two = local_bars(start_local=datetime(2024, 3, 2, 9, 15, tzinfo=KOLKATA), count=2)

    flags = [clock.advance(one) for one in (*day_one, *day_two)]
    assert flags == [True, False, False, True, False]


def test_session_clock_counts_bars_within_the_session():
    clock = SessionClock("UTC")
    for one in local_bars(start_local=datetime(2024, 3, 1, 9, 0, tzinfo=ZoneInfo("UTC")), count=4):
        clock.advance(one)
    assert clock.bars_in_session == 4


def test_session_clock_compares_against_wall_clock_times():
    clock = SessionClock("Asia/Kolkata")
    clock.advance(local_bars(start_local=datetime(2024, 3, 1, 15, 20, tzinfo=KOLKATA), count=1)[0])
    assert clock.is_at_or_after("15:15") is True
    assert clock.is_before("15:15") is False


def test_session_clock_read_before_the_first_bar_fails_loudly():
    clock = SessionClock("UTC")
    with pytest.raises(EngineError, match="before the first bar"):
        _ = clock.local_time


# -- opening range ---------------------------------------------------------


def test_opening_range_publishes_nothing_while_the_window_is_forming():
    opening = OpeningRange(timezone="Asia/Kolkata", session_start="09:15", range_minutes=15)
    forming = local_bars(start_local=datetime(2024, 3, 1, 9, 15, tzinfo=KOLKATA), count=3)
    for one in forming:
        opening.update(one)
        # 09:15, 09:20, 09:25 are all inside the 15-minute window.
        assert opening.output("high") is None
    assert opening.is_complete is False


def test_opening_range_reports_the_window_extremes_once_it_closes():
    opening = OpeningRange(timezone="Asia/Kolkata", session_start="09:15", range_minutes=15)
    start = datetime(2024, 3, 1, 9, 15, tzinfo=KOLKATA)
    prices = [100.0, 104.0, 98.0, 101.0]  # last bar is 09:30, outside the window
    bars = []
    for index, price in enumerate(prices):
        moment = start + timedelta(minutes=5 * index)
        bars.append(
            Bar(
                ts=int(moment.timestamp() * 1000),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=100.0,
            )
        )
    for one in bars:
        opening.update(one)

    assert opening.is_complete is True
    assert opening.output("high") == pytest.approx(105.0)  # 104 + 1
    assert opening.output("low") == pytest.approx(97.0)  # 98 - 1
    assert opening.output("middle") == pytest.approx(101.0)
    assert opening.output("width") == pytest.approx(8.0)


def test_opening_range_resets_at_each_new_session():
    opening = OpeningRange(timezone="Asia/Kolkata", session_start="09:15", range_minutes=10)
    day_one = local_bars(start_local=datetime(2024, 3, 1, 9, 15, tzinfo=KOLKATA), count=6)
    for one in day_one:
        opening.update(one)
    assert opening.is_complete is True

    first_of_day_two = local_bars(start_local=datetime(2024, 3, 2, 9, 15, tzinfo=KOLKATA), count=1)[
        0
    ]
    opening.update(first_of_day_two)
    assert opening.is_complete is False
    assert opening.output("high") is None


def test_opening_range_stays_empty_for_a_session_that_starts_after_the_window():
    # A dataset that begins mid-session must not invent a range from later bars.
    opening = OpeningRange(timezone="Asia/Kolkata", session_start="09:15", range_minutes=15)
    late = local_bars(start_local=datetime(2024, 3, 1, 11, 0, tzinfo=KOLKATA), count=4)
    for one in late:
        opening.update(one)
    assert opening.is_complete is False
    assert opening.output("high") is None


def test_opening_range_declares_no_bar_based_warmup():
    # Its readiness is driven by the wall clock, not a bar count.
    opening = OpeningRange(timezone="UTC", session_start="09:15", range_minutes=15)
    assert opening.warmup_bars == 0


# -- VWAP ------------------------------------------------------------------


def test_typical_price_is_the_mean_of_high_low_close():
    assert typical_price(bar(12.0, high=15.0, low=9.0)) == pytest.approx(12.0)


def test_session_vwap_is_volume_weighted():
    vwap = SessionVwap("UTC")
    start = datetime(2024, 3, 1, 9, 0, tzinfo=ZoneInfo("UTC"))
    heavy = Bar(ts=int(start.timestamp() * 1000), open=10, high=10, low=10, close=10, volume=900)
    light = Bar(
        ts=int((start + timedelta(minutes=5)).timestamp() * 1000),
        open=20,
        high=20,
        low=20,
        close=20,
        volume=100,
    )
    vwap.update(heavy)
    vwap.update(light)
    # (10*900 + 20*100) / 1000 = 11
    assert vwap.value == pytest.approx(11.0)


def test_session_vwap_re_anchors_at_each_session():
    vwap = SessionVwap("Asia/Kolkata")
    for one in local_bars(
        start_local=datetime(2024, 3, 1, 9, 15, tzinfo=KOLKATA), count=4, price=100.0
    ):
        vwap.update(one)
    assert vwap.value == pytest.approx(100.0)

    for one in local_bars(
        start_local=datetime(2024, 3, 2, 9, 15, tzinfo=KOLKATA), count=1, price=200.0
    ):
        vwap.update(one)
    # A VWAP that had not re-anchored would sit near 120, not 200.
    assert vwap.value == pytest.approx(200.0)
    assert vwap.output("session_volume") == pytest.approx(1_000.0)


def test_session_vwap_distance_is_signed_percent():
    vwap = SessionVwap("UTC")
    start = datetime(2024, 3, 1, 9, 0, tzinfo=ZoneInfo("UTC"))
    vwap.update(
        Bar(ts=int(start.timestamp() * 1000), open=100, high=100, low=100, close=100, volume=1)
    )
    vwap.update(
        Bar(
            ts=int((start + timedelta(minutes=5)).timestamp() * 1000),
            open=100,
            high=100,
            low=100,
            close=100,
            volume=0,
        )
    )
    distance = vwap.output("distance_pct")
    assert distance == pytest.approx(0.0)


def test_session_vwap_falls_back_to_typical_price_on_zero_volume():
    # Volume is nullable in the canonical bar schema, so this must not divide by zero.
    vwap = SessionVwap("UTC")
    vwap.update(bar(50.0, high=52.0, low=48.0, volume=0.0))
    assert vwap.value == pytest.approx(50.0)
    assert vwap.output("session_volume") == pytest.approx(0.0)


def test_rolling_vwap_needs_a_full_window():
    vwap = RollingVwap(3)
    for one in closes([10.0, 11.0]):
        vwap.update(one)
    assert vwap.value is None


def test_rolling_vwap_weights_by_volume_within_the_window():
    vwap = RollingVwap(2)
    vwap.update(bar(10.0, volume=100.0))
    vwap.update(bar(20.0, volume=300.0))
    # (10*100 + 20*300) / 400 = 17.5
    assert vwap.value == pytest.approx(17.5)


# -- OBV -------------------------------------------------------------------


def test_obv_adds_volume_on_up_closes_and_subtracts_on_down_closes():
    obv = OnBalanceVolume()
    values = feed(
        obv,
        [
            bar(10.0, volume=100.0),
            bar(11.0, volume=200.0),
            bar(9.0, volume=50.0),
        ],
    )
    assert values[0] is None
    assert values[1] == pytest.approx(200.0)
    assert values[2] == pytest.approx(150.0)


def test_obv_ignores_unchanged_closes():
    obv = OnBalanceVolume()
    values = feed(obv, [bar(10.0, volume=100.0), bar(10.0, volume=500.0)])
    assert values[1] == pytest.approx(0.0)
