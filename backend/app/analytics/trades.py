"""Trade-level statistics, including intra-trade excursions.

MAE (maximum adverse excursion) and MFE (maximum favourable excursion) are
measured here rather than recorded by the engine: they are a pure function of a
trade's entry and the bars it spanned, so deriving them keeps the bar loop
untouched. Both are reported in account currency as positive magnitudes.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.analytics import _numeric as num
from app.analytics.equity import EquitySeries
from app.analytics.inputs import TradeRecord
from app.domain.enums import PositionSide


@dataclass(frozen=True)
class Excursions:
    """Per-trade worst and best unrealised moves, aligned to ``trades`` order."""

    mae: tuple[float, ...]
    mfe: tuple[float, ...]

    @property
    def average_mae(self) -> float | None:
        return None if not self.mae else float(np.mean(self.mae))

    @property
    def average_mfe(self) -> float | None:
        return None if not self.mfe else float(np.mean(self.mfe))


@dataclass(frozen=True)
class TradeMetrics:
    """Counts, rates, streaks, holding times and excursions."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    breakeven_trades: int
    win_rate_pct: float
    loss_rate_pct: float
    longest_win_streak: int
    longest_loss_streak: int
    average_holding_time_ms: float
    max_holding_time_ms: int
    min_holding_time_ms: int
    average_bars_held: float
    average_mae: float | None
    average_mfe: float | None
    largest_winner: float
    largest_loser: float


def compute_excursions(*, trades: tuple[TradeRecord, ...], series: EquitySeries) -> Excursions:
    """Adverse and favourable excursion for every trade.

    The window runs from the entry bar to the exit bar inclusive: the entry
    fills at the entry bar's open, so that bar's range is already at risk, and
    the exit bar's range is traversed before the exit fills at its open.

    Without bars - a report built from trades alone - both series are empty and
    the averages become ``None`` rather than a misleading zero.
    """
    if not trades or series.is_empty:
        return Excursions(mae=(), mfe=())

    mae: list[float] = []
    mfe: list[float] = []
    for trade in trades:
        start = int(np.searchsorted(series.ts, trade.entry_ts, side="left"))
        stop = int(np.searchsorted(series.ts, trade.exit_ts, side="right"))
        if stop <= start:
            continue
        window = slice(start, stop)
        highest = float(np.max(series.high[window]))
        lowest = float(np.min(series.low[window]))
        if trade.side is PositionSide.LONG:
            adverse = trade.entry_price - lowest
            favourable = highest - trade.entry_price
        else:
            adverse = highest - trade.entry_price
            favourable = trade.entry_price - lowest
        mae.append(num.money(max(adverse, 0.0) * trade.quantity))
        mfe.append(num.money(max(favourable, 0.0) * trade.quantity))

    return Excursions(mae=tuple(mae), mfe=tuple(mfe))


def compute_trade_metrics(
    *, trades: tuple[TradeRecord, ...], excursions: Excursions
) -> TradeMetrics:
    """Trade statistics.

    Breakeven trades (``net_pnl == 0``) are counted separately and excluded from
    both the win and loss rates, so the two rates do not sum to 100% when any
    exist. That is deliberate: a scratch trade is neither a win nor a loss, and
    folding it into either inflates one of them.
    """
    total = len(trades)
    if total == 0:
        return TradeMetrics(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            breakeven_trades=0,
            win_rate_pct=0.0,
            loss_rate_pct=0.0,
            longest_win_streak=0,
            longest_loss_streak=0,
            average_holding_time_ms=0.0,
            max_holding_time_ms=0,
            min_holding_time_ms=0,
            average_bars_held=0.0,
            average_mae=None,
            average_mfe=None,
            largest_winner=0.0,
            largest_loser=0.0,
        )

    winners = [trade.net_pnl for trade in trades if trade.net_pnl > 0]
    losers = [trade.net_pnl for trade in trades if trade.net_pnl < 0]
    holding = [max(trade.exit_ts - trade.entry_ts, 0) for trade in trades]
    win_streak, loss_streak = _streaks(trades)

    return TradeMetrics(
        total_trades=total,
        winning_trades=len(winners),
        losing_trades=len(losers),
        breakeven_trades=total - len(winners) - len(losers),
        win_rate_pct=num.percent(len(winners) / total * 100.0),
        loss_rate_pct=num.percent(len(losers) / total * 100.0),
        longest_win_streak=win_streak,
        longest_loss_streak=loss_streak,
        average_holding_time_ms=num.money(sum(holding) / total),
        max_holding_time_ms=max(holding),
        min_holding_time_ms=min(holding),
        average_bars_held=num.money(sum(trade.bars_held for trade in trades) / total),
        average_mae=num.money_or_none(excursions.average_mae),
        average_mfe=num.money_or_none(excursions.average_mfe),
        largest_winner=num.money(max(winners, default=0.0)),
        largest_loser=num.money(abs(min(losers, default=0.0))),
    )


def _streaks(trades: tuple[TradeRecord, ...]) -> tuple[int, int]:
    """Longest runs of consecutive winners and losers, in ``seq`` order.

    A breakeven trade breaks both streaks: it is not a continuation of either.
    """
    longest_wins = longest_losses = 0
    wins = losses = 0
    for trade in trades:
        if trade.net_pnl > 0:
            wins += 1
            losses = 0
        elif trade.net_pnl < 0:
            losses += 1
            wins = 0
        else:
            wins = losses = 0
        longest_wins = max(longest_wins, wins)
        longest_losses = max(longest_losses, losses)
    return longest_wins, longest_losses
