from __future__ import annotations

from datetime import date
from typing import Any

import pytest
from sqlmodel import Session, SQLModel, create_engine

import app.models  # noqa: F401 - ensures all tables are registered on SQLModel.metadata
from app.core.settings import Settings
from app.models import Diagnosis, Exam, Patient, User
from app.repositories.interfaces.config_repository import ConfigRepository
from app.repositories.interfaces.metadata_repository import MetadataRepository
from app.repositories.sqlmodel.diagnosis_region_repository import SqlModelDiagnosisRegionRepository
from app.repositories.sqlmodel.diagnosis_repository import SqlModelDiagnosisRepository
from app.repositories.sqlmodel.diagnosis_validation_repository import (
    SqlModelDiagnosisValidationRepository,
)
from app.repositories.sqlmodel.exam_draft_repository import SqlModelExamDraftRepository
from app.repositories.sqlmodel.exam_repository import SqlModelExamRepository
from app.repositories.sqlmodel.patient_repository import SqlModelPatientRepository
from app.repositories.sqlmodel.review_repository import SqlModelReviewRepository
from app.repositories.sqlmodel.user_repository import SqlModelUserRepository
from app.repositories.sqlmodel.validation_cycle_repository import SqlModelValidationCycleRepository
from app.services.cache.null_cache_client import NullCacheClient
from app.services.diagnosis_payload_service import DiagnosisPayloadService
from app.services.diagnosis_standardizer import DiagnosisStandardizer
from app.services.exam_payload_service import ExamPayloadService
from app.services.validation_context_service import ValidationContextService
from app.services.validation_queue_service import ValidationQueueService


class FakeConfigRepository(ConfigRepository):
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data or {}

    def load_json(self, name: str, default: Any) -> Any:
        return self._data.get(name, default)


class FakeMetadataRepository(MetadataRepository):
    def __init__(self, records: list[dict] | None = None, images: dict[int, dict] | None = None) -> None:
        self._records = records or []
        self._images = images or {}

    def load_records(self) -> list[dict]:
        return self._records

    def load_image(self, metadata_id: int | None) -> dict | None:
        if metadata_id is None:
            return None
        return self._images.get(metadata_id)


@pytest.fixture()
def session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture()
def patient_repository(session):
    return SqlModelPatientRepository(session)


@pytest.fixture()
def exam_repository(session):
    return SqlModelExamRepository(session)


@pytest.fixture()
def diagnosis_repository(session):
    return SqlModelDiagnosisRepository(session)


@pytest.fixture()
def diagnosis_region_repository(session):
    return SqlModelDiagnosisRegionRepository(session)


@pytest.fixture()
def diagnosis_validation_repository(session):
    return SqlModelDiagnosisValidationRepository(session)


@pytest.fixture()
def review_repository(session):
    return SqlModelReviewRepository(session)


@pytest.fixture()
def exam_draft_repository(session):
    return SqlModelExamDraftRepository(session)


@pytest.fixture()
def user_repository(session):
    return SqlModelUserRepository(session)


@pytest.fixture()
def validation_cycle_repository(session):
    return SqlModelValidationCycleRepository(session)


@pytest.fixture()
def fake_config_repository():
    return FakeConfigRepository()


@pytest.fixture()
def fake_metadata_repository():
    return FakeMetadataRepository()


@pytest.fixture()
def settings():
    return Settings()


@pytest.fixture()
def null_cache_client():
    return NullCacheClient()


@pytest.fixture()
def diagnosis_standardizer(fake_config_repository):
    return DiagnosisStandardizer(fake_config_repository)


@pytest.fixture()
def validation_context_service(fake_config_repository, settings, diagnosis_standardizer):
    return ValidationContextService(fake_config_repository, settings, diagnosis_standardizer)


@pytest.fixture()
def diagnosis_payload_service(
    diagnosis_region_repository,
    diagnosis_validation_repository,
    diagnosis_standardizer,
    validation_context_service,
):
    return DiagnosisPayloadService(
        diagnosis_region_repository,
        diagnosis_validation_repository,
        diagnosis_standardizer,
        validation_context_service,
    )


@pytest.fixture()
def validation_queue_service(
    exam_repository, diagnosis_repository, diagnosis_standardizer, diagnosis_payload_service
):
    return ValidationQueueService(
        exam_repository, diagnosis_repository, diagnosis_standardizer, diagnosis_payload_service
    )


@pytest.fixture()
def exam_payload_service(
    patient_repository,
    review_repository,
    exam_draft_repository,
    diagnosis_repository,
    diagnosis_payload_service,
    validation_context_service,
    validation_queue_service,
):
    return ExamPayloadService(
        patient_repository,
        review_repository,
        exam_draft_repository,
        diagnosis_repository,
        diagnosis_payload_service,
        validation_context_service,
        validation_queue_service,
    )


def make_patient(session: Session, **overrides: Any) -> Patient:
    defaults = dict(name="Paciente Teste", age=40, sex="F", weight=60.0, height=1.6, bmi=23.4)
    defaults.update(overrides)
    patient = Patient(**defaults)
    session.add(patient)
    session.commit()
    session.refresh(patient)
    return patient


def make_exam(session: Session, patient: Patient | None = None, **overrides: Any) -> Exam:
    patient = patient or make_patient(session)
    defaults = dict(
        exam_code=f"ECG-{patient.id}-{overrides.get('exam_code', 'X')}",
        patient_id=patient.id,
        exam_date=date(2026, 1, 1),
        category="rotina",
        exam_type="repouso",
    )
    defaults.update(overrides)
    defaults["patient_id"] = patient.id
    exam = Exam(**defaults)
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return exam


def make_diagnosis(session: Session, exam: Exam, **overrides: Any) -> Diagnosis:
    defaults = dict(exam_id=exam.id, name="Diagnostico Teste")
    defaults.update(overrides)
    defaults["exam_id"] = exam.id
    diagnosis = Diagnosis(**defaults)
    session.add(diagnosis)
    session.commit()
    session.refresh(diagnosis)
    return diagnosis


def make_user(session: Session, **overrides: Any) -> User:
    defaults = dict(username="dr.teste", full_name="Dr. Teste", hashed_password="x")
    defaults.update(overrides)
    user = User(**defaults)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user
