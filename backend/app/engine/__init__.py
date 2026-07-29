"""Backtest engine.

Framework-free by contract: imports nothing from FastAPI, SQLAlchemy or
Pydantic, and nothing from app.api / app.services / app.models / app.db.
Enforced by the import-linter contracts in pyproject.toml.
"""
