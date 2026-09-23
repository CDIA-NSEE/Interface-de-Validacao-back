from __future__ import annotations

from datetime import date

from app.models import Diagnosis, DiagnosisRegion, Exam, Patient
from app.repositories.sqlmodel.diagnosis_region_repository import SqlModelDiagnosisRegionRepository
from app.repositories.sqlmodel.diagnosis_repository import SqlModelDiagnosisRepository
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


def test_list_for_diagnosis_orders_by_created_at_then_id(session):
    diagnosis = _make_diagnosis(session)
    repo = SqlModelDiagnosisRegionRepository(session)
    repo.add(
        DiagnosisRegion(
            exam_id=diagnosis.exam_id,
            diagnosis_id=diagnosis.id,
            x=1,
            y=1,
            width=10,
            height=10,
            created_by_name="Dr. Who",
        )
    )
    repo.add(
        DiagnosisRegion(
            exam_id=diagnosis.exam_id,
            diagnosis_id=diagnosis.id,
            x=2,
            y=2,
            width=10,
            height=10,
            created_by_name="Dr. Who",
        )
    )
    repo.commit()

    regions = repo.list_for_diagnosis(diagnosis.id)
    assert len(regions) == 2
    assert regions[0].id < regions[1].id


def test_list_for_exams(session):
    diagnosis = _make_diagnosis(session)
    repo = SqlModelDiagnosisRegionRepository(session)
    repo.add(
        DiagnosisRegion(
            exam_id=diagnosis.exam_id,
            diagnosis_id=diagnosis.id,
            x=1,
            y=1,
            width=10,
            height=10,
            created_by_name="Dr. Who",
        )
    )
    repo.commit()

    assert len(repo.list_for_exams([diagnosis.exam_id])) == 1
    assert repo.list_for_exams([999]) == []
