"""Backtest execution request/response DTOs."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import OrderStatus, OrderType, PositionSide
from app.domain.explain import ExplainLevel
from app.schemas.explain import ExplainEventRead


class BacktestExecuteRequest(BaseModel):
    """Inputs for replaying a strategy against a saved dataset.

    ``library_strategy_id`` is additive and optional: omit it and the saved
    strategy's own code runs, exactly as before. Supply it and the named
    built-in strategy runs instead, configured by ``strategy_params``.

    Every run is still recorded against a row in ``strategies`` - the research
    container the run history and journal hang off. ``strategy_id`` names it
    explicitly; omitting it for a library run lets the service resolve (and, the
    first time, create) the container for that library strategy, so launching a
    backtest straight from the Strategy Library does not require the trader to
    hand-create a research record first.
    """

    model_config = ConfigDict(populate_by_name=True)

    strategy_id: str | None = Field(
        default=None,
        min_length=1,
        description="Research container for the run. Optional for a library strategy.",
    )
    dataset_id: str = Field(min_length=1)
    dataset_version_id: str | None = Field(
        default=None,
        min_length=1,
        description="Explicit immutable dataset version to run against.",
    )
    dataset_version_number: int | None = Field(
        default=None,
        ge=1,
        alias="dataset_version",
        description="Dataset version number. Omitted uses the current version.",
    )
    initial_capital: float = Field(default=100_000.0, gt=0)
    commission: float = Field(default=0.0, ge=0)
    slippage: float = Field(default=0.0, ge=0)
    explain_level: ExplainLevel | None = Field(
        default=None,
        description=(
            "Omit to use the strategy's recommended level: FULL for a strategy that "
            "traces its conditions, TRADES_ONLY otherwise."
        ),
    )
    library_strategy_id: str | None = Field(
        default=None,
        description="Run this built-in strategy instead of the saved code.",
    )
    strategy_params: dict[str, bool | int | float | str] | None = Field(
        default=None,
        description="Parameter values for the library strategy; defaults fill any gaps.",
    )

    @model_validator(mode="after")
    def _check_strategy_selection(self) -> BacktestExecuteRequest:
        if self.strategy_id is None and self.library_strategy_id is None:
            raise ValueError("Provide strategy_id, library_strategy_id, or both")
        if self.strategy_params is not None and self.library_strategy_id is None:
            # Silently ignoring them would look like the run honoured values it never saw.
            raise ValueError("strategy_params only apply to a library strategy")
        if self.dataset_version_id is not None and self.dataset_version_number is not None:
            raise ValueError("Provide dataset_version_id or dataset_version, not both")
        return self


class OrderRead(BaseModel):
    id: int
    order_type: OrderType
    quantity: float
    submitted_bar_index: int
    submitted_ts: int
    status: OrderStatus
    fill_price: float | None = None
    fill_ts: int | None = None
    filled_bar_index: int | None = None
    commission: float = 0.0
    slippage_cost: float = 0.0
    rejection_reason: str | None = None


class TradeRead(BaseModel):
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


class EquityPointRead(BaseModel):
    trade_number: int
    equity: float
    timestamp: int


class CandleRead(BaseModel):
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class TradeMarkerRead(BaseModel):
    ts: int
    price: float
    trade_seq: int
    side: PositionSide
    marker_kind: str


class PerformanceMetricsRead(BaseModel):
    net_profit: float
    gross_profit: float
    gross_loss: float
    total_trades: int = Field(ge=0)
    winning_trades: int = Field(ge=0)
    losing_trades: int = Field(ge=0)
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


class ExecutionResultRead(BaseModel):
    """Outcome of one in-process replay with performance analytics."""

    run_id: str | None = None
    dataset_version_id: str | None = None
    dataset_version_number: int | None = None
    dataset_fingerprint: str | None = None
    completed: bool
    bars_processed: int = Field(ge=0)
    execution_time_ms: float = Field(ge=0)
    errors: list[str]
    warnings: list[str]
    strategy_logs: list[str]
    orders: list[OrderRead]
    trades: list[TradeRead]
    final_cash: float
    position_closed: bool
    trade_count: int = Field(ge=0)
    metrics: PerformanceMetricsRead
    equity_history: list[EquityPointRead]
    candles: list[CandleRead]
    entry_markers: list[TradeMarkerRead]
    exit_markers: list[TradeMarkerRead]
    explain_events: list[ExplainEventRead] = Field(default_factory=list)
    explain_level: ExplainLevel = ExplainLevel.TRADES_ONLY
