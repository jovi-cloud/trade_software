"""What the analytics layer consumes, and the constants it annualises with.

Deliberately plain records rather than engine objects. The same report can then
be produced from a live ``ExecutionResult`` or from the JSON snapshot of a run
saved months ago, which is what makes Run Comparison, Monte Carlo and PDF
reporting additive rather than a refactor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import PositionSide

#: Trading days in a year. The annualisation factor for every daily-return
#: statistic (volatility, Sharpe, Sortino, downside deviation). 252 is the
#: institutional convention for equity markets and is used unconditionally so
#: that two runs on different instruments stay directly comparable.
TRADING_DAYS_PER_YEAR = 252

#: Calendar days in a year, including the leap-year quarter day. Used only for
#: elapsed-time arithmetic (CAGR, annualised return), never for volatility.
CALENDAR_DAYS_PER_YEAR = 365.25

MS_PER_DAY = 86_400_000
MS_PER_HOUR = 3_600_000


@dataclass(frozen=True, slots=True)
class TradeRecord:
    """One completed round trip, as the analytics layer sees it.

    Mirrors ``app.engine.execution.trade.Trade`` field for field, but is its own
    type so analytics never imports the engine.
    """

    seq: int
    side: PositionSide
    quantity: float
    entry_ts: int
    entry_price: float
    exit_ts: int
    exit_price: float
    gross_pnl: float
    commission: float
    slippage_cost: float
    net_pnl: float
    bars_held: int


@dataclass(frozen=True, slots=True)
class BarRecord:
    """One OHLCV bar. Needed to mark open positions to market and to measure
    excursions (MAE/MFE) inside a trade."""

    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


@dataclass(frozen=True)
class AnalyticsConfig:
    """Assumptions a report is computed under.

    Recorded on the report itself (``AnalyticsMeta``) so a saved number can
    always be traced back to the assumption that produced it.
    """

    #: Annual risk-free rate as a percent (6.0 means 6%). Divided by
    #: ``TRADING_DAYS_PER_YEAR`` to get the daily hurdle for Sharpe/Sortino.
    risk_free_rate_pct: float = 0.0

    #: Confidence level for Value at Risk (95.0 means the 5th percentile).
    var_confidence_pct: float = 95.0

    #: Window, in trading days, for the rolling-return series.
    rolling_window_days: int = 21

    #: Upper bound on the number of points in an emitted curve. Scalars are
    #: always computed from the full series; only the curves handed to a chart
    #: are thinned, and extremes are preserved.
    max_curve_points: int = 2_000

    #: Portfolio beta against the benchmark. Treynor Ratio stays ``None`` until
    #: a benchmark exists to estimate it from - the seam is here so adding one
    #: later needs no signature change.
    beta: float | None = None

    #: Benchmark daily returns in percent, aligned to the run's trading days.
    #: Supplied, the Information Ratio is computed; omitted, it is ``None``.
    benchmark_daily_returns_pct: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not 50.0 <= self.var_confidence_pct < 100.0:
            raise ValueError("var_confidence_pct must be in [50, 100)")
        if self.rolling_window_days < 1:
            raise ValueError("rolling_window_days must be at least 1")
        if self.max_curve_points < 2:
            raise ValueError("max_curve_points must be at least 2")

    @property
    def daily_risk_free_pct(self) -> float:
        """The per-day hurdle rate. Simple division, not compounding: at these
        magnitudes the difference is far below reporting precision."""
        return self.risk_free_rate_pct / TRADING_DAYS_PER_YEAR


@dataclass(frozen=True)
class AnalyticsInput:
    """Everything one report is derived from.

    ``bars`` may be empty - every metric that needs a price series then
    degrades to ``None`` or zero rather than failing, so a report always exists
    for a completed run.
    """

    trades: tuple[TradeRecord, ...] = ()
    bars: tuple[BarRecord, ...] = ()
    initial_capital: float = 0.0
    config: AnalyticsConfig = field(default_factory=AnalyticsConfig)

    def __post_init__(self) -> None:
        if self.initial_capital < 0:
            raise ValueError("initial_capital must not be negative")
