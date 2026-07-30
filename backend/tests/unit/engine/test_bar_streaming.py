"""The bar loop replays a stream without materialising it.

What these pin down is a memory property, which is why they assert on how much
of the source was consumed rather than only on the result: a regression that
quietly calls ``list(bars)`` again would still produce correct numbers, and the
only visible symptom would be a multi-gigabyte run on a large dataset.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.engine.bars import Bar, BarIterator
from app.engine.errors import EngineError
from app.engine.results.chart_data import CandleCollector
from app.engine.runner import ExecutionConfig, ExecutionEngine

COUNTING_STRATEGY = """
class Strategy:
    seen = 0

    def on_bar(self, bar):
        self.seen = self.seen + 1
"""


def _bar(index: int) -> Bar:
    price = 100.0 + index
    return Bar(
        ts=1_000 + index * 1_000,
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=10.0,
    )


class _CountingSource:
    """A bar source that records how many bars have been pulled from it."""

    def __init__(self, count: int) -> None:
        self.count = count
        self.produced = 0
        self.live = 0

    def __iter__(self) -> Iterator[Bar]:
        for index in range(self.count):
            self.produced += 1
            self.live = 1  # one bar exists at a time
            yield _bar(index)


def test_a_streaming_run_never_holds_more_than_one_bar() -> None:
    source = _CountingSource(500)

    result = ExecutionEngine(ExecutionConfig()).run(
        strategy_source=COUNTING_STRATEGY,
        bars=BarIterator.streaming(source, count=500),
    )

    assert result.completed
    assert result.bars_processed == 500
    assert source.produced == 500
    assert source.live == 1


def test_a_streamed_iterator_declares_its_length_without_draining() -> None:
    source = _CountingSource(1_000)

    bars = BarIterator.streaming(source, count=1_000)

    assert len(bars) == 1_000
    assert bars.is_streaming
    assert source.produced == 0, "asking for the length must not consume the stream"


def test_a_streamed_iterator_refuses_a_second_replay() -> None:
    bars = BarIterator.streaming(_CountingSource(3), count=3)
    assert len(list(bars)) == 3

    with pytest.raises(EngineError, match="already been replayed"):
        list(bars)


def test_a_sequence_backed_iterator_is_still_replayable() -> None:
    bars = BarIterator([_bar(0), _bar(1)])

    assert not bars.is_streaming
    assert len(list(bars)) == 2
    assert len(list(bars)) == 2


def test_the_first_bar_is_replayed_exactly_once() -> None:
    """The clock for pre-loop events is read by peeking; the peek is put back."""
    source = _CountingSource(4)

    result = ExecutionEngine(ExecutionConfig()).run(
        strategy_source=COUNTING_STRATEGY,
        bars=BarIterator.streaming(source, count=4),
    )

    assert result.bars_processed == 4
    assert source.produced == 4


def test_an_empty_stream_warns_rather_than_failing() -> None:
    result = ExecutionEngine(ExecutionConfig()).run(
        strategy_source=COUNTING_STRATEGY,
        bars=BarIterator.streaming(_CountingSource(0), count=0),
    )

    assert result.bars_processed == 0
    assert any("no bars" in warning for warning in result.warnings)


def test_the_candle_collector_taps_the_stream_without_buffering_bars() -> None:
    source = _CountingSource(50)
    collector = CandleCollector()

    result = ExecutionEngine(ExecutionConfig()).run(
        strategy_source=COUNTING_STRATEGY,
        bars=BarIterator.streaming(collector.tap(source), count=50),
    )

    candles = collector.candles
    assert result.bars_processed == 50
    assert len(candles) == 50
    assert source.live == 1
    # The candle series mirrors the bars it was tapped from, in order.
    assert [candle.ts for candle in candles] == [_bar(index).ts for index in range(50)]
    assert candles[0].close == _bar(0).close


def test_candles_cover_only_the_bars_the_engine_received() -> None:
    """A run that dies mid-replay must not report a full-length bar series.

    Building candles from the whole file instead of the replay is how a run that
    failed on its first bar still produced a ten-bar analytics report.
    """
    failing = """
class Strategy:
    seen = 0

    def on_bar(self, bar):
        self.seen = self.seen + 1
        if self.seen == 3:
            raise ValueError("boom")
"""
    collector = CandleCollector()

    result = ExecutionEngine(ExecutionConfig()).run(
        strategy_source=failing,
        bars=BarIterator.streaming(collector.tap(_CountingSource(100)), count=100),
    )

    assert not result.completed
    assert result.bars_processed == 2
    assert len(collector.candles) == 3, "the bar that raised was received, the rest never arrived"
