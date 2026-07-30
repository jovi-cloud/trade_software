"""The indicator registry is the vocabulary the UI and docs read from."""

from __future__ import annotations

import pytest

from app.engine.indicators.base import Indicator
from app.engine.indicators.registry import get_indicator, indicator_names, list_indicators


def test_registry_is_not_empty_and_names_are_unique():
    infos = list_indicators()
    assert len(infos) >= 15
    names = [info.name for info in infos]
    assert len(names) == len(set(names))


def test_every_entry_is_fully_described():
    for info in list_indicators():
        assert info.name.islower()
        assert info.label
        assert info.category
        assert info.description.endswith(".")
        assert info.outputs


def test_get_indicator_resolves_by_name():
    info = get_indicator("rsi")
    assert info.label == "Relative Strength Index"
    assert info.arguments == ("period",)


def test_unknown_indicator_lists_the_available_names():
    with pytest.raises(KeyError, match="Unknown indicator"):
        get_indicator("stochastic")


def test_declared_outputs_match_what_the_class_publishes():
    # The docs and the parameter editor read `outputs`; a mismatch would offer a
    # trader an output name that resolves to nothing at runtime.
    for info in list_indicators():
        assert info.outputs == info.factory.outputs  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("name", "args", "kwargs"),
    [
        ("sma", (3,), {}),
        ("ema", (3,), {}),
        ("wma", (3,), {}),
        ("macd", (2, 4, 2), {}),
        ("donchian", (3,), {}),
        ("supertrend", (3, 2.0), {}),
        ("rsi", (3,), {}),
        ("roc", (3,), {}),
        ("atr", (3,), {}),
        ("stddev", (3,), {}),
        ("bbands", (3, 2.0), {}),
        ("vwap", ("UTC",), {}),
        ("rolling_vwap", (3,), {}),
        ("obv", (), {}),
        (
            "opening_range",
            (),
            {"timezone": "UTC", "session_start": "09:15", "range_minutes": 15},
        ),
    ],
)
def test_every_registered_indicator_can_be_constructed_and_driven(name, args, kwargs):
    from tests.unit.engine.indicators.conftest import closes

    indicator = get_indicator(name).create(*args, **kwargs)
    assert isinstance(indicator, Indicator)
    for one in closes([10.0, 11.0, 12.0, 11.0, 13.0, 14.0, 15.0]):
        indicator.update(one)
    assert indicator.bars_seen == 7
    assert set(indicator.snapshot()) == set(indicator.outputs)


def test_indicator_names_covers_the_full_registry():
    assert set(indicator_names()) == {info.name for info in list_indicators()}
