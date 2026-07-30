"""Explainability API schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.explain import ExplainEventStatus, ExplainEventType, ExplainLayer
from app.engine.explain.trade_inspector import TradeOutcome


class ExplainEventRead(BaseModel):
    schema_version: int = Field(default=1, ge=0)
    event_id: str
    seq: int = Field(ge=1)
    event_type: ExplainEventType
    layer: ExplainLayer
    timestamp_ms: int
    bar_index: int | None = None
    reason_code: str
    status: ExplainEventStatus
    trade_id: int | None = None
    trade_seq: int | None = None
    order_id: int | None = None
    position_id: int | None = None
    instrument: str | None = None
    timeframe: str | None = None
    message: str
    price: float | None = None
    quantity: float | None = None
    commission: float | None = None
    slippage: float | None = None
    cash: float | None = None
    portfolio_value: float | None = None
    pnl: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExplainEventFilter(BaseModel):
    layer: ExplainLayer | None = None
    event_type: ExplainEventType | None = None
    trade_id: int | None = Field(default=None, ge=1)
    order_id: int | None = Field(default=None, ge=1)
    position_id: int | None = Field(default=None, ge=1)
    reason_code: str | None = None
    status: ExplainEventStatus | None = None
    q: str | None = None
    timestamp_from_ms: int | None = Field(default=None, ge=0)
    timestamp_to_ms: int | None = Field(default=None, ge=0)
    bar_index: int | None = Field(default=None, ge=0)


class TradeTimelineStepRead(BaseModel):
    step_type: ExplainEventType
    label: str
    event_seq: int
    timestamp_ms: int
    bar_index: int | None = None
    price: float | None = None
    quantity: float | None = None
    commission: float | None = None
    slippage: float | None = None
    cash: float | None = None
    portfolio_value: float | None = None
    reason_code: str
    message: str
    related_event_seqs: list[int] = Field(default_factory=list)


class TradeSummaryRead(BaseModel):
    trade_number: int = Field(ge=1)
    direction: str
    entry_time_ms: int
    exit_time_ms: int
    entry_price: float
    exit_price: float
    gross_profit: float
    net_profit: float
    commission: float
    slippage: float
    holding_period_bars: int = Field(ge=0)
    mae: float | None = None
    mfe: float | None = None
    return_pct: float
    risk_reward: float | None = None
    status: TradeOutcome
    order_ids: list[int] = Field(default_factory=list)
    position_id: int | None = None
    event_count: int = Field(ge=0)


class TradeInspectionRead(BaseModel):
    summary: TradeSummaryRead
    timeline: list[TradeTimelineStepRead]
    event_seqs: list[int] = Field(default_factory=list)


class TradeListRead(BaseModel):
    items: list[TradeSummaryRead]
    total: int


class ConditionTraceRead(BaseModel):
    name: str
    actual_value: str
    expected_value: str
    passed: bool
    #: False when the rule was declared but never consulted on this bar - which
    #: ``passed`` alone cannot express, and which is the answer to "why did my
    #: crossover not fire" whenever a position was already open.
    evaluated: bool = True


class OperandRead(BaseModel):
    """One raw number behind a verdict on a specific bar."""

    name: str
    label: str
    unit: str = ""
    value: float


class ConditionDefinitionRead(BaseModel):
    name: str
    expected: str


class OperandDefinitionRead(BaseModel):
    name: str
    label: str
    unit: str = ""


class DecisionSchemaRead(BaseModel):
    """A decision log's per-run constants, hoisted out of the rows."""

    version: int = Field(default=1, ge=1)
    instrument: str | None = None
    timeframe: str | None = None
    indicators: list[str] = Field(default_factory=list)
    conditions: list[ConditionDefinitionRead] = Field(default_factory=list)
    operands: list[OperandDefinitionRead] = Field(default_factory=list)


