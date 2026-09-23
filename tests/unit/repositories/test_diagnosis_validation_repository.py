from __future__ import annotations

from datetime import date

from app.models import Diagnosis, DiagnosisValidation, Exam, Patient
from app.repositories.sqlmodel.diagnosis_repository import SqlModelDiagnosisRepository
from app.repositories.sqlmodel.diagnosis_validation_repository import SqlModelDiagnosisValidationRepository
from app.repositories.sqlmodel.exam_repository import SqlModelExamRepository
from app.repositories.sqlmodel.patient_repository import SqlModelPatientRepository


def _make_diagnosis(session) -> Diagnosis:
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

    diagnosis_repo = SqlModelDiagnosisRepository(session)
    diagnosis = diagnosis_repo.add(Diagnosis(exam_id=exam.id, name="Sinus rhythm"))
    diagnosis_repo.commit()
    diagnosis_repo.refresh(diagnosis)
    return diagnosis


def test_list_for_exam_and_cycle_filters_and_orders_desc(session):
    diagnosis = _make_diagnosis(session)
    repo = SqlModelDiagnosisValidationRepository(session)
    repo.add(
        DiagnosisValidation(
            exam_id=diagnosis.exam_id,
            diagnosis_id=diagnosis.id,
            standard_text="Sinus rhythm",
            cycle_key="cycle-a",
            review_status="pending",
            reviewer_name="Dr. A",
        )
    )
    repo.add(
        DiagnosisValidation(
            exam_id=diagnosis.exam_id,
            diagnosis_id=diagnosis.id,
            standard_text="Sinus rhythm",
            cycle_key="cycle-b",
            review_status="pending",
            reviewer_name="Dr. B",
        )
    )
    repo.commit()

    results = repo.list_for_exam_and_cycle(diagnosis.exam_id, "cycle-a")
    assert len(results) == 1
    assert results[0].cycle_key == "cycle-a"


def test_list_for_exams(session):
    diagnosis = _make_diagnosis(session)
    repo = SqlModelDiagnosisValidationRepository(session)
    repo.add(
        DiagnosisValidation(
            exam_id=diagnosis.exam_id,
            diagnosis_id=diagnosis.id,
            standard_text="Sinus rhythm",
            review_status="pending",
            reviewer_name="Dr. A",
        )
    )
    repo.commit()

    assert len(repo.list_for_exams([diagnosis.exam_id])) == 1
    assert repo.list_for_exams([999]) == []
