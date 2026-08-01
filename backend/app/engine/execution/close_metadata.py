"""Metadata captured when a position is closed."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.engine.strategy.risk import TradeRiskState


@dataclass(frozen=True, slots=True)
class TradeCloseMetadata:
    """Risk analytics attached to a completed round trip."""

    exit_reason: str
    initial_stop_level: float | None = None
    trailing_stop_at_exit: float | None = None
    highest_price_reached: float | None = None
    lowest_price_reached: float | None = None
    max_favorable_excursion: float | None = None
    max_adverse_excursion: float | None = None
    max_profit: float | None = None
    max_drawdown_in_trade: float | None = None


def metadata_from_risk_state(
    risk_state: TradeRiskState | None,
    *,
    exit_reason: str,
) -> TradeCloseMetadata:
    """Snapshot per-trade risk analytics at the moment of exit."""
    if risk_state is None:
        return TradeCloseMetadata(exit_reason=exit_reason)
    trailing_at_exit = (
        risk_state.trailing.current_trailing_stop
        if risk_state.trailing is not None
        else None
    )
    return TradeCloseMetadata(
        exit_reason=exit_reason,
        initial_stop_level=risk_state.stop_level,
        trailing_stop_at_exit=trailing_at_exit,
        highest_price_reached=risk_state.highest_price_since_entry,
        lowest_price_reached=risk_state.lowest_price_since_entry,
        max_favorable_excursion=risk_state.max_favorable_excursion,
        max_adverse_excursion=risk_state.max_adverse_excursion,
        max_profit=risk_state.max_profit,
        max_drawdown_in_trade=risk_state.max_drawdown_in_trade,
    )
