# Market Data Format

The canonical bar schema and the rules applied during CSV import.

**Status:** placeholder — written in Phase 1.

Canonical schema (already fixed by ARCHITECTURE.md 2.3):

| Column   | Type    | Notes                              |
|----------|---------|------------------------------------|
| `ts`     | int64   | UTC epoch milliseconds, ascending, unique |
| `open`   | float64 |                                    |
| `high`   | float64 |                                    |
| `low`    | float64 |                                    |
| `close`  | float64 |                                    |
| `volume` | float64 | nullable                           |
