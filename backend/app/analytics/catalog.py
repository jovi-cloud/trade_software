"""The metric catalog: name, label, format, category and description for every metric.

This table is the single source of truth for how a metric is *presented*, kept
separate from how it is *computed*. It exists so that:

* the frontend renders metric cards and tooltips without hard-coding 60 labels;
* Run Comparison can align two runs, know which direction is better, and format
  a delta - without a redesign;
* a PDF research report can iterate a section in a fixed, meaningful order.

``key`` matches the field name on the group dataclass named by ``category``. A
unit test asserts the two sides stay in step, so adding a metric is: add a field,
add a definition. Nothing downstream changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MetricCategory(StrEnum):
    """Which group a metric belongs to. Values match ``AnalyticsReport`` fields."""

    RETURNS = "returns"
    RISK = "risk"
    RISK_ADJUSTED = "risk_adjusted"
    TRADES = "trades"
    PORTFOLIO = "portfolio"
    STATISTICS = "statistics"


class MetricFormat(StrEnum):
    """How a value should be rendered. The frontend switches on this."""

    CURRENCY = "currency"
    #: Already scaled: 12.5 means 12.5%.
    PERCENT = "percent"
    #: Dimensionless multiple, e.g. a Sharpe ratio or a profit factor.
    RATIO = "ratio"
    INTEGER = "integer"
    #: Milliseconds, rendered as a human duration.
    DURATION = "duration"
    NUMBER = "number"


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Everything needed to display or compare one metric."""

    key: str
    label: str
    category: MetricCategory
    format: MetricFormat
    description: str
    #: ``None`` where "better" is not meaningful (trade counts, exposure, costs).
    higher_is_better: bool | None = None
    #: Shown in the Overview section.
    is_headline: bool = False
    precision: int = 2


def _definition(
    key: str,
    label: str,
    category: MetricCategory,
    fmt: MetricFormat,
    description: str,
    *,
    higher_is_better: bool | None = None,
    is_headline: bool = False,
    precision: int = 2,
) -> MetricDefinition:
    return MetricDefinition(
        key=key,
        label=label,
        category=category,
        format=fmt,
        description=description,
        higher_is_better=higher_is_better,
        is_headline=is_headline,
        precision=precision,
    )


_RETURNS = (
    _definition(
        "net_profit",
        "Net Profit",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Total profit from closed trades, after commission and slippage.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "gross_profit",
        "Gross Profit",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Sum of the net P&L of winning trades only.",
        higher_is_better=True,
    ),
    _definition(
        "gross_loss",
        "Gross Loss",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Sum of the net P&L of losing trades, as a positive amount.",
        higher_is_better=False,
    ),
    _definition(
        "total_return_pct",
        "Total Return",
        MetricCategory.RETURNS,
        MetricFormat.PERCENT,
        "Net profit as a percentage of starting capital.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "annualised_return_pct",
        "Annualised Return",
        MetricCategory.RETURNS,
        MetricFormat.PERCENT,
        "Total return scaled linearly to one year over the elapsed calendar time. "
        "No compounding assumption. Undefined for runs shorter than a day.",
        higher_is_better=True,
    ),
    _definition(
        "cagr_pct",
        "CAGR",
        MetricCategory.RETURNS,
        MetricFormat.PERCENT,
        "Compound annual growth rate: the constant yearly rate that turns starting "
        "capital into final equity over the elapsed calendar time (365.25 days/year).",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "average_trade",
        "Average Trade",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Net profit divided by the number of trades, including breakeven trades.",
        higher_is_better=True,
    ),
    _definition(
        "average_win",
        "Average Win",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Gross profit divided by the number of winning trades.",
        higher_is_better=True,
    ),
    _definition(
        "average_loss",
        "Average Loss",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Gross loss divided by the number of losing trades, as a positive amount.",
        higher_is_better=False,
    ),
    _definition(
        "profit_factor",
        "Profit Factor",
        MetricCategory.RETURNS,
        MetricFormat.RATIO,
        "Gross profit divided by gross loss. Above 1.0 is profitable; "
        "undefined when there were no losing trades.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "expectancy",
        "Expectancy",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Probability-weighted profit per trade: win rate x average win minus "
        "loss rate x average loss.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "recovery_factor",
        "Recovery Factor",
        MetricCategory.RETURNS,
        MetricFormat.RATIO,
        "Net profit divided by maximum drawdown: how many times the worst "
        "setback the strategy earned back.",
        higher_is_better=True,
    ),
    _definition(
        "payoff_ratio",
        "Payoff Ratio",
        MetricCategory.RETURNS,
        MetricFormat.RATIO,
        "Average win divided by average loss. Below 1.0 needs a high win rate to pay.",
        higher_is_better=True,
    ),
    _definition(
        "commission_paid",
        "Commission Paid",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Total commission charged across every fill.",
    ),
    _definition(
        "slippage_cost",
        "Slippage Cost",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Total modelled slippage cost across every fill.",
    ),
    _definition(
        "final_equity",
        "Final Equity",
        MetricCategory.RETURNS,
        MetricFormat.CURRENCY,
        "Account equity at the last bar, marked to market.",
        higher_is_better=True,
    ),
)

