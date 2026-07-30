"""Strategy metadata: derived labels, capability queries and search."""

from __future__ import annotations

from app.domain.enums import MarketType, Timeframe
from tests.unit.engine.strategy.conftest import make_metadata


def test_direction_label_reflects_the_declared_sides():
    assert make_metadata(supports_long=True, supports_short=True).direction_label == "Long & short"
    assert make_metadata(supports_long=True, supports_short=False).direction_label == "Long only"
    assert make_metadata(supports_long=False, supports_short=True).direction_label == "Short only"
    assert (
        make_metadata(supports_long=False, supports_short=False).direction_label
        == "No direction declared"
    )


def test_styles_lists_only_the_declared_horizons():
    metadata = make_metadata(
        supports_intraday=True, supports_swing=False, supports_position_trading=True
    )
    assert metadata.styles == ("intraday", "position")


def test_styles_is_empty_when_no_horizon_is_declared():
    metadata = make_metadata(
        supports_intraday=False, supports_swing=False, supports_position_trading=False
    )
    assert metadata.styles == ()


def test_supports_timeframe_compares_canonical_strings():
    metadata = make_metadata(timeframes=(Timeframe.M5, Timeframe.H1))
    assert metadata.supports_timeframe("5m") is True
    assert metadata.supports_timeframe("1h") is True
    assert metadata.supports_timeframe("1d") is False


def test_supports_market_compares_canonical_strings():
    metadata = make_metadata(markets=(MarketType.CRYPTO,))
    assert metadata.supports_market("crypto") is True
    assert metadata.supports_market("equity") is False


def test_search_matches_the_name_case_insensitively():
    metadata = make_metadata(name="EMA Crossover")
    assert metadata.matches("ema") is True
    assert metadata.matches("EMA CROSS") is True


def test_search_matches_tags_and_category_and_author():
    metadata = make_metadata(tags=("breakout", "intraday"), author="Platform")
    assert metadata.matches("breakout") is True
    assert metadata.matches("trend following") is True  # category, underscores humanised
    assert metadata.matches("platform") is True


def test_search_matches_the_documentation_overview():
    metadata = make_metadata()
    assert metadata.matches("what this strategy does") is True


def test_an_empty_query_matches_everything():
    assert make_metadata().matches("") is True
    assert make_metadata().matches("   ") is True


def test_search_does_not_match_unrelated_text():
    assert make_metadata().matches("supertrend") is False
