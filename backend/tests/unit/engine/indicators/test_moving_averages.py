"""SMA, EMA, WMA and MACD against hand-computed values."""

from __future__ import annotations

import pytest

from app.engine.indicators.base import RollingWindow
from app.engine.indicators.trend import (
    ExponentialMovingAverage,
    Macd,
    SimpleMovingAverage,
    WeightedMovingAverage,
    _source_value,
)
from tests.unit.engine.indicators.conftest import bar, closes, feed


def test_sma_publishes_nothing_until_the_window_is_full():
    sma = SimpleMovingAverage(3)
    assert feed(sma, closes([1.0, 2.0])) == [None, None]


def test_sma_matches_the_arithmetic_mean_of_the_window():
    sma = SimpleMovingAverage(3)
    values = feed(sma, closes([2.0, 4.0, 6.0, 8.0]))
    assert values[2] == pytest.approx(4.0)  # (2+4+6)/3
    assert values[3] == pytest.approx(6.0)  # (4+6+8)/3


def test_sma_of_a_flat_series_equals_the_level():
    sma = SimpleMovingAverage(4)
    assert feed(sma, closes([7.0] * 6))[-1] == pytest.approx(7.0)


def test_sma_reads_alternative_price_sources():
    sma = SimpleMovingAverage(1, source="high")
    sma.update(bar(10.0, high=12.0, low=9.0))
    assert sma.value == pytest.approx(12.0)


def test_ema_is_seeded_with_the_sma_of_the_first_period_closes():
    # Seeding from the SMA (not the first close) is what makes two runs over
    # overlapping date ranges agree.
    ema = ExponentialMovingAverage(3)
    values = feed(ema, closes([1.0, 2.0, 3.0]))
    assert values[:2] == [None, None]
    assert values[2] == pytest.approx(2.0)


def test_ema_applies_alpha_two_over_period_plus_one():
    ema = ExponentialMovingAverage(3)  # alpha = 0.5
    values = feed(ema, closes([1.0, 2.0, 3.0, 5.0]))
    # 2.0 + 0.5 * (5 - 2) = 3.5
    assert values[3] == pytest.approx(3.5)


def test_ema_converges_toward_a_constant_series():
    ema = ExponentialMovingAverage(5)
    values = feed(ema, closes([1.0] * 5 + [10.0] * 60))
    assert values[-1] == pytest.approx(10.0, abs=1e-6)


def test_wma_weights_the_newest_close_most_heavily():
    wma = WeightedMovingAverage(3)
    values = feed(wma, closes([1.0, 2.0, 3.0]))
    # (1*1 + 2*2 + 3*3) / (1+2+3) = 14/6
    assert values[2] == pytest.approx(14.0 / 6.0)


def test_wma_differs_from_sma_on_a_trend():
    bars = closes([1.0, 2.0, 3.0, 4.0])
    wma = feed(WeightedMovingAverage(4), bars)[-1]
    sma = feed(SimpleMovingAverage(4), bars)[-1]
    assert wma is not None and sma is not None
    assert wma > sma


def test_macd_line_is_the_difference_of_its_two_emas():
    macd = Macd(2, 4, 2)
    bars = closes([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0])
    fast = ExponentialMovingAverage(2)
    slow = ExponentialMovingAverage(4)
    for one in bars:
        macd.update(one)
        fast.update(one)
        slow.update(one)
    assert fast.value is not None and slow.value is not None
    assert macd.output("line") == pytest.approx(fast.value - slow.value)


def test_macd_histogram_is_line_minus_signal():
    macd = Macd(3, 6, 3)
    for one in closes([float(i) for i in range(1, 30)]):
        macd.update(one)
    line = macd.output("line")
    signal = macd.output("signal")
    assert line is not None and signal is not None
    assert macd.output("histogram") == pytest.approx(line - signal)


def test_macd_warmup_accounts_for_the_signal_ema_seeding_from_the_line():
    macd = Macd(3, 6, 3)
    assert macd.warmup_bars == 6 + 3 - 1

    # `is_ready` covers every output, so it flips only once the signal line
    # exists - which is later than the raw MACD line becoming available.
    readiness = []
    for one in closes([float(i) for i in range(1, 20)]):
        macd.update(one)
        readiness.append(macd.is_ready)

    assert readiness[macd.warmup_bars - 2] is False
    assert readiness[macd.warmup_bars - 1] is True


def test_macd_is_negative_on_a_falling_series():
    macd = Macd(3, 6, 3)
    for one in closes([float(100 - i) for i in range(40)]):
        macd.update(one)
    line = macd.output("line")
    assert line is not None and line < 0


def test_rolling_window_rejects_a_zero_size():
    with pytest.raises(ValueError, match="at least 1"):
        RollingWindow(0)


def test_rolling_window_variance_is_population_not_sample():
    window = RollingWindow(4)
    for value in (2.0, 4.0, 4.0, 6.0):
        window.append(value)
    # mean 4, deviations -2,0,0,2 -> population variance 8/4 = 2
    assert window.variance() == pytest.approx(2.0)


def test_rolling_window_variance_is_never_negative_on_a_flat_window():
    window = RollingWindow(3)
    for _ in range(3):
        window.append(1e8)
    variance = window.variance()
    assert variance is not None and variance >= 0.0


def test_rolling_window_tracks_extremes_and_eviction():
    window = RollingWindow(3)
    for value in (5.0, 1.0, 9.0, 3.0):
        window.append(value)
    assert window.items == (1.0, 9.0, 3.0)
    assert window.highest() == 9.0
    assert window.lowest() == 1.0
    assert window.total == pytest.approx(13.0)


def test_unknown_price_source_is_rejected_loudly():
    with pytest.raises(ValueError, match="Unknown price source"):
        _source_value(bar(1.0), "typical")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("close", 4.0),
        ("open", 1.0),
        ("high", 5.0),
        ("low", 0.0),
        ("hl2", 2.5),
        ("hlc3", 3.0),
        ("ohlc4", 2.5),
    ],
)
def test_price_sources(source: str, expected: float) -> None:
    one = bar(4.0, open_=1.0, high=5.0, low=0.0)
    assert _source_value(one, source) == pytest.approx(expected)