_RISK = (
    _definition(
        "max_drawdown",
        "Maximum Drawdown",
        MetricCategory.RISK,
        MetricFormat.CURRENCY,
        "Largest peak-to-trough fall in equity, as a positive amount.",
        higher_is_better=False,
    ),
    _definition(
        "max_drawdown_pct",
        "Maximum Drawdown %",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Largest peak-to-trough fall as a percentage of the equity peak it fell from.",
        higher_is_better=False,
        is_headline=True,
    ),
    _definition(
        "average_drawdown",
        "Average Drawdown",
        MetricCategory.RISK,
        MetricFormat.CURRENCY,
        "Mean of the deepest point of each drawdown episode - what a typical setback costs.",
        higher_is_better=False,
    ),
    _definition(
        "average_drawdown_pct",
        "Average Drawdown %",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Mean depth of a drawdown episode, as a percentage of its peak.",
        higher_is_better=False,
    ),
    _definition(
        "longest_drawdown_ms",
        "Longest Drawdown",
        MetricCategory.RISK,
        MetricFormat.DURATION,
        "Elapsed time of the longest stretch spent below a previous equity peak.",
        higher_is_better=False,
    ),
    _definition(
        "longest_drawdown_bars",
        "Longest Drawdown (Bars)",
        MetricCategory.RISK,
        MetricFormat.INTEGER,
        "Number of bars in that same longest underwater stretch.",
        higher_is_better=False,
    ),
    _definition(
        "drawdown_episodes",
        "Drawdown Episodes",
        MetricCategory.RISK,
        MetricFormat.INTEGER,
        "How many separate times equity fell below a previous peak.",
    ),
    _definition(
        "ulcer_index",
        "Ulcer Index",
        MetricCategory.RISK,
        MetricFormat.RATIO,
        "Root mean square of percentage drawdown across every bar. Penalises deep "
        "and long drawdowns together, unlike maximum drawdown alone.",
        higher_is_better=False,
    ),
    _definition(
        "volatility_pct",
        "Volatility (Daily)",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Standard deviation of daily returns.",
        higher_is_better=False,
    ),
    _definition(
        "annualised_volatility_pct",
        "Annualised Volatility",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Daily volatility scaled by sqrt(252).",
        higher_is_better=False,
    ),
    _definition(
        "downside_deviation_pct",
        "Downside Deviation",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Annualised standard deviation of returns below the risk-free hurdle only. "
        "The denominator of the Sortino Ratio.",
        higher_is_better=False,
    ),
    _definition(
        "value_at_risk_pct",
        "Value at Risk",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Historical VaR: the daily loss not exceeded at the configured confidence "
        "level. No distributional assumption - the empirical percentile.",
        higher_is_better=False,
    ),
    _definition(
        "conditional_value_at_risk_pct",
        "Conditional VaR",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Expected shortfall: the average loss on the days that breach VaR.",
        higher_is_better=False,
    ),
    _definition(
        "exposure_pct",
        "Exposure",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Share of bars with an open position at the close.",
        is_headline=True,
    ),
    _definition(
        "time_in_market_pct",
        "Time in Market",
        MetricCategory.RISK,
        MetricFormat.PERCENT,
        "Share of elapsed calendar time holding a position. Diverges from Exposure "
        "on intraday data, where a position held over a session gap spans few bars "
        "but many hours.",
    ),
)

