"""Strategy use cases: CRUD, search/filter/sort, soft delete, dashboard stats."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.base import utcnow
from app.domain.enums import StrategyStatus
from app.models.strategy import Strategy
from app.repositories.strategy_repo import StrategyRepository
from app.schemas.strategy import StrategyCreate, StrategyUpdate

ALLOWED_SORT_COLUMNS = {"updated_at", "name"}
MAX_PAGE_SIZE = 100
DASHBOARD_LIST_LIMIT = 5
# Fields on StrategyUpdate that must never be cleared to null - only omitted.
REQUIRED_ON_UPDATE = {
    "name",
    "description",
    "instrument",
    "market_type",
    "timeframe",
    "status",
    "confidence_level",
    "priority",
}
# Long-text fields that are optional at every stage - blank strings collapse to null.
OPTIONAL_TEXT_FIELDS = (
    "hypothesis",
    "entry_rules",
    "exit_rules",
    "stop_loss_method",
    "target_method",
    "position_sizing",
    "assumptions",
    "known_weaknesses",
    "ideas_for_improvement",
)


def _normalize_tags(tags: str | None) -> str | None:
    if not tags:
        return None
    seen: dict[str, None] = {}
    for part in tags.split(","):
        cleaned = part.strip()
        if cleaned:
            seen.setdefault(cleaned, None)
    return ", ".join(seen) or None


def _clean_text(value: str | None) -> str | None:
    if not value:
        return None
    stripped = value.strip()
    return stripped or None


class StrategyService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repo = StrategyRepository(session)

    def create(self, data: StrategyCreate) -> Strategy:
        name = data.name.strip()
        if self.repo.get_by_name(name) is not None:
            raise ConflictError(f"A strategy named '{name}' already exists")

        strategy = Strategy(
            name=name,
            description=data.description.strip(),
            hypothesis=_clean_text(data.hypothesis),
            market_type=data.market_type,
            instrument=data.instrument.strip(),
            timeframe=data.timeframe,
            entry_rules=_clean_text(data.entry_rules),
            exit_rules=_clean_text(data.exit_rules),
            stop_loss_method=_clean_text(data.stop_loss_method),
            target_method=_clean_text(data.target_method),
            position_sizing=_clean_text(data.position_sizing),
            assumptions=_clean_text(data.assumptions),
            known_weaknesses=_clean_text(data.known_weaknesses),
            ideas_for_improvement=_clean_text(data.ideas_for_improvement),
            status=data.status,
            confidence_level=data.confidence_level,
            priority=data.priority,
            tags=_normalize_tags(data.tags),
        )
        self.repo.add(strategy)
        self.session.commit()
        self.session.refresh(strategy)
        return strategy

    def get(self, strategy_id: str) -> Strategy:
        strategy = self.repo.get(strategy_id)
        if strategy is None:
            raise NotFoundError(f"Strategy '{strategy_id}' not found")
        return strategy

    def list(
        self,
        *,
        q: str | None,
        status: StrategyStatus | None,
        sort: str,
        order: str,
        limit: int,
        offset: int,
    ) -> tuple[list[Strategy], int]:
        sort_column = sort if sort in ALLOWED_SORT_COLUMNS else "updated_at"
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)
        return self.repo.search(
            q=q.strip() if q else None,
            status=status,
            sort_column=sort_column,
            descending=order != "asc",
            limit=limit,
            offset=offset,
        )

    def update(self, strategy_id: str, data: StrategyUpdate) -> Strategy:
        strategy = self.get(strategy_id)
        updates = data.model_dump(exclude_unset=True)

        for field in REQUIRED_ON_UPDATE & updates.keys():
            if updates[field] is None:
                raise ValidationError(f"'{field}' must not be null")

        if "name" in updates:
            new_name = updates["name"].strip()
            if not new_name:
                raise ValidationError("'name' must not be blank")
            if new_name != strategy.name and self.repo.get_by_name(new_name) is not None:
                raise ConflictError(f"A strategy named '{new_name}' already exists")
            strategy.name = new_name

        if "description" in updates:
            description = updates["description"].strip()
            if not description:
                raise ValidationError("'description' must not be blank")
            strategy.description = description

        if "instrument" in updates:
            instrument = updates["instrument"].strip()
            if not instrument:
                raise ValidationError("'instrument' must not be blank")
            strategy.instrument = instrument

        for field in ("market_type", "timeframe", "status", "confidence_level", "priority"):
            if field in updates:
                setattr(strategy, field, updates[field])

        for field in OPTIONAL_TEXT_FIELDS:
            if field in updates:
                setattr(strategy, field, _clean_text(updates[field]))

        if "tags" in updates:
            strategy.tags = _normalize_tags(updates["tags"])

        self.session.commit()
        self.session.refresh(strategy)
        return strategy

    def delete(self, strategy_id: str) -> None:
        strategy = self.get(strategy_id)
        strategy.deleted_at = utcnow()
        self.session.commit()

    def stats(self) -> dict[str, object]:
        counts = self.repo.counts_by_status()
        return {
            "total": sum(counts.values()),
            "draft": counts.get(StrategyStatus.DRAFT, 0),
            "testing": counts.get(StrategyStatus.TESTING, 0),
            "validated": counts.get(StrategyStatus.VALIDATED, 0),
            "archived": counts.get(StrategyStatus.ARCHIVED, 0),
            "rejected": counts.get(StrategyStatus.REJECTED, 0),
            "high_priority": self.repo.high_priority(DASHBOARD_LIST_LIMIT),
            "recent_research": self.repo.recently_updated(DASHBOARD_LIST_LIMIT),
            "needs_review": self.repo.needs_review(DASHBOARD_LIST_LIMIT),
        }
