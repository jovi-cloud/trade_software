"""Statistical quality-of-edge measures.

These answer a different question from the return and risk groups: not "how much
did it make" but "how much of that is signal". All four are ``None`` when the
sample is too small to support them, rather than a number that would be read as
a finding.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from app.analytics import _numeric as num
from app.analytics.inputs import TradeRecord
from app.analytics.returns import ReturnMetrics
from app.analytics.trades import Excursions, TradeMetrics

#: Below this many trades, SQN and the Z score describe noise. Van Tharp's
#: original SQN guidance assumes at least 30 trades; the runs test needs a
#: comparable sample before its normal approximation holds.
MIN_SAMPLE_TRADES = 30


@dataclass(frozen=True)
class StatisticalMetrics:
    """System quality, position sizing guidance, and streak dependency."""

    sqn: float | None
    kelly_pct: float | None
    z_score: float | None
    edge_ratio: float | None


def compute_statistical_metrics(
    *,
    trades: tuple[TradeRecord, ...],
    trade_metrics: TradeMetrics,
    returns: ReturnMetrics,
    excursions: Excursions,
) -> StatisticalMetrics:
    """Assemble the statistics group."""
    return StatisticalMetrics(
        sqn=_sqn(trades),
        kelly_pct=_kelly_pct(trade_metrics, returns),
        z_score=_z_score(trades, trade_metrics),
        edge_ratio=_edge_ratio(excursions),
    )


def _sqn(trades: tuple[TradeRecord, ...]) -> float | None:
    """System Quality Number: ``sqrt(N) * mean(pnl) / stdev(pnl)``.

    Van Tharp's measure - expectancy scaled by consistency and sample size. The
    sample-size gate matters here: ``sqrt(N)`` rewards trade count directly, so
    a five-trade run would otherwise post a flattering number.
    """
    if len(trades) < MIN_SAMPLE_TRADES:
        return None
    pnl = np.fromiter((trade.net_pnl for trade in trades), dtype=np.float64, count=len(trades))
    deviation = num.sample_stdev(pnl)
    if deviation is None:
        return None
    return num.ratio(math.sqrt(len(trades)) * float(np.mean(pnl)) / deviation)


def _kelly_pct(metrics: TradeMetrics, returns: ReturnMetrics) -> float | None:
    """Kelly fraction from win rate and payoff ratio, as a percent of equity.

    ``win_rate - loss_rate / payoff_ratio``. This is the theoretical
    growth-optimal fraction, not a recommendation: it assumes the observed edge
    is the true edge and tolerates drawdowns most researchers will not. A
    negative result means the edge is not exploitable by sizing at all.
    """
    if metrics.total_trades == 0 or returns.average_loss == 0:
        return None
    payoff = num.divide(returns.average_win, returns.average_loss)
    if payoff is None or payoff == 0:
        return None
    win_rate = metrics.win_rate_pct / 100.0
    loss_rate = metrics.loss_rate_pct / 100.0
    return num.percent((win_rate - loss_rate / payoff) * 100.0)


def _z_score(trades: tuple[TradeRecord, ...], metrics: TradeMetrics) -> float | None:
    """Wald-Wolfowitz runs test on the win/loss sequence.

    Measures whether wins and losses cluster more (negative Z) or less
    (positive Z) than independent coin flips would produce. |Z| > 1.96 is the
    conventional 95% significance threshold. Streak dependence is what decides
    whether "stop trading after two losses" is an edge or superstition.

    Breakeven trades carry no outcome, so they are dropped from the sequence
    entirely rather than breaking a run - which means the sample here can be
    smaller than ``total_trades``.
    """
    wins = metrics.winning_trades
    losses = metrics.losing_trades
    total = wins + losses
    if total < MIN_SAMPLE_TRADES or wins == 0 or losses == 0:
        return None

    runs = _count_runs(trades)
    expected = 2.0 * wins * losses
    variance = expected * (expected - total) / (total - 1)
    if variance <= 0:
        return None
    return num.ratio((total * (runs - 0.5) - expected) / math.sqrt(variance))


def _count_runs(trades: tuple[TradeRecord, ...]) -> int:
    """Number of streaks in the win/loss sequence, ignoring breakeven trades."""
    runs = 0
    previous: bool | None = None
    for trade in trades:
        if trade.net_pnl == 0:
            continue
        is_win = trade.net_pnl > 0
        if is_win is not previous:
            runs += 1
            previous = is_win
    return runs


def _edge_ratio(excursions: Excursions) -> float | None:
    """Mean favourable excursion over mean adverse excursion.

    Above 1.0 means trades ran further in favour than against before closing -
    evidence the entry has an edge independent of how the exit was timed.
    """
    average_mfe = excursions.average_mfe
    average_mae = excursions.average_mae
    if average_mfe is None or average_mae is None:
        return None
    return num.ratio(num.divide(average_mfe, average_mae))