_RISK_ADJUSTED = (
    _definition(
        "sharpe_ratio",
        "Sharpe Ratio",
        MetricCategory.RISK_ADJUSTED,
        MetricFormat.RATIO,
        "Mean daily excess return over its standard deviation, annualised by "
        "sqrt(252). Undefined for a flat equity curve.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "sortino_ratio",
        "Sortino Ratio",
        MetricCategory.RISK_ADJUSTED,
        MetricFormat.RATIO,
        "Sharpe with only downside deviation in the denominator - upside volatility "
        "is not treated as risk.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "calmar_ratio",
        "Calmar Ratio",
        MetricCategory.RISK_ADJUSTED,
        MetricFormat.RATIO,
        "Annualised return divided by maximum drawdown percentage.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "mar_ratio",
        "MAR Ratio",
        MetricCategory.RISK_ADJUSTED,
        MetricFormat.RATIO,
        "CAGR divided by maximum drawdown percentage - the compounded counterpart "
        "of the Calmar Ratio.",
        higher_is_better=True,
    ),
    _definition(
        "information_ratio",
        "Information Ratio",
        MetricCategory.RISK_ADJUSTED,
        MetricFormat.RATIO,
        "Active return over tracking error against a benchmark. Requires a "
        "benchmark return series; otherwise undefined.",
        higher_is_better=True,
    ),
    _definition(
        "treynor_ratio",
        "Treynor Ratio",
        MetricCategory.RISK_ADJUSTED,
        MetricFormat.RATIO,
        "Excess annualised return per unit of market beta. Requires a beta "
        "estimate; otherwise undefined.",
        higher_is_better=True,
    ),
)

_TRADES = (
    _definition(
        "total_trades",
        "Total Trades",
        MetricCategory.TRADES,
        MetricFormat.INTEGER,
        "Number of completed round trips. Positions still open at the end are excluded.",
        is_headline=True,
    ),
    _definition(
        "winning_trades",
        "Winning Trades",
        MetricCategory.TRADES,
        MetricFormat.INTEGER,
        "Trades with net P&L above zero.",
    ),
    _definition(
        "losing_trades",
        "Losing Trades",
        MetricCategory.TRADES,
        MetricFormat.INTEGER,
        "Trades with net P&L below zero.",
    ),
    _definition(
        "breakeven_trades",
        "Breakeven Trades",
        MetricCategory.TRADES,
        MetricFormat.INTEGER,
        "Trades with exactly zero net P&L. Excluded from both win and loss rates.",
    ),
    _definition(
        "win_rate_pct",
        "Win Rate",
        MetricCategory.TRADES,
        MetricFormat.PERCENT,
        "Winning trades as a share of all trades.",
        higher_is_better=True,
        is_headline=True,
    ),
    _definition(
        "loss_rate_pct",
        "Loss Rate",
        MetricCategory.TRADES,
        MetricFormat.PERCENT,
        "Losing trades as a share of all trades. Sums to under 100% with the win "
        "rate when breakeven trades exist.",
        higher_is_better=False,
    ),
    _definition(
        "longest_win_streak",
        "Longest Win Streak",
        MetricCategory.TRADES,
        MetricFormat.INTEGER,
        "Most consecutive winning trades. A breakeven trade ends a streak.",
        higher_is_better=True,
    ),
    _definition(
        "longest_loss_streak",
        "Longest Loss Streak",
        MetricCategory.TRADES,
        MetricFormat.INTEGER,
        "Most consecutive losing trades - the run of pain to be survived live.",
        higher_is_better=False,
    ),
    _definition(
        "average_holding_time_ms",
        "Average Holding Time",
        MetricCategory.TRADES,
        MetricFormat.DURATION,
        "Mean elapsed time from entry fill to exit fill.",
    ),
    _definition(
        "max_holding_time_ms",
        "Maximum Holding Time",
        MetricCategory.TRADES,
        MetricFormat.DURATION,
        "Longest time a single position was held.",
    ),
    _definition(
        "min_holding_time_ms",
        "Minimum Holding Time",
        MetricCategory.TRADES,
        MetricFormat.DURATION,
        "Shortest time a single position was held.",
    ),
    _definition(
        "average_bars_held",
        "Average Bars Held",
        MetricCategory.TRADES,
        MetricFormat.NUMBER,
        "Mean number of bars a position was open for.",
    ),
    _definition(
        "average_mae",
        "Average MAE",
        MetricCategory.TRADES,
        MetricFormat.CURRENCY,
        "Mean maximum adverse excursion: how far a trade typically went against "
        "the entry before closing. Sizes the stop a strategy actually needs.",
        higher_is_better=False,
    ),
    _definition(
        "average_mfe",
        "Average MFE",
        MetricCategory.TRADES,
        MetricFormat.CURRENCY,
        "Mean maximum favourable excursion: how far a trade typically ran in "
        "favour. Well above average win means profit is being left on the table.",
        higher_is_better=True,
    ),
    _definition(
        "largest_winner",
        "Largest Winner",
        MetricCategory.TRADES,
        MetricFormat.CURRENCY,
        "Net P&L of the single best trade.",
        higher_is_better=True,
    ),
    _definition(
        "largest_loser",
        "Largest Loser",
        MetricCategory.TRADES,
        MetricFormat.CURRENCY,
        "Net P&L of the single worst trade, as a positive amount.",
        higher_is_better=False,
    ),
)

