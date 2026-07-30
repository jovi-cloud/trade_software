"""Underwater analysis of the equity curve.

One pass produces the drawdown curve used for charting *and* every drawdown
scalar, including the episode boundaries. Depth is reported as a positive
number: a maximum drawdown of 1,250 means equity fell 1,250 below its peak.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.analytics import _numeric as num
from app.analytics.equity import BoolArray, EquitySeries, FloatArray, IntArray


@dataclass(frozen=True, slots=True)
class DrawdownEpisode:
    """One uninterrupted stretch below a previous equity peak."""

    start_ts: int
    trough_ts: int
    #: ``None`` when the run ended still underwater - the episode never recovered.
    recovery_ts: int | None
    depth: float
    depth_pct: float
    bars: int
    duration_ms: int


@dataclass(frozen=True)
class DrawdownSeries:
    """Per-bar distance below the running equity peak.

    ``depth`` and ``depth_pct`` are non-negative; zero means the curve is at a
    new high.
    """

    ts: IntArray
    peak: FloatArray
    depth: FloatArray
    depth_pct: FloatArray
    underwater: BoolArray
    episodes: tuple[DrawdownEpisode, ...]

    @property
    def is_empty(self) -> bool:
        return self.ts.size == 0

    @classmethod
    def empty(cls) -> DrawdownSeries:
        empty_float = np.zeros(0, dtype=np.float64)
        return cls(
            ts=np.zeros(0, dtype=np.int64),
            peak=empty_float,
            depth=empty_float,
            depth_pct=empty_float,
            underwater=np.zeros(0, dtype=np.bool_),
            episodes=(),
        )


def build_drawdown_series(series: EquitySeries) -> DrawdownSeries:
    """Running-peak drawdown over the whole equity curve.

    The peak is seeded with the starting capital, so a strategy that loses money
    from its very first bar is correctly in drawdown rather than treating its
    own first low as a peak.
    """
    if series.is_empty:
        return DrawdownSeries.empty()

    peak = np.maximum.accumulate(np.maximum(series.equity, series.initial_capital))
    depth = np.maximum(peak - series.equity, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        depth_pct = np.where(peak > 0.0, depth / peak * 100.0, 0.0)
    depth_pct = np.nan_to_num(depth_pct, nan=0.0, posinf=0.0, neginf=0.0)
    underwater = depth > 0.0

    return DrawdownSeries(
        ts=series.ts,
        peak=peak,
        depth=depth,
        depth_pct=depth_pct,
        underwater=underwater,
        episodes=_episodes(series.ts, depth, depth_pct, underwater),
    )


def _episodes(
    ts: IntArray,
    depth: FloatArray,
    depth_pct: FloatArray,
    underwater: BoolArray,
) -> tuple[DrawdownEpisode, ...]:
    """Split the underwater mask into contiguous episodes.

    Boundaries are found on the mask's transitions rather than by scanning every
    bar in Python, so cost scales with the number of episodes, not bars.
    """
    if not underwater.any():
        return ()

    padded = np.concatenate(([False], underwater, [False]))
    transitions = np.diff(padded.astype(np.int8))
    starts = np.flatnonzero(transitions == 1)
    ends = np.flatnonzero(transitions == -1)  # exclusive

    episodes: list[DrawdownEpisode] = []
    for start, end in zip(starts.tolist(), ends.tolist(), strict=True):
        window = slice(start, end)
        trough_offset = int(np.argmax(depth[window]))
        trough_index = start + trough_offset
        recovered = end < underwater.size
        # The episode starts at the peak bar - the last bar that was not
        # underwater - because that is where equity began falling.
        peak_index = max(start - 1, 0)
        start_ts = int(ts[peak_index])
        recovery_ts = int(ts[end]) if recovered else None
        end_ts = recovery_ts if recovery_ts is not None else int(ts[-1])
        episodes.append(
            DrawdownEpisode(
                start_ts=start_ts,
                trough_ts=int(ts[trough_index]),
                recovery_ts=recovery_ts,
                depth=num.money(float(depth[trough_index])),
                depth_pct=num.percent(float(depth_pct[trough_index])),
                bars=int(end - start),
                duration_ms=end_ts - start_ts,
            )
        )
    return tuple(episodes)


@dataclass(frozen=True)
class DrawdownMetrics:
    """Scalar drawdown statistics, all computed from the full series."""

    max_drawdown: float
    max_drawdown_pct: float
    average_drawdown: float
    average_drawdown_pct: float
    longest_drawdown_ms: int
    longest_drawdown_bars: int
    ulcer_index: float | None
    drawdown_episodes: int
    max_drawdown_start_ts: int | None
    max_drawdown_trough_ts: int | None
    max_drawdown_recovery_ts: int | None


def compute_drawdown_metrics(drawdowns: DrawdownSeries) -> DrawdownMetrics:
    """Reduce the underwater series to headline numbers.

    *Average drawdown* is the mean of each episode's **maximum** depth, not the
    mean depth across underwater bars. The episode definition answers "how bad
    is a typical setback", which is the question a researcher is actually
    asking; the bar-weighted version is dominated by the long shallow tails of
    recovery.

    *Ulcer Index* is ``sqrt(mean(depth_pct**2))`` over every bar of the run,
    including bars at a new high. It is deliberately not annualised.
    """
    if drawdowns.is_empty:
        return DrawdownMetrics(
            max_drawdown=0.0,
            max_drawdown_pct=0.0,
            average_drawdown=0.0,
            average_drawdown_pct=0.0,
            longest_drawdown_ms=0,
            longest_drawdown_bars=0,
            ulcer_index=None,
            drawdown_episodes=0,
            max_drawdown_start_ts=None,
            max_drawdown_trough_ts=None,
            max_drawdown_recovery_ts=None,
        )

    episodes = drawdowns.episodes
    worst = max(episodes, key=lambda episode: episode.depth, default=None)
    longest = max(episodes, key=lambda episode: episode.duration_ms, default=None)

    return DrawdownMetrics(
        max_drawdown=num.money(float(np.max(drawdowns.depth))),
        max_drawdown_pct=num.percent(float(np.max(drawdowns.depth_pct))),
        average_drawdown=num.money(
            num.mean(np.array([episode.depth for episode in episodes], dtype=np.float64))
        ),
        average_drawdown_pct=num.percent(
            num.mean(np.array([episode.depth_pct for episode in episodes], dtype=np.float64))
        ),
        longest_drawdown_ms=longest.duration_ms if longest is not None else 0,
        # Same episode as the duration above, so the two never describe
        # different setbacks.
        longest_drawdown_bars=longest.bars if longest is not None else 0,
        ulcer_index=num.ratio(float(np.sqrt(np.mean(np.square(drawdowns.depth_pct))))),
        drawdown_episodes=len(episodes),
        max_drawdown_start_ts=worst.start_ts if worst is not None else None,
        max_drawdown_trough_ts=worst.trough_ts if worst is not None else None,
        max_drawdown_recovery_ts=worst.recovery_ts if worst is not None else None,
    )
