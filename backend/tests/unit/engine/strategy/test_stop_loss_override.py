"""Tests for run-level stop-loss overrides."""

from __future__ import annotations

from app.engine.strategy.risk import (
    AtrDistance,
    PercentDistance,
    RiskRules,
    StopLossOverride,
    apply_stop_loss_override,
)


def test_apply_percent_override_replaces_stop_only() -> None:
    rules = RiskRules(
        stop_loss=AtrDistance(2.0),
        take_profit=PercentDistance(4.0),
    )

    updated = apply_stop_loss_override(rules, StopLossOverride(mode="percent", percent=1.5))

    assert isinstance(updated.stop_loss, PercentDistance)
    assert updated.stop_loss.percent == 1.5
    assert isinstance(updated.take_profit, PercentDistance)


def test_apply_atr_override() -> None:
    rules = RiskRules(stop_loss=PercentDistance(2.0))

    updated = apply_stop_loss_override(rules, StopLossOverride(mode="atr", atr_multiple=3.0))

    assert isinstance(updated.stop_loss, AtrDistance)
    assert updated.stop_loss.multiple == 3.0


def test_apply_disabled_override() -> None:
    rules = RiskRules(stop_loss=PercentDistance(2.0))

    updated = apply_stop_loss_override(rules, StopLossOverride(mode="disabled"))

    assert updated.stop_loss is None
