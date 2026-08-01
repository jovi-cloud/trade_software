# Trailing stop loss

## Overview

The engine supports ratcheting trailing stops for library strategies. When
`enable_trailing_stop` is true, the stop follows the best price reached and
never moves in the losing direction.

## Parameters

| Parameter | Description |
|-----------|-------------|
| `enable_trailing_stop` | Master switch. When false, legacy `trailing_stop_pct` / `trailing_atr_multiple` still apply. |
| `trailing_method` | `percent`, `points`, or `atr` |
| `trailing_stop_percent` | Distance as % of best price (e.g. `2` = 2%) |
| `trailing_stop_points` | Fixed price distance from best price |
| `trailing_stop_atr_multiplier` | Multiple of ATR (uses current bar ATR, falls back to entry ATR) |

## Example (EMA Crossover)

```json
{
  "library_strategy_id": "ema_crossover",
  "strategy_params": {
    "enable_trailing_stop": true,
    "trailing_method": "percent",
    "trailing_stop_percent": 2.0,
    "stop_atr_multiple": 2.0
  }
}
```

## Execution model

1. Update highest/lowest price using the bar high/low.
2. Recompute the trailing stop from the best price.
3. Ratchet the stop (never loosen).
4. Exit when the bar range breaches the stop (long: `low <= stop`, short: `high >= stop`).

Exits are submitted at the **next bar open**, consistent with all protective exits.

## Trade output

Closed trades include `exit_reason`, `trailing_stop_at_exit`, excursion fields, and
chart overlays via `trailing_stop_points`.
