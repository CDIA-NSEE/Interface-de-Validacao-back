from __future__ import annotations

from app.models import ValidationCycle
from app.repositories.sqlmodel.validation_cycle_repository import SqlModelValidationCycleRepository


def test_get_by_key(session):
    repo = SqlModelValidationCycleRepository(session)
    repo.add(ValidationCycle(cycle_key="default", label="Ciclo padrao"))
    repo.commit()

    cycle = repo.get_by_key("default")
    assert cycle is not None
    assert cycle.label == "Ciclo padrao"
    assert repo.get_by_key("missing") is None
