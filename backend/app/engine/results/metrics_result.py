"""Performance metric dataclasses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EquityPoint:
    """Account equity after one closed trade."""

    trade_number: int
    equity: float
    timestamp: int


@dataclass(frozen=True)
class PerformanceMetrics:
    """Headline statistics derived from completed trades."""

    net_profit: float
    gross_profit: float
    gross_loss: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float
    profit_factor: float
    expectancy: float
    average_trade: float
    average_holding_bars: float
    commission_paid: float
    slippage_cost: float
    final_cash: float
    return_pct: float
    trailing_exit_count: int = 0
    trailing_exit_average_profit: float = 0.0
    trailing_exit_largest_profit: float = 0.0
    trailing_exit_smallest_profit: float = 0.0
    trailing_exit_win_rate_pct: float = 0.0
    trailing_exit_average_bars_held: float = 0.0
