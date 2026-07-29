# Working in this repository

Read [ARCHITECTURE.md](ARCHITECTURE.md) before changing anything structural.
It is the approved design and takes precedence over inference from the code.

## Non-negotiables

- **Layer direction:** `api → services → { repositories, engine, data } → domain`.
  Nothing points back up. Enforced by `import-linter` on `make lint`.
- **The engine is a library.** `app/engine/` must never import FastAPI,
  SQLAlchemy, Pydantic, or anything from `app.api` / `app.services` /
  `app.models` / `app.db`.
- **Immutability:** `strategy_versions` and `backtest_runs` are append-only.
  Editing a saved version is impossible; saving creates version N+1.
- **No business logic in routers.** Validate → call service → return.
- **Never raise `HTTPException` below the router layer.** Raise a domain error
  from `app/core/exceptions.py`; `app/api/errors.py` maps it to a status code.
- **Frontend API types are generated** (`make types`), never hand-written.
- **Server state lives in TanStack Query.** No `useEffect` + `fetch`.

## Before every commit

```bash
make check      # ruff, mypy, import contracts, oxlint, pytest
```

## Current state

Phase 0 complete: foundation only. No ORM models, no business logic, one health
endpoint, one placeholder dashboard. Phases are listed in ARCHITECTURE.md §7 —
do not start the next one without approval.
