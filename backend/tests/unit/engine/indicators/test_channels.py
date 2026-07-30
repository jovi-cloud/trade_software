"""Donchian channel and SuperTrend."""

from __future__ import annotations

import pytest

from app.engine.indicators.trend import DonchianChannel, SuperTrend
from tests.unit.engine.indicators.conftest import closes, ohlc


def test_donchian_spans_the_highest_high_and_lowest_low():
    channel = DonchianChannel(3)
    for one in ohlc([(10, 12, 8, 11), (11, 15, 10, 14), (14, 13, 6, 9)]):
        channel.update(one)
    assert channel.output("upper") == pytest.approx(15.0)
    assert channel.output("lower") == pytest.approx(6.0)
    assert channel.output("middle") == pytest.approx(10.5)
    assert channel.output("width") == pytest.approx(9.0)


def test_donchian_excluding_the_current_bar_reports_the_prior_window():
    channel = DonchianChannel(2, exclude_current=True)
    bars = ohlc([(10, 12, 8, 11), (11, 15, 10, 14), (14, 30, 6, 29)])
    uppers = []
    for one in bars:
        channel.update(one)
        uppers.append(channel.output("upper"))

    assert uppers[0] is None  # nothing in the window yet
    assert uppers[1] is None  # only one prior bar
    # The third bar's own 30 high is excluded, so the channel is still 15.
    assert uppers[2] == pytest.approx(15.0)


def test_donchian_excluding_the_current_bar_needs_one_more_warmup_bar():
    assert DonchianChannel(20).warmup_bars == 20
    assert DonchianChannel(20, exclude_current=True).warmup_bars == 21


def test_donchian_publishes_nothing_until_the_window_is_full():
    channel = DonchianChannel(4)
    for one in closes([1.0, 2.0]):
        channel.update(one)
    assert channel.is_ready is False


def test_supertrend_publishes_nothing_while_atr_warms_up():
    supertrend = SuperTrend(5, 2.0)
    for one in closes([10.0, 11.0, 12.0]):
        supertrend.update(one)
    assert supertrend.value is None
    assert supertrend.output("direction") is None


def test_supertrend_holds_an_uptrend_while_price_rises():
    supertrend = SuperTrend(3, 1.0)
    for one in closes([float(100 + i) for i in range(30)]):
        supertrend.update(one)
    assert supertrend.output("direction") == pytest.approx(1.0)
    line = supertrend.value
    assert line is not None
    # In an uptrend the published line is the lower band, below price.
    assert line < 100 + 29


def test_supertrend_flips_to_a_downtrend_on_a_sustained_decline():
    supertrend = SuperTrend(3, 1.0)
    prices = [float(100 + i) for i in range(25)] + [float(124 - 4 * i) for i in range(1, 25)]
    directions = []
    for one in closes(prices):
        supertrend.update(one)
        directions.append(supertrend.output("direction"))

    assert directions[24] == pytest.approx(1.0)
    assert directions[-1] == pytest.approx(-1.0)


def test_supertrend_bands_only_ratchet_in_the_trend_direction():
    # The lower band must never fall while price holds above it: that ratchet is
    # what makes the line usable as a trailing stop.
    supertrend = SuperTrend(3, 1.5)
    lowers: list[float] = []
    for one in closes([float(100 + i) for i in range(40)]):
        supertrend.update(one)
        lower = supertrend.output("lower")
        if lower is not None:
            lowers.append(lower)

    assert lowers == sorted(lowers)


def test_supertrend_warmup_is_atr_period_plus_one():
    assert SuperTrend(10, 3.0).warmup_bars == 11
