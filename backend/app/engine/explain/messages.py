"""Template-based human messages for explain events.

All trader-facing text is produced here from structured facts — never from
free-form logs or AI generation.
"""

from __future__ import annotations

from app.domain.enums import OrderType, PositionSide


def run_started_message(*, bar_count: int) -> str:
    if bar_count == 0:
        return "Backtest run started with an empty dataset."
    return f"Backtest run started. {bar_count:,} price bars will be replayed."


def dataset_loaded_message(*, bar_count: int, dataset_name: str) -> str:
    return f"Dataset '{dataset_name}' loaded with {bar_count:,} price bars."


def strategy_loaded_message() -> str:
    return "Strategy code compiled and loaded successfully."


def strategy_load_failed_message(*, detail: str) -> str:
    return f"Strategy could not be loaded: {detail}"


def parameters_applied_message(
    *,
    initial_capital: float,
    commission: float,
    slippage: float,
) -> str:
    return (
        f"Run parameters applied: starting capital {initial_capital:,.2f}, "
        f"commission rate {commission:.6g}, slippage rate {slippage:.6g}."
    )


def bar_processing_started_message(*, bar_index: int) -> str:
    return f"Processing price bar {bar_index + 1}."


def conditions_evaluated_message(*, bar_index: int, passed_count: int, total_count: int) -> str:
    if total_count == 0:
        return f"No strategy conditions were traced on bar {bar_index + 1}."
    return f"Evaluated {total_count} condition(s) on bar {bar_index + 1}; {passed_count} passed."


def signal_generated_message(*, action: str, quantity: float, bar_index: int) -> str:
    return f"Strategy signalled {action} for {quantity:g} shares on bar {bar_index + 1}."


def signal_rejected_message(*, action: str, reason: str) -> str:
    return f"{action} signal was not submitted: {reason}."


def order_created_message(*, order_type: OrderType, quantity: float) -> str:
    label = _order_type_label(order_type)
    return f"{label} created for {quantity:g} shares."


def order_submitted_message(*, order_type: OrderType, quantity: float) -> str:
    label = _order_type_label(order_type)
    return f"{label} submitted for {quantity:g} shares at the next bar open."


def order_filled_message(*, order_type: OrderType, fill_price: float) -> str:
    label = _order_type_label(order_type)
    return f"{label} filled at {fill_price:,.4f}."


def order_rejected_message(*, order_type: OrderType, reason: str) -> str:
    label = _order_type_label(order_type)
    return f"{label} was rejected: {reason}."


def position_opened_message(*, side: PositionSide, quantity: float, price: float) -> str:
    side_label = "Long" if side is PositionSide.LONG else "Short"
    return f"{side_label} position opened: {quantity:g} shares at {price:,.4f}."


def position_closed_message(*, side: PositionSide, quantity: float, price: float) -> str:
    side_label = "Long" if side is PositionSide.LONG else "Short"
    return f"{side_label} position closed: {quantity:g} shares at {price:,.4f}."


def position_updated_message(
    *, side: PositionSide, mark_price: float, unrealized_pnl: float
) -> str:
    side_label = "Long" if side is PositionSide.LONG else "Short"
    return (
        f"{side_label} position marked at {mark_price:,.4f}; unrealized P&L {unrealized_pnl:,.2f}."
    )


def profit_calculated_message(*, trade_seq: int, net_pnl: float) -> str:
    outcome = "profit" if net_pnl >= 0 else "loss"
    return f"Trade {trade_seq} closed with net {outcome} of {net_pnl:,.2f}."


def metrics_generated_message(*, trade_count: int) -> str:
    if trade_count == 0:
        return "Performance metrics calculated. No completed trades in this run."
    return f"Performance metrics calculated from {trade_count} completed trade(s)."


def charts_generated_message(*, candle_count: int, marker_count: int) -> str:
    return f"Chart data prepared: {candle_count:,} candles and {marker_count} trade marker(s)."


def run_completed_message(*, completed: bool, trade_count: int) -> str:
    if not completed:
        return "Backtest run ended before completion due to an error."
    if trade_count == 0:
        return "Backtest run completed. No trades were executed."
    return f"Backtest run completed with {trade_count} completed trade(s)."


def _order_type_label(order_type: OrderType) -> str:
    if order_type is OrderType.BUY_MARKET:
        return "Buy market order"
    if order_type is OrderType.SELL_MARKET:
        return "Sell short market order"
    return "Close position order"
