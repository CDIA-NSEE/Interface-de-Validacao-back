from __future__ import annotations

from datetime import UTC, date, datetime

from app.models import Exam, Patient
from app.repositories.sqlmodel.exam_repository import SqlModelExamRepository
from app.repositories.sqlmodel.patient_repository import SqlModelPatientRepository


def _make_patient(session) -> Patient:
    patient_repo = SqlModelPatientRepository(session)
    patient = patient_repo.add(Patient(name="Jane Doe", age=42, sex="F", weight=60.0, height=1.65, bmi=22.0))
    patient_repo.commit()
    patient_repo.refresh(patient)
    return patient


def _make_exam(patient_id: int, **overrides) -> Exam:
    defaults = dict(
        exam_code="EX-001",
        patient_id=patient_id,
        exam_date=date(2026, 1, 1),
        category="rotina",
        exam_type="repouso",
    )
    defaults.update(overrides)
    return Exam(**defaults)


def test_list_all(session):
    patient = _make_patient(session)
    repo = SqlModelExamRepository(session)
    repo.add(_make_exam(patient.id, exam_code="EX-001"))
    repo.add(_make_exam(patient.id, exam_code="EX-002"))
    repo.commit()

    exams = repo.list_all()
    assert {exam.exam_code for exam in exams} == {"EX-001", "EX-002"}


def test_first_returns_none_when_empty(session):
    repo = SqlModelExamRepository(session)
    assert repo.first() is None


def test_list_recent_orders_by_exam_date_and_created_at_desc(session):
    patient = _make_patient(session)
    repo = SqlModelExamRepository(session)
    older = repo.add(_make_exam(patient.id, exam_code="EX-OLD", exam_date=date(2026, 1, 1)))
    older.created_at = datetime(2026, 1, 1, tzinfo=UTC)
    newer = repo.add(_make_exam(patient.id, exam_code="EX-NEW", exam_date=date(2026, 2, 1)))
    newer.created_at = datetime(2026, 2, 1, tzinfo=UTC)
    repo.commit()

    recent = repo.list_recent()
    assert [exam.exam_code for exam in recent] == ["EX-NEW", "EX-OLD"]


def test_list_by_codes(session):
    patient = _make_patient(session)
    repo = SqlModelExamRepository(session)
    repo.add(_make_exam(patient.id, exam_code="EX-001"))
    repo.add(_make_exam(patient.id, exam_code="EX-002"))
    repo.add(_make_exam(patient.id, exam_code="EX-003"))
    repo.commit()

    codes = {exam.exam_code for exam in repo.list_by_codes(["EX-001", "EX-003"])}
    assert codes == {"EX-001", "EX-003"}


def test_first_for_patient(session):
    patient = _make_patient(session)
    repo = SqlModelExamRepository(session)
    exam = repo.add(_make_exam(patient.id))
    repo.commit()
    repo.refresh(exam)

    assert repo.first_for_patient(patient.id).id == exam.id
    assert repo.first_for_patient(999) is None


def test_list_imported_metadata_hashes_excludes_none(session):
    patient = _make_patient(session)
    repo = SqlModelExamRepository(session)
    repo.add(_make_exam(patient.id, exam_code="EX-001", metadata_hash="hash-1"))
    repo.add(_make_exam(patient.id, exam_code="EX-002", metadata_hash=None))
    repo.commit()

    assert repo.list_imported_metadata_hashes() == {"hash-1"}
