from __future__ import annotations

from sqlmodel import Session, select

from app.modules.validation.models import ValidationCycle
from app.modules.validation.repositories.interfaces import ValidationCycleRepository
from app.shared.repository import SqlModelRepository


class SqlModelValidationCycleRepository(SqlModelRepository[ValidationCycle], ValidationCycleRepository):
    def __init__(self, session: Session) -> None:
        super().__init__(session, ValidationCycle)

    def get_by_key(self, cycle_key: str) -> ValidationCycle | None:
        return self._session.exec(
            select(ValidationCycle).where(ValidationCycle.cycle_key == cycle_key)
        ).first()
