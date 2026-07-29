"""Central rounding policy for all engine calculations.

Every monetary, price, quantity, and percentage value is rounded through
these constants so rounding rules are never duplicated across modules.
"""

from __future__ import annotations

# Currency, cash, P&L, commission, slippage, portfolio value.
MONEY_DECIMALS: int = 6

# Fill prices and OHLC bar prices at execution boundaries.
PRICE_DECIMALS: int = 6

# Share/lot quantity at order and position boundaries.
QUANTITY_DECIMALS: int = 6

# Win rate, return %, and other headline percentages (12.5 means 12.5%).
PERCENT_DECIMALS: int = 6

# Values that intentionally remain float without Decimal conversion:
# - Raw OHLCV bar data from Parquet (converted at execution boundary only)
# - Chart coordinates and downsampling
# - Indicator computations (future phase)
# - Execution timing (execution_time_ms)
