# Decimal and Rounding Policy

## Decimal policy

Money calculations use `Decimal` internally via `app/domain/money.py`:

- Cash balances
- Commission
- Slippage cost (reporting field)
- Trade gross/net P&L
- Portfolio proceeds and debits
- Final account balance
- Fill prices at execution boundaries

Conversion uses `Decimal(str(value))` to avoid binary float artefacts. Values are converted back to `float` at module boundaries so the engine API remains unchanged.

## Rounding policy

Central constants live in `app/domain/rounding.py`:

| Constant | Precision | Used for |
|---|---|---|
| `MONEY_DECIMALS` | 6 | Cash, P&L, commission, slippage |
| `PRICE_DECIMALS` | 6 | Fill prices |
| `QUANTITY_DECIMALS` | 6 | Order quantity |
| `PERCENT_DECIMALS` | 6 | Win rate, return % |

Rounding mode: `ROUND_HALF_UP` via `money.quantize()`.

All modules call `round_money`, `round_price`, `round_quantity`, `round_percent`, `add_money`, `sub_money`, or `mul_money` — never ad-hoc `round()` for money.

## Float by design

These remain `float` intentionally:

- Parquet OHLCV source data
- Chart rendering and downsampling
- Future indicator vector math
- Execution timing (`execution_time_ms`)
