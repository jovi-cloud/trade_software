"""Strategy code use cases: get-or-create, save, syntax-only validation.

Validation is ``ast.parse`` only. It never executes, imports, or compiles the
code beyond building a syntax tree - see ARCHITECTURE.md's "sandboxing: none"
decision, which makes this restraint deliberate rather than a missing feature.
"""

from __future__ import annotations

import ast

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.strategy_code import StrategyCode
from app.repositories.strategy_code_repo import StrategyCodeRepository
from app.repositories.strategy_repo import StrategyRepository
from app.schemas.strategy_code import StrategyValidationResult, SyntaxErrorDetail

DEFAULT_STRATEGY_TEMPLATE = """class Strategy:

    def on_start(self):
        pass

    def on_bar(self, bar):
        pass

    def on_stop(self):
        pass
"""


def _check_syntax(code: str) -> SyntaxErrorDetail | None:
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return SyntaxErrorDetail(
            line=exc.lineno, column=exc.offset, message=exc.msg or "Invalid syntax"
        )
    return None


class StrategyCodeService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = StrategyCodeRepository(session)
        self.strategy_repo = StrategyRepository(session)

    def _require_strategy(self, strategy_id: str) -> None:
        if self.strategy_repo.get(strategy_id) is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")

    def get_or_create(self, strategy_id: str) -> StrategyCode:
        self._require_strategy(strategy_id)
        record = self.repo.get_by_strategy_id(strategy_id)
        if record is not None:
            return record

        error = _check_syntax(DEFAULT_STRATEGY_TEMPLATE)
        record = StrategyCode(
            strategy_id=strategy_id,
            code=DEFAULT_STRATEGY_TEMPLATE,
            compiled_successfully=error is None,
            compile_error=error.message if error else None,
        )
        self.repo.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record

    def update(self, strategy_id: str, code: str) -> StrategyCode:
        self._require_strategy(strategy_id)
        record = self.repo.get_by_strategy_id(strategy_id)
        error = _check_syntax(code)

        if record is None:
            record = StrategyCode(strategy_id=strategy_id, code=code)
            self.repo.add(record)
        else:
            record.code = code

        record.compiled_successfully = error is None
        record.compile_error = error.message if error else None

        self.session.commit()
        self.session.refresh(record)
        return record

    def validate(self, strategy_id: str, code: str) -> StrategyValidationResult:
        self._require_strategy(strategy_id)
        error = _check_syntax(code)
        return StrategyValidationResult(valid=error is None, error=error)
