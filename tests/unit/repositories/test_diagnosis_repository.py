from __future__ import annotations

from datetime import date

from app.models import Diagnosis, Exam, Patient
from app.repositories.sqlmodel.diagnosis_repository import SqlModelDiagnosisRepository
from app.repositories.sqlmodel.exam_repository import SqlModelExamRepository
from app.repositories.sqlmodel.patient_repository import SqlModelPatientRepository


def _make_exam(session) -> Exam:
    patient_repo = SqlModelPatientRepository(session)
    patient = patient_repo.add(Patient(name="Jane Doe", age=42, sex="F", weight=60.0, height=1.65, bmi=22.0))
    patient_repo.commit()
    patient_repo.refresh(patient)

    exam_repo = SqlModelExamRepository(session)
    exam = exam_repo.add(
        Exam(
            exam_code="EX-001",
            patient_id=patient.id,
            exam_date=date(2026, 1, 1),
            category="rotina",
            exam_type="repouso",
        )
    )
    exam_repo.commit()
    exam_repo.refresh(exam)
    return exam


def test_list_for_exam_orders_by_created_at(session):
    exam = _make_exam(session)
    repo = SqlModelDiagnosisRepository(session)
    repo.add(Diagnosis(exam_id=exam.id, name="Sinus rhythm", source="original"))
    repo.add(Diagnosis(exam_id=exam.id, name="Tachycardia", source="reviewer"))
    repo.commit()

    diagnoses = repo.list_for_exam(exam.id)
    assert {d.name for d in diagnoses} == {"Sinus rhythm", "Tachycardia"}


def test_list_original_for_exam_filters_by_source(session):
    exam = _make_exam(session)
    repo = SqlModelDiagnosisRepository(session)
    repo.add(Diagnosis(exam_id=exam.id, name="Sinus rhythm", source="original"))
    repo.add(Diagnosis(exam_id=exam.id, name="Tachycardia", source="reviewer"))
    repo.commit()

    original = repo.list_original_for_exam(exam.id)
    assert [d.name for d in original] == ["Sinus rhythm"]


def test_list_for_exams(session):
    exam = _make_exam(session)
    repo = SqlModelDiagnosisRepository(session)
    repo.add(Diagnosis(exam_id=exam.id, name="Sinus rhythm"))
    repo.commit()

    assert len(repo.list_for_exams([exam.id])) == 1
    assert repo.list_for_exams([999]) == []
