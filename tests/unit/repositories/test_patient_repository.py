from __future__ import annotations

from app.models import Patient
from app.repositories.sqlmodel.patient_repository import SqlModelPatientRepository


def _make_patient(**overrides) -> Patient:
    defaults = dict(name="Jane Doe", age=42, sex="F", weight=60.0, height=1.65, bmi=22.0)
    defaults.update(overrides)
    return Patient(**defaults)


def test_add_and_get(session):
    repo = SqlModelPatientRepository(session)
    patient = repo.add(_make_patient())
    repo.commit()
    repo.refresh(patient)

    assert patient.id is not None
    assert repo.get(patient.id) == patient


def test_get_missing_returns_none(session):
    repo = SqlModelPatientRepository(session)
    assert repo.get(999) is None


def test_save_updates_existing(session):
    repo = SqlModelPatientRepository(session)
    patient = repo.add(_make_patient())
    repo.commit()
    repo.refresh(patient)

    patient.name = "Updated Name"
    repo.save(patient)
    repo.commit()
    repo.refresh(patient)

    assert repo.get(patient.id).name == "Updated Name"


def test_delete_removes_entity(session):
    repo = SqlModelPatientRepository(session)
    patient = repo.add(_make_patient())
    repo.commit()
    repo.refresh(patient)
    patient_id = patient.id

    repo.delete(patient)
    repo.commit()

    assert repo.get(patient_id) is None
