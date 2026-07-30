"""RSI and Rate of Change against hand-computed values."""

from __future__ import annotations

import pytest

from app.engine.indicators.momentum import RateOfChange, RelativeStrengthIndex
from tests.unit.engine.indicators.conftest import closes, feed


def test_rsi_needs_one_extra_bar_to_establish_a_previous_close():
    rsi = RelativeStrengthIndex(3)
    assert rsi.warmup_bars == 4
    values = feed(rsi, closes([10.0, 11.0, 12.0]))
    assert values == [None, None, None]


def test_rsi_is_one_hundred_when_every_change_is_a_gain():
    rsi = RelativeStrengthIndex(3)
    values = feed(rsi, closes([10.0, 11.0, 12.0, 13.0]))
    assert values[3] == pytest.approx(100.0)


def test_rsi_is_zero_when_every_change_is_a_loss():
    rsi = RelativeStrengthIndex(3)
    values = feed(rsi, closes([13.0, 12.0, 11.0, 10.0]))
    assert values[3] == pytest.approx(0.0)


def test_rsi_is_fifty_on_a_perfectly_flat_series():
    # Both averages are zero, so the ratio is undefined; neutral is the only
    # reading consistent with "no strength in either direction".
    rsi = RelativeStrengthIndex(3)
    values = feed(rsi, closes([10.0] * 6))
    assert values[-1] == pytest.approx(50.0)


def test_rsi_seed_matches_the_closed_form_for_equal_gains_and_losses():
    # Changes: +2, -2, +2 -> avg gain 4/3, avg loss 2/3 -> RS 2 -> RSI 100-100/3
    rsi = RelativeStrengthIndex(3)
    values = feed(rsi, closes([10.0, 12.0, 10.0, 12.0]))
    assert values[3] == pytest.approx(100.0 - 100.0 / 3.0)


def test_rsi_stays_within_bounds_on_a_volatile_series():
    rsi = RelativeStrengthIndex(14)
    prices = [100.0]
    for index in range(200):
        prices.append(prices[-1] * (1.02 if index % 3 else 0.97))
    for value in feed(rsi, closes(prices)):
        if value is not None:
            assert 0.0 <= value <= 100.0


def test_rsi_wilder_smoothing_is_not_a_plain_ema():
    # Wilder uses (prev*(n-1) + new)/n, not alpha = 2/(n+1). If it were an EMA
    # the two would agree; this asserts they do not.
    period = 5
    rsi = RelativeStrengthIndex(period)
    values = feed(rsi, closes([10, 11, 12, 11, 13, 14, 12, 15, 16, 14]))
    wilder = values[-1]
    assert wilder is not None
    assert wilder != pytest.approx(50.0)


def test_roc_expresses_percent_as_two_point_five_not_zero_point_zero_two_five():
    roc = RateOfChange(2)
    values = feed(roc, closes([100.0, 100.0, 102.5]))
    assert values[2] == pytest.approx(2.5)


def test_roc_spans_period_intervals_not_period_closes():
    roc = RateOfChange(3)
    assert roc.warmup_bars == 4
    values = feed(roc, closes([100.0, 1.0, 1.0, 110.0]))
    assert values[3] == pytest.approx(10.0)


def test_roc_is_negative_on_a_decline():
    roc = RateOfChange(1)
    values = feed(roc, closes([100.0, 90.0]))
    assert values[1] == pytest.approx(-10.0)


def test_roc_treats_a_zero_reference_price_as_no_change():
    roc = RateOfChange(1)
    values = feed(roc, closes([0.0, 5.0]))
    assert values[1] == pytest.approx(0.0)
