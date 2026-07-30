"""True Range, ATR, standard deviation and Bollinger Bands."""

from __future__ import annotations

import math

import pytest

from app.engine.indicators.volatility import (
    AverageTrueRange,
    BollingerBands,
    StandardDeviation,
    true_range,
)
from tests.unit.engine.indicators.conftest import bar, closes, feed, ohlc


def test_true_range_degrades_to_the_bar_range_without_a_previous_close():
    assert true_range(bar(10.0, high=12.0, low=9.0), None) == pytest.approx(3.0)


def test_true_range_uses_the_gap_when_it_exceeds_the_bar_range():
    # Gapped up: high-low is 1 but high-prev_close is 6.
    assert true_range(bar(15.0, high=16.0, low=15.0), 10.0) == pytest.approx(6.0)


def test_true_range_uses_the_downward_gap_too():
    assert true_range(bar(5.0, high=6.0, low=5.0), 12.0) == pytest.approx(7.0)


def test_atr_seeds_with_the_mean_of_the_first_period_true_ranges():
    atr = AverageTrueRange(3)
    bars = ohlc([(10, 12, 10, 11), (11, 13, 11, 12), (12, 14, 12, 13)])
    # TRs: 2 (no prev close), max(2, |13-11|, |11-11|)=2, max(2, |14-12|, |12-12|)=2
    assert feed(atr, bars)[2] == pytest.approx(2.0)


def test_atr_applies_wilders_recursion_not_an_ema():
    atr = AverageTrueRange(2)
    bars = ohlc([(10, 11, 9, 10), (10, 11, 9, 10), (10, 20, 9, 10)])
    values = feed(atr, bars)
    # Seed = mean(2, 2) = 2. Third TR = max(11, |20-10|, |9-10|) = 11.
    # Wilder: (2 * 1 + 11) / 2 = 6.5. An EMA with alpha 2/3 would give 8.
    assert values[2] == pytest.approx(6.5)


def test_atr_is_zero_on_bars_with_no_range_and_no_gaps():
    atr = AverageTrueRange(3)
    assert feed(atr, closes([5.0] * 6))[-1] == pytest.approx(0.0)


def test_atr_warmup_is_period_plus_one():
    assert AverageTrueRange(14).warmup_bars == 15


def test_standard_deviation_is_population_form():
    stddev = StandardDeviation(4)
    values = feed(stddev, closes([2.0, 4.0, 4.0, 6.0]))
    # Population variance 2 -> sqrt(2). The sample form would give sqrt(8/3).
    assert values[3] == pytest.approx(math.sqrt(2.0))


def test_standard_deviation_is_zero_on_a_flat_window():
    stddev = StandardDeviation(3)
    assert feed(stddev, closes([9.0] * 5))[-1] == pytest.approx(0.0)


def test_bollinger_bands_sit_k_deviations_around_the_middle_band():
    bands = BollingerBands(4, 2.0)
    for one in closes([2.0, 4.0, 4.0, 6.0]):
        bands.update(one)
    middle = bands.output("middle")
    upper = bands.output("upper")
    lower = bands.output("lower")
    assert middle == pytest.approx(4.0)
    assert upper == pytest.approx(4.0 + 2.0 * math.sqrt(2.0))
    assert lower == pytest.approx(4.0 - 2.0 * math.sqrt(2.0))


def test_bollinger_percent_b_places_the_close_inside_the_envelope():
    bands = BollingerBands(4, 2.0)
    for one in closes([2.0, 4.0, 4.0, 6.0]):
        bands.update(one)
    percent_b = bands.output("percent_b")
    lower = bands.output("lower")
    upper = bands.output("upper")
    assert percent_b is not None and lower is not None and upper is not None
    assert percent_b == pytest.approx((6.0 - lower) / (upper - lower))
    assert 0.0 < percent_b < 1.0


def test_bollinger_bandwidth_is_span_over_middle():
    bands = BollingerBands(3, 1.0)
    for one in closes([10.0, 12.0, 14.0]):
        bands.update(one)
    upper = bands.output("upper")
    lower = bands.output("lower")
    middle = bands.output("middle")
    assert upper is not None and lower is not None and middle is not None
    assert bands.output("bandwidth") == pytest.approx((upper - lower) / middle)


def test_bollinger_on_a_flat_series_collapses_to_the_mean_with_neutral_percent_b():
    bands = BollingerBands(3, 2.0)
    for one in closes([5.0] * 4):
        bands.update(one)
    assert bands.output("upper") == pytest.approx(5.0)
    assert bands.output("lower") == pytest.approx(5.0)
    # A zero-width band means the close sits exactly on the mean.
    assert bands.output("percent_b") == pytest.approx(0.5)
    assert bands.output("bandwidth") == pytest.approx(0.0)


def test_bollinger_publishes_nothing_until_the_window_is_full():
    bands = BollingerBands(5, 2.0)
    for one in closes([1.0, 2.0, 3.0]):
        bands.update(one)
    assert bands.is_ready is False
    assert bands.snapshot() == {
        "middle": None,
        "upper": None,
        "lower": None,
        "bandwidth": None,
        "percent_b": None,
    }


def test_unknown_output_name_is_rejected_with_the_available_names():
    bands = BollingerBands(3, 2.0)
    with pytest.raises(KeyError, match="has no output"):
        bands.output("signal")
