# Explainability Reason Codes

Every `reason_code` on an explainability event uses a stable dotted namespace.
Codes are deterministic and never free-form strings.

**Schema version:** 1

## Signal (`signal.*`)

| Code | Event types | Meaning |
|---|---|---|
| `signal.long` | `signal_generated` | Strategy requested a long entry |
| `signal.short` | `signal_generated` | Strategy requested a short entry |
| `signal.exit` | `signal_generated` | Strategy requested to close the position |
| `signal.rejected` | `signal_generated` | Signal was not submitted (validation failed) |

## Order (`order.*`)

| Code | Event types | Meaning |
|---|---|---|
| `order.created` | `order_created` | Order object created in the order book |
| `order.submitted` | `order_submitted` | Order queued for next-bar fill |
| `order.filled` | `order_filled` | Order matched and filled |
| `order.cancelled` | `order_cancelled` | Order removed before fill (reserved) |
| `order.rejected` | `order_rejected` | Order rejected at fill time |

## Position (`position.*`)

| Code | Event types | Meaning |
|---|---|---|
| `position.opened` | `position_opened` | New position opened from a fill |
| `position.updated` | `position_updated` | Mark-to-market update while position is open |
| `position.closed` | `position_closed` | Position fully closed |

## Risk (`risk.*`)

| Code | Event types | Meaning |
|---|---|---|
| `risk.insufficient_cash` | `order_rejected` | Fill rejected: not enough cash |
| `risk.max_position` | `order_rejected` | Fill rejected: position already open |
| `risk.validation_failed` | `signal_generated` | Pre-submit validation failed |

## System (`system.*`)

| Code | Event types | Meaning |
|---|---|---|
| `system.run_started` | `run_started` | Backtest replay started |
| `system.dataset_loaded` | `dataset_loaded` | Market data loaded |
| `system.strategy_loaded` | `strategy_loaded` | Strategy compiled successfully |
| `system.strategy_load_failed` | `strategy_loaded` | Strategy compilation failed |
| `system.parameters_loaded` | `parameters_applied` | Run configuration applied |
| `system.bar_processing` | `bar_processing_started` | Processing a price bar (full detail only) |
| `system.metrics_generated` | `metrics_generated` | Performance metrics computed |
| `system.charts_generated` | `charts_generated` | Chart artifacts prepared |
| `system.completed` | `run_completed` | Run finished |
| `system.profit_calculated` | `profit_calculated` | Round-trip P&L recorded for a trade |

## Decision (`decision.*`)

| Code | Event types | Meaning |
|---|---|---|
| `decision.conditions_evaluated` | `conditions_evaluated` | Strategy/engine conditions recorded for a bar |
| `decision.no_trade` | inferred | No actionable trade on this bar |

## Narrative (`narrative.*`)

Human-readable duplicates for the summary layer. Same facts as execution events.

## Legacy mappings (schema version 0)

Runs persisted before Phase 5B may use older codes. The API normalizes these
on read:

| Legacy | Normalized |
|---|---|
| `lifecycle.run_started` | `system.run_started` |
| `lifecycle.dataset_loaded` | `system.dataset_loaded` |
| `lifecycle.strategy_loaded` | `system.strategy_loaded` |
| `lifecycle.strategy_load_failed` | `system.strategy_load_failed` |
| `lifecycle.metrics_generated` | `system.metrics_generated` |
| `lifecycle.charts_generated` | `system.charts_generated` |
| `lifecycle.run_completed` | `system.completed` |
| `config.parameters_applied` | `system.parameters_loaded` |
| `execution.bar_processing` | `system.bar_processing` |
| `strategy.signal.*` | `signal.long` / `signal.short` / `signal.exit` |
| `order.submitted.*` | `order.submitted` |
| `order.filled.*` | `order.filled` |
| `position.opened.*` | `position.opened` |
| `position.closed.*` | `position.closed` |
