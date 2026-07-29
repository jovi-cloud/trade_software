# Engine Calculation Audit

Phase 4C audit of every monetary calculation path in `app/engine/`.

## Execution fills (`execution/simulator.py`)

| Calculation | Formula | Notes |
|---|---|---|
| Long entry fill price | `open * (1 + slippage)` | Slippage embedded in price |
| Short entry fill price | `open * (1 - slippage)` | Slippage embedded in price |
| Long exit fill price | `open * (1 - slippage)` | |
| Short exit fill price | `open * (1 + slippage)` | |
| Commission | `quantity * fill_price * commission_rate` | Applied per fill |
| Slippage cost (reporting) | `quantity * open * slippage_rate` | Tracked separately; not subtracted again from `net_pnl` |

## Portfolio cash (`execution/portfolio.py`)

| Event | Cash change |
|---|---|
| Open long | `- (quantity * fill_price + commission)` |
| Open short | `+ (quantity * fill_price - commission)` |
| Close long | `+ (quantity * fill_price - commission)` |
| Close short | `- (quantity * fill_price + commission)` |

## Trade P&L (`execution/trade_manager.py`)

| Field | Formula |
|---|---|
| Long gross P&L | `(exit_price - entry_price) * quantity` |
| Short gross P&L | `(entry_price - exit_price) * quantity` |
| net P&L | `gross_pnl - total_commission` |

Slippage is already reflected in fill prices, so it must not be subtracted again.

## Metrics (`results/metrics.py`)

| Metric | Formula |
|---|---|
| net_profit | `final_cash - initial_capital` |
| gross_profit | `sum(net_pnl)` for winners |
| gross_loss | `abs(sum(net_pnl))` for losers |
| win_rate_pct | `winning_trades / total_trades * 100` |
| profit_factor | `gross_profit / gross_loss` (0 when no losses) |
| expectancy / average_trade | `net_profit / total_trades` |
| return_pct | `(final_cash - initial_capital) / initial_capital * 100` |
| equity point | cumulative `initial_capital + sum(net_pnl)` after each trade |

## Bug fixed in Phase 4C

`net_pnl` previously subtracted `slippage_cost` even though slippage is embedded in fill prices. This caused `sum(net_pnl)` to diverge from `final_cash - initial_capital` whenever slippage was non-zero.

## Values that remain float

- Raw OHLCV bar data from Parquet
- Chart coordinates and marker positions
- Indicator computations (future phase)
- `execution_time_ms`