class DecisionRowRead(BaseModel):
    """Everything calculated on one bar.

    ``conditions`` is tri-state: absent means the rule was never consulted on
    this bar, which is a different fact from having been consulted and failed.
    """

    bar_index: int = Field(ge=0)
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    indicators: dict[str, float] = Field(default_factory=dict)
    conditions: dict[str, bool | None] = Field(default_factory=dict)
    operands: list[OperandRead] = Field(default_factory=list)


class DecisionLogRead(BaseModel):
    """One window of the per-bar decision log."""

    run_id: str
    total_rows: int = Field(ge=0)
    start: int = Field(ge=0)
    log_schema: DecisionSchemaRead
    rows: list[DecisionRowRead] = Field(default_factory=list)


class ConditionSummaryRead(BaseModel):
    """How often one condition was reached, and how often it passed."""

    name: str
    expected: str
    evaluated: int = Field(ge=0)
    passed: int = Field(ge=0)


class DecisionSummaryRead(BaseModel):
    """Whole-run condition tallies - the "why did nothing happen" table."""

    run_id: str
    total_rows: int = Field(ge=0)
    conditions: list[ConditionSummaryRead] = Field(default_factory=list)


class BarCandleRead(BaseModel):
    bar_index: int = Field(ge=0)
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class BarOrderSummaryRead(BaseModel):
    order_ref: int = Field(ge=1)
    order_type: str
    quantity: float
    status: str
    fill_price: float | None = None
    commission: float = 0.0
    slippage_cost: float = 0.0


class BarPositionSummaryRead(BaseModel):
    side: str
    quantity: float
    entry_price: float


class BarMarketStateRead(BaseModel):
    current_price: float
    open: float
    high: float
    low: float
    close: float
    volume: float
    trend: str
    volatility_pct: float
    session: str
    indicators: dict[str, float | str] = Field(default_factory=dict)
    cash: float | None = None
    portfolio_value: float | None = None
    position: BarPositionSummaryRead | None = None


class BarDecisionRead(BaseModel):
    decision_type: str
    reason_code: str
    message: str
    related_event_seqs: list[int] = Field(default_factory=list)


class BarExecutionSummaryRead(BaseModel):
    occurred: bool
    message: str
    order_ref: int | None = None
    fill_price: float | None = None
    quantity: float | None = None
    commission: float | None = None
    slippage: float | None = None
    position: BarPositionSummaryRead | None = None
    pnl: float | None = None


class BarTimelineStepRead(BaseModel):
    label: str
    event_type: ExplainEventType
    event_seq: int
    timestamp_ms: int


class BarNavigationRead(BaseModel):
    bar_index: int = Field(ge=0)
    bar_count: int = Field(ge=0)
    previous_bar_index: int | None = Field(default=None, ge=0)
    next_bar_index: int | None = Field(default=None, ge=0)
    first_signal_bar: int | None = Field(default=None, ge=0)
    last_signal_bar: int | None = Field(default=None, ge=0)
    trade_entry_bars: list[int] = Field(default_factory=list)
    trade_exit_bars: list[int] = Field(default_factory=list)


class BarInspectionRead(BaseModel):
    bar_index: int = Field(ge=0)
    candle: BarCandleRead
    market_state: BarMarketStateRead
    conditions: list[ConditionTraceRead]
    #: The arithmetic behind this bar's verdicts, from the decision log. Empty
    #: for runs recorded before the log existed, or below FULL.
    operands: list[OperandRead] = Field(default_factory=list)
    decision: BarDecisionRead
    execution: BarExecutionSummaryRead
    timeline: list[BarTimelineStepRead]
    open_orders: list[BarOrderSummaryRead]
    filled_orders: list[BarOrderSummaryRead]
    cancelled_orders: list[BarOrderSummaryRead]
    event_seqs: list[int] = Field(default_factory=list)
    navigation: BarNavigationRead
    explain_events: list[ExplainEventRead] = Field(default_factory=list)
