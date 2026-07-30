"""Return and profitability metrics.

All profit figures are **realised**: they come from closed round trips, net of
commission and slippage. A position still open when the data ran out contributes
to the equity curve's final mark but not to these numbers - the engine reports
that situation as a run warning, and silently blending an unrealised mark into
"Net Profit" would make a run's headline figure unreproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.analytics import _numeric as num
from app.analytics.inputs import CALENDAR_DAYS_PER_YEAR, MS_PER_DAY, TradeRecord


@dataclass(frozen=True)
class ReturnMetrics:
    """Profitability of the run, in currency and in percent."""

    net_profit: float
    gross_profit: float
    gross_loss: float
    total_return_pct: float
    annualised_return_pct: float | None
    cagr_pct: float | None
    average_trade: float
    average_win: float
    average_loss: float
    profit_factor: float | None
    expectancy: float
    recovery_factor: float | None
    payoff_ratio: float | None
    commission_paid: float
    slippage_cost: float
    final_equity: float


def compute_return_metrics(
    *,
    trades: tuple[TradeRecord, ...],
    initial_capital: float,
    final_equity: float,
    max_drawdown: float,
    elapsed_ms: int,
) -> ReturnMetrics:
    """Return metrics from closed trades.

    Two annualisations are reported because they answer different questions and
    are both quoted in practice:

    * ``annualised_return_pct`` scales the simple total return linearly to a
      year (``total * 365.25 / days``). No compounding assumption.
    * ``cagr_pct`` is the compound rate that turns the starting capital into the
      final equity over the same elapsed calendar time.

    Both are ``None`` for a run shorter than a day, where annualising a handful
    of bars produces a number with no meaning.
    """
    winners = tuple(trade for trade in trades if trade.net_pnl > 0)
    losers = tuple(trade for trade in trades if trade.net_pnl < 0)

    gross_profit = sum(trade.net_pnl for trade in winners)
    gross_loss = abs(sum(trade.net_pnl for trade in losers))
    net_profit = sum(trade.net_pnl for trade in trades)

    average_win = num.divide(gross_profit, len(winners)) or 0.0
    average_loss = num.divide(gross_loss, len(losers)) or 0.0

    total_return_pct = (num.divide(net_profit, initial_capital) or 0.0) * 100.0
    elapsed_days = elapsed_ms / MS_PER_DAY

    return ReturnMetrics(
        net_profit=num.money(net_profit),
        gross_profit=num.money(gross_profit),
        gross_loss=num.money(gross_loss),
        total_return_pct=num.percent(total_return_pct),
        annualised_return_pct=_annualised_return(total_return_pct, elapsed_days),
        cagr_pct=_cagr(initial_capital, final_equity, elapsed_days),
        average_trade=num.money(num.divide(net_profit, len(trades)) or 0.0),
        average_win=num.money(average_win),
        average_loss=num.money(average_loss),
        profit_factor=num.ratio(num.divide(gross_profit, gross_loss)),
        expectancy=num.money(
            _expectancy(len(trades), len(winners), len(losers), average_win, average_loss)
        ),
        recovery_factor=num.ratio(num.divide(net_profit, max_drawdown)),
        payoff_ratio=num.ratio(num.divide(average_win, average_loss)),
        commission_paid=num.money(sum(trade.commission for trade in trades)),
        slippage_cost=num.money(sum(trade.slippage_cost for trade in trades)),
        final_equity=num.money(final_equity),
    )


def _expectancy(
    total: int, winners: int, losers: int, average_win: float, average_loss: float
) -> float:
    """Probability-weighted expected profit per trade.

    ``win_rate * average_win - loss_rate * average_loss`` - the classic
    formulation, computed the way a researcher would check it by hand.

    Note that this is algebraically identical to Average Trade: substituting
    ``average_win = gross_profit / winners`` collapses the expression to
    ``net_profit / total``. Both are reported because both are conventionally
    quoted and Run Comparison will be read by people who look for one or the
    other - not because they measure different things. Any divergence between
    them would be a bug, and the golden test asserts they agree.
    """
    if total == 0:
        return 0.0
    win_rate = winners / total
    loss_rate = losers / total
    return win_rate * average_win - loss_rate * average_loss


def _annualised_return(total_return_pct: float, elapsed_days: float) -> float | None:
    if elapsed_days < 1.0:
        return None
    return num.percent(total_return_pct * CALENDAR_DAYS_PER_YEAR / elapsed_days)


def _cagr(initial_capital: float, final_equity: float, elapsed_days: float) -> float | None:
    """Compound annual growth rate.

    Undefined - and reported as ``None`` - when the account was wiped out or went
    negative: no real growth rate maps a positive start onto a non-positive end.

    Also ``None`` when compounding overflows, which happens for an implausible
    gain over a very short window (a 100,000x return across two days annualises
    past the float range). Reporting nothing is right for such a run: the number
    would be meaningless even if it fitted, and an infinity cannot cross the API.
    """
    if elapsed_days < 1.0 or initial_capital <= 0 or final_equity <= 0:
        return None
    years = elapsed_days / CALENDAR_DAYS_PER_YEAR
    try:
        growth = (final_equity / initial_capital) ** (1.0 / years) - 1.0
    except OverflowError:
        return None
    return num.percent(growth * 100.0)