_PORTFOLIO = (
    _definition(
        "capital_utilisation_pct",
        "Capital Utilisation",
        MetricCategory.PORTFOLIO,
        MetricFormat.PERCENT,
        "Average share of equity deployed in positions, averaged over every bar "
        "including flat ones.",
    ),
    _definition(
        "peak_capital_utilisation_pct",
        "Peak Capital Utilisation",
        MetricCategory.PORTFOLIO,
        MetricFormat.PERCENT,
        "Highest share of equity committed to a position at any single bar.",
    ),
    _definition(
        "cash_utilisation_pct",
        "Cash Utilisation",
        MetricCategory.PORTFOLIO,
        MetricFormat.PERCENT,
        "Average share of equity held in cash - the complement of capital utilisation.",
    ),
)

_STATISTICS = (
    _definition(
        "sqn",
        "SQN",
        MetricCategory.STATISTICS,
        MetricFormat.RATIO,
        "System Quality Number: sqrt(trades) x mean trade P&L / its standard "
        "deviation. Requires at least 30 trades.",
        higher_is_better=True,
    ),
    _definition(
        "kelly_pct",
        "Kelly %",
        MetricCategory.STATISTICS,
        MetricFormat.PERCENT,
        "Theoretical growth-optimal fraction of equity per trade. Assumes the "
        "observed edge is the true edge - treat as an upper bound, not a setting.",
        higher_is_better=True,
    ),
    _definition(
        "z_score",
        "Z Score",
        MetricCategory.STATISTICS,
        MetricFormat.RATIO,
        "Runs test on the win/loss sequence. Negative means wins and losses "
        "cluster into streaks; |Z| above 1.96 is significant at 95%. "
        "Requires at least 30 decisive trades.",
    ),
    _definition(
        "edge_ratio",
        "Edge Ratio",
        MetricCategory.STATISTICS,
        MetricFormat.RATIO,
        "Average MFE over average MAE. Above 1.0 means trades ran further in "
        "favour than against - entry quality, independent of exit timing.",
        higher_is_better=True,
    ),
)

#: Presentation order for every metric, everywhere.
METRIC_DEFINITIONS: tuple[MetricDefinition, ...] = (
    *_RETURNS,
    *_RISK,
    *_RISK_ADJUSTED,
    *_TRADES,
    *_PORTFOLIO,
    *_STATISTICS,
)

METRIC_DEFINITIONS_BY_KEY: dict[str, MetricDefinition] = {
    definition.key: definition for definition in METRIC_DEFINITIONS
}

HEADLINE_METRIC_KEYS: tuple[str, ...] = tuple(
    definition.key for definition in METRIC_DEFINITIONS if definition.is_headline
)


def definitions_for(category: MetricCategory) -> tuple[MetricDefinition, ...]:
    """Every definition in one category, in presentation order."""
    return tuple(definition for definition in METRIC_DEFINITIONS if definition.category is category)
