from __future__ import annotations

from datetime import date

from app.models import Exam, Patient, Review
from app.repositories.sqlmodel.exam_repository import SqlModelExamRepository
from app.repositories.sqlmodel.patient_repository import SqlModelPatientRepository
from app.repositories.sqlmodel.review_repository import SqlModelReviewRepository


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
    repo = SqlModelReviewRepository(session)
    repo.add(
        Review(exam_id=exam.id, doctor_name="Dr. A", status_before="nao_validado", status_after="valido")
    )
    repo.commit()

    reviews = repo.list_for_exam(exam.id)
    assert len(reviews) == 1


def test_list_completed_filters_status_after(session):
    exam = _make_exam(session)
    repo = SqlModelReviewRepository(session)
    repo.add(
        Review(exam_id=exam.id, doctor_name="Dr. A", status_before="nao_validado", status_after="valido")
    )
    repo.add(
        Review(exam_id=exam.id, doctor_name="Dr. B", status_before="nao_validado", status_after="pendente")
    )
    repo.commit()

    completed = repo.list_completed()
    assert len(completed) == 1
    assert completed[0].status_after == "valido"


def test_list_for_exams(session):
    exam = _make_exam(session)
    repo = SqlModelReviewRepository(session)
    repo.add(
        Review(exam_id=exam.id, doctor_name="Dr. A", status_before="nao_validado", status_after="valido")
    )
    repo.commit()

    assert len(repo.list_for_exams([exam.id])) == 1
    assert repo.list_for_exams([999]) == []
