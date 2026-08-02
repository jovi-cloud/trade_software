"""The single reconstruction of the account equity curve.

Everything downstream - drawdown, volatility, Sharpe, monthly returns, exposure,
utilisation - reads these arrays. They are built exactly once per report, which
is how the "no duplicated calculations" rule is kept structurally rather than by
discipline.

The engine records equity only after each closed trade (one point per trade).
Risk statistics need equity *per bar*, so it is reconstructed here from closed
trades marked to market against bar closes. That reconstruction is exact for the
current single-position engine: at most one position is open at any bar, and its
unrealised P&L is a pure function of the entry price, side, quantity and close.
Reconstructing rather than instrumenting the bar loop is what keeps this an
additive layer.

Costs are realised at exit, so an open position's mark is gross of its exit
commission and slippage. The realised leg is always net of both.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import numpy as np
from numpy.typing import NDArray

from app.analytics.inputs import MS_PER_DAY, BarRecord, TradeRecord
from app.domain.enums import PositionSide

FloatArray = NDArray[np.float64]
IntArray = NDArray[np.int64]
BoolArray = NDArray[np.bool_]


def _empty_float() -> FloatArray:
    return np.zeros(0, dtype=np.float64)


def _empty_int() -> IntArray:
    return np.zeros(0, dtype=np.int64)


@dataclass(frozen=True)
class EquitySeries:
    """Per-bar account state. All arrays share the bar index.

    ``exposure_notional`` is the absolute market value of the open position at
    the bar close - the numerator of capital utilisation.
    """

    ts: IntArray
    close: FloatArray
    high: FloatArray
    low: FloatArray
    equity: FloatArray
    realised: FloatArray
    exposure_notional: FloatArray
    in_position: BoolArray
    initial_capital: float

    @property
    def bar_count(self) -> int:
        return int(self.ts.size)

    @property
    def is_empty(self) -> bool:
        return self.ts.size == 0

    @property
    def bars_in_position(self) -> int:
        return int(np.count_nonzero(self.in_position))

    @property
    def final_equity(self) -> float:
        if self.is_empty:
            return self.initial_capital
        return float(self.equity[-1])

    @property
    def start_ts(self) -> int | None:
        return None if self.is_empty else int(self.ts[0])

    @property
    def end_ts(self) -> int | None:
        return None if self.is_empty else int(self.ts[-1])

    @property
    def elapsed_ms(self) -> int:
        if self.ts.size < 2:
            return 0
        return int(self.ts[-1] - self.ts[0])

    @classmethod
    def empty(cls, initial_capital: float) -> EquitySeries:
        return cls(
            ts=_empty_int(),
            close=_empty_float(),
            high=_empty_float(),
            low=_empty_float(),
            equity=_empty_float(),
            realised=_empty_float(),
            exposure_notional=_empty_float(),
            in_position=np.zeros(0, dtype=np.bool_),
            initial_capital=initial_capital,
        )


def build_equity_series(
    *,
    bars: tuple[BarRecord, ...],
    trades: tuple[TradeRecord, ...],
    initial_capital: float,
) -> EquitySeries:
    """Mark-to-market equity at every bar close.

    Vectorised on purpose: a year of 1m bars is ~100k rows and a report must
    stay comfortably sub-second so that it can be produced inline with the run
    rather than as a separate job.
    """
    if not bars:
        return EquitySeries.empty(initial_capital)

    count = len(bars)
    ts = np.fromiter((bar.ts for bar in bars), dtype=np.int64, count=count)
    close = np.fromiter((bar.close for bar in bars), dtype=np.float64, count=count)
    high = np.fromiter((bar.high for bar in bars), dtype=np.float64, count=count)
    low = np.fromiter((bar.low for bar in bars), dtype=np.float64, count=count)

    realised = np.full(count, float(initial_capital), dtype=np.float64)
    if trades:
        exit_ts = np.fromiter(
            (trade.exit_ts for trade in trades), dtype=np.int64, count=len(trades)
        )
        net_pnl = np.fromiter(
            (trade.net_pnl for trade in trades), dtype=np.float64, count=len(trades)
        )
        order = np.argsort(exit_ts, kind="stable")
        cumulative = np.concatenate(([0.0], np.cumsum(net_pnl[order])))
        # A trade is realised on the bar it exits on, so side="right".
        closed_by_bar = np.searchsorted(exit_ts[order], ts, side="right")
        realised = float(initial_capital) + cumulative[closed_by_bar]

    unrealised = np.zeros(count, dtype=np.float64)
    exposure_notional = np.zeros(count, dtype=np.float64)
    in_position = np.zeros(count, dtype=np.bool_)

    for trade in trades:
        start = int(np.searchsorted(ts, trade.entry_ts, side="left"))
        # Exclusive of the exit bar: the exit fills at that bar's open, so the
        # position is no longer held at its close, and its P&L is already in
        # ``realised``.
        stop = int(np.searchsorted(ts, trade.exit_ts, side="left"))
        if stop <= start:
            continue
        held = slice(start, stop)
        sign = 1.0 if trade.side is PositionSide.LONG else -1.0
        unrealised[held] += sign * (close[held] - trade.entry_price) * trade.quantity
        exposure_notional[held] += np.abs(close[held]) * trade.quantity
        in_position[held] = True

    return EquitySeries(
        ts=ts,
        close=close,
        high=high,
        low=low,
        equity=realised + unrealised,
        realised=realised,
        exposure_notional=exposure_notional,
        in_position=in_position,
        initial_capital=float(initial_capital),
    )


def _utc_offset_ms(ts_ms: int, timezone: str) -> int:
    """UTC offset, in milliseconds, of ``timezone`` at the instant ``ts_ms``.

    One offset for the whole run rather than a per-bar lookup: exact for
    ``Asia/Kolkata`` (no DST, ever), and for any other fixed-offset exchange
    zone. A run that happens to straddle a DST transition in a zone that
    observes one may misattribute a handful of bars near that boundary - a
    rare edge case, and still strictly better than bucketing everything by
    the wrong calendar day the way raw UTC does for every single day.
    """
    moment = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
    offset = moment.astimezone(ZoneInfo(timezone)).utcoffset()
    return int(offset.total_seconds() * 1000) if offset is not None else 0


@dataclass(frozen=True)
class DailySeries:
    """Equity sampled at each exchange-local day's last bar, and the returns
    between them.

    Daily is the basis for every dispersion statistic. Annualising raw 1m-bar
    returns would make the same strategy look wildly different on 1m and 1d
    data; sampling to days first makes runs comparable across timeframes and
    matches how these numbers are quoted in practice.

    Only days that actually contain bars appear - market holidays and weekends
    are absent rather than carried forward flat, so a gap never registers as a
    zero-return day.
    """

    day_ms: IntArray
    equity: FloatArray
    returns_pct: FloatArray
    pnl: FloatArray

    @property
    def day_count(self) -> int:
        return int(self.day_ms.size)

    @property
    def is_empty(self) -> bool:
        return self.day_ms.size == 0

    @classmethod
    def empty(cls) -> DailySeries:
        return cls(
            day_ms=_empty_int(),
            equity=_empty_float(),
            returns_pct=_empty_float(),
            pnl=_empty_float(),
        )


def build_daily_series(series: EquitySeries, *, timezone: str = "UTC") -> DailySeries:
    """Collapse a per-bar equity curve to one closing value per exchange-local day.

    ``timezone`` is the exchange the bars trade in (``dataset.timezone`` /
    ``ExecutionConfig.session_timezone``), not the server's or viewer's. A bar
    stamped at midnight local time - the common convention for a daily-bar
    dataset - sits on the *previous* UTC calendar day for any zone east of
    UTC, so bucketing by raw UTC would silently misattribute every single
    trading day (and, at a month or year boundary, an entire period) to the
    wrong bucket for a dataset that trades outside UTC, e.g. NSE's Asia/Kolkata.
    """
    if series.is_empty:
        return DailySeries.empty()

    offset_ms = _utc_offset_ms(int(series.ts[0]), timezone)
    day_index = (series.ts + offset_ms) // MS_PER_DAY
    days = np.unique(day_index)
    # Bars are ascending, so the last bar of each day is the position before
    # the next day starts.
    last_of_day = np.searchsorted(day_index, days, side="right") - 1
    equity = series.equity[last_of_day]

    previous = np.concatenate(([series.initial_capital], equity[:-1]))
    pnl = equity - previous
    with np.errstate(divide="ignore", invalid="ignore"):
        returns_pct = np.where(previous != 0.0, (equity / previous - 1.0) * 100.0, 0.0)

    return DailySeries(
        # The actual UTC instant of that exchange-local day's midnight - a
        # real, valid timestamp, not a UTC day boundary - so callers that
        # re-derive the calendar date (``periods.py``) or display it
        # (``formatTimestamp`` in the given ``timezone``) see the same date.
        day_ms=days * MS_PER_DAY - offset_ms,
        equity=equity,
        returns_pct=np.nan_to_num(returns_pct, nan=0.0, posinf=0.0, neginf=0.0),
        pnl=pnl,
    )
