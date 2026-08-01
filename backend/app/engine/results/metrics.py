"""Pure performance metric functions.

Every metric is computed from trade history and capital inputs only. Formulas
are documented in ``docs/metrics.md``.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.domain.money import round_money, round_percent
from app.engine.execution.trade import Trade
from app.engine.results.metrics_result import EquityPoint, PerformanceMetrics


class MetricsEngine:
    """Derives performance statistics from completed trades."""

    def compute(
        self,
        *,
        trades: Sequence[Trade],
        initial_capital: float,
        final_cash: float,
    ) -> tuple[PerformanceMetrics, tuple[EquityPoint, ...]]:
        equity_history = self._equity_history(trades, initial_capital)
        metrics = self._metrics(trades, initial_capital, final_cash)
        return metrics, equity_history

    def _equity_history(
        self, trades: Sequence[Trade], initial_capital: float
    ) -> tuple[EquityPoint, ...]:
        equity = initial_capital
        points: list[EquityPoint] = []
        for trade in trades:
            equity = round_money(equity + trade.net_pnl)
            points.append(
                EquityPoint(
                    trade_number=trade.seq,
                    equity=equity,
                    timestamp=trade.exit_ts,
                )
            )
        return tuple(points)

    def _metrics(
        self,
        trades: Sequence[Trade],
        initial_capital: float,
        final_cash: float,
    ) -> PerformanceMetrics:
        total_trades = len(trades)
        winners = [trade for trade in trades if trade.net_pnl > 0]
        losers = [trade for trade in trades if trade.net_pnl < 0]

        gross_profit = round_money(sum(trade.net_pnl for trade in winners))
        gross_loss = round_money(abs(sum(trade.net_pnl for trade in losers)))
        net_profit = round_money(final_cash - initial_capital)

        winning_trades = len(winners)
        losing_trades = len(losers)
        win_rate_pct = round_percent((winning_trades / total_trades * 100) if total_trades else 0.0)

        average_win = round_money(gross_profit / winning_trades) if winning_trades else 0.0
        average_loss = round_money(gross_loss / losing_trades) if losing_trades else 0.0
        largest_win = round_money(max((trade.net_pnl for trade in winners), default=0.0))
        largest_loss = round_money(abs(min((trade.net_pnl for trade in losers), default=0.0)))

        if gross_loss > 0:
            profit_factor = round_money(gross_profit / gross_loss)
        elif gross_profit > 0:
            profit_factor = 0.0
        else:
            profit_factor = 0.0

        average_trade = round_money(net_profit / total_trades) if total_trades else 0.0
        expectancy = average_trade
        average_holding_bars = (
            round_money(sum(trade.bars_held for trade in trades) / total_trades)
            if total_trades
            else 0.0
        )

        commission_paid = round_money(sum(trade.commission for trade in trades))
        slippage_cost = round_money(sum(trade.slippage_cost for trade in trades))
        return_pct = (
            round_percent((final_cash - initial_capital) / initial_capital * 100)
            if initial_capital > 0
            else 0.0
        )
        trailing_exits = [
            trade for trade in trades if (trade.exit_reason or "") == "trailing_stop"
        ]
        trailing_count = len(trailing_exits)
        trailing_profits = [trade.net_pnl for trade in trailing_exits]
        trailing_winners = [profit for profit in trailing_profits if profit > 0]
        trailing_average_profit = (
            round_money(sum(trailing_profits) / trailing_count) if trailing_count else 0.0
        )
        trailing_largest = round_money(max(trailing_profits, default=0.0))
        trailing_smallest = round_money(min(trailing_profits, default=0.0))
        trailing_win_rate = (
            round_percent(len(trailing_winners) / trailing_count * 100) if trailing_count else 0.0
        )
        trailing_average_bars = (
            round_money(sum(trade.bars_held for trade in trailing_exits) / trailing_count)
            if trailing_count
            else 0.0
        )

        return PerformanceMetrics(
            net_profit=net_profit,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            win_rate_pct=win_rate_pct,
            average_win=average_win,
            average_loss=average_loss,
            largest_win=largest_win,
            largest_loss=largest_loss,
            profit_factor=profit_factor,
            expectancy=expectancy,
            average_trade=average_trade,
            average_holding_bars=average_holding_bars,
            commission_paid=commission_paid,
            slippage_cost=slippage_cost,
            final_cash=round_money(final_cash),
            return_pct=return_pct,
            trailing_exit_count=trailing_count,
            trailing_exit_average_profit=trailing_average_profit,
            trailing_exit_largest_profit=trailing_largest,
            trailing_exit_smallest_profit=trailing_smallest,
            trailing_exit_win_rate_pct=trailing_win_rate,
            trailing_exit_average_bars_held=trailing_average_bars,
        )
