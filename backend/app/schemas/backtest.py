"""Backtest execution request/response DTOs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.domain.enums import OrderStatus, OrderType, PositionSide


class BacktestExecuteRequest(BaseModel):
    """Inputs for replaying a saved strategy against a saved dataset."""

    strategy_id: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    initial_capital: float = Field(default=100_000.0, gt=0)
    commission: float = Field(default=0.0, ge=0)
    slippage: float = Field(default=0.0, ge=0)


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
