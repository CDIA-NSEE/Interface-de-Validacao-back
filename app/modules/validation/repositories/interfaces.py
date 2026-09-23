from __future__ import annotations

from abc import abstractmethod

from app.modules.validation.models import ValidationCycle
from app.shared.repository import Repository


class ValidationCycleRepository(Repository[ValidationCycle, int]):
    @abstractmethod
    def get_by_key(self, cycle_key: str) -> ValidationCycle | None: ...
