"""Chart data builder unit tests."""

from __future__ import annotations

from app.domain.enums import PositionSide
from app.engine.execution.trade import Trade
from app.engine.results.chart_data import ChartDataBuilder
from app.engine.results.metrics import MetricsEngine

INITIAL = 10_000.0


def _bar_row(ts: int, close: float) -> dict[str, object]:
    return {
        "ts": ts,
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 100.0,
    }


def _trade(
    seq: int,
    *,
    side: PositionSide = PositionSide.LONG,
    entry_ts: int = 1_000,
    exit_ts: int = 2_000,
    entry_price: float = 100.0,
    exit_price: float = 105.0,
    net_pnl: float = 5.0,
) -> Trade:
    return Trade(
        seq=seq,
        side=side,
        quantity=1.0,
        entry_ts=entry_ts,
        entry_price=entry_price,
        exit_ts=exit_ts,
        exit_price=exit_price,
        gross_pnl=net_pnl,
        commission=0.0,
        slippage_cost=0.0,
        net_pnl=net_pnl,
        bars_held=3,
    )


def test_no_trades_returns_candles_only() -> None:
    rows = [_bar_row(1_000, 100), _bar_row(2_000, 101)]
    candles, entries, exits = ChartDataBuilder().build(rows, [])

    assert len(candles) == 2
    assert candles[0].ts == 1_000
    assert candles[1].close == 101
    assert entries == ()
    assert exits == ()


def test_one_trade_produces_entry_and_exit_markers() -> None:
    trade = _trade(1, entry_ts=1_000, exit_ts=3_000, entry_price=100.0, exit_price=106.0)
    rows = [_bar_row(1_000, 100), _bar_row(2_000, 103), _bar_row(3_000, 106)]
    candles, entries, exits = ChartDataBuilder().build(rows, [trade])

    assert len(candles) == 3
    assert len(entries) == 1
    assert len(exits) == 1
    assert entries[0].trade_seq == 1
    assert entries[0].ts == 1_000
    assert entries[0].price == 100.0
    assert entries[0].side is PositionSide.LONG
    assert entries[0].marker_kind == "entry"
    assert exits[0].ts == 3_000
    assert exits[0].price == 106.0
    assert exits[0].marker_kind == "exit"


def test_many_trades_marker_positions_match_trades() -> None:
    trades = (
        _trade(1, entry_ts=1_000, exit_ts=2_000, entry_price=10.0, exit_price=11.0),
        _trade(
            2,
            entry_ts=3_000,
            exit_ts=4_000,
            entry_price=12.0,
            exit_price=13.0,
            side=PositionSide.SHORT,
        ),
    )
    rows = [_bar_row(ts, float(ts)) for ts in (1_000, 2_000, 3_000, 4_000)]
    _, entries, exits = ChartDataBuilder().build(rows, trades)

    assert len(entries) == 2
    assert len(exits) == 2
    assert entries[1].side is PositionSide.SHORT
    assert exits[0].trade_seq == 1
    assert exits[1].trade_seq == 2


def test_large_dataset_builds_all_candles() -> None:
    count = 5_000
    rows = [_bar_row(i * 60_000, 100.0 + i * 0.01) for i in range(count)]
    candles, entries, exits = ChartDataBuilder().build(rows, [])

    assert len(candles) == count
    assert candles[-1].ts == (count - 1) * 60_000
    assert entries == ()
    assert exits == ()


def test_equity_points_align_with_closed_trades() -> None:
    trades = (
        _trade(1, net_pnl=100.0, exit_ts=2_000),
        _trade(2, net_pnl=-25.0, exit_ts=4_000),
    )
    _, equity = MetricsEngine().compute(
        trades=trades, initial_capital=INITIAL, final_cash=INITIAL + 75
    )

    assert len(equity) == 2
    assert equity[0].trade_number == 1
    assert equity[0].equity == INITIAL + 100
    assert equity[0].timestamp == 2_000
    assert equity[1].trade_number == 2
    assert equity[1].equity == INITIAL + 75
    assert equity[1].timestamp == 4_000
