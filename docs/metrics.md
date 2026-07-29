# Performance Metrics

The exact formula and annualisation assumption for every metric the platform
reports. If a number on the Results page is ever in doubt, this file is the
authority.

**Status:** Phase 3C — trade-level analytics only. No Sharpe, drawdown, or CAGR
yet.

## Inputs

- `trades` — completed round-trip trades, ordered by `seq`
- `initial_capital` — starting cash
- `final_cash` — ending cash after the run

## Trade classification

- **Winning trade:** `net_pnl > 0`
- **Losing trade:** `net_pnl < 0`
- **Breakeven trade:** `net_pnl == 0` (excluded from win/loss counts)

## Headline metrics

| Metric | Formula |
|---|---|
| Net Profit | `final_cash - initial_capital` |
| Gross Profit | `sum(net_pnl)` for winning trades |
| Gross Loss | `abs(sum(net_pnl))` for losing trades |
| Total Trades | `len(trades)` |
| Winning Trades | count where `net_pnl > 0` |
| Losing Trades | count where `net_pnl < 0` |
| Win Rate % | `winning_trades / total_trades * 100` (0 if no trades) |
| Average Win | `gross_profit / winning_trades` (0 if none) |
| Average Loss | `gross_loss / losing_trades` (0 if none) |
| Largest Win | `max(net_pnl)` among winners (0 if none) |
| Largest Loss | `abs(min(net_pnl))` among losers (0 if none) |
| Profit Factor | `gross_profit / gross_loss` (0 if no losses) |
| Expectancy | `net_profit / total_trades` (0 if no trades) |
| Average Trade | same as Expectancy |
| Average Holding Bars | `mean(trade.bars_held)` (0 if no trades) |
| Commission Paid | `sum(trade.commission)` |
| Slippage Cost | `sum(trade.slippage_cost)` |
| Final Cash | `final_cash` |
| Return % | `(final_cash - initial_capital) / initial_capital * 100` |

Percent fields are stored as `12.5` meaning 12.5%, not `0.125`.

## Equity history

After each closed trade, in `seq` order:

```
equity_n = initial_capital + sum(net_pnl for trades 1..n)
```

Each point: `{ trade_number: seq, equity, timestamp: exit_ts }`.
