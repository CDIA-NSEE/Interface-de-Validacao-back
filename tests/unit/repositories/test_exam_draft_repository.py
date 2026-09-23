from __future__ import annotations

from datetime import date

from app.models import Exam, ExamDraft, Patient, User
from app.repositories.sqlmodel.exam_draft_repository import SqlModelExamDraftRepository
from app.repositories.sqlmodel.exam_repository import SqlModelExamRepository
from app.repositories.sqlmodel.patient_repository import SqlModelPatientRepository
from app.repositories.sqlmodel.user_repository import SqlModelUserRepository


def _make_exam_and_user(session) -> tuple[Exam, User]:
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

    user_repo = SqlModelUserRepository(session)
    user = user_repo.add(User(username="doctor1", full_name="Dr. One", hashed_password="hash"))
    user_repo.commit()
    user_repo.refresh(user)

    return exam, user


def test_get_for_exam_and_reviewer(session):
    exam, user = _make_exam_and_user(session)
    repo = SqlModelExamDraftRepository(session)
    repo.add(ExamDraft(exam_id=exam.id, reviewer_id=user.id, notes="draft notes"))
    repo.commit()

    draft = repo.get_for_exam_and_reviewer(exam.id, user.id)
    assert draft is not None
    assert draft.notes == "draft notes"
    assert repo.get_for_exam_and_reviewer(exam.id, 999) is None


def test_list_for_exams(session):
    exam, user = _make_exam_and_user(session)
    repo = SqlModelExamDraftRepository(session)
    repo.add(ExamDraft(exam_id=exam.id, reviewer_id=user.id))
    repo.commit()

    assert len(repo.list_for_exams([exam.id])) == 1
    assert repo.list_for_exams([999]) == []
