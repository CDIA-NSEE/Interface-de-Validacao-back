from __future__ import annotations

from datetime import date

import pytest

from app.core.exceptions import ValidationError
from app.models import Diagnosis, DiagnosisRegion, Exam, Patient
from app.schemas import DiagnosisRegionPayload
from app.services.diagnosis_region_shared import sync_legacy_region_fields, validate_region_payload


def test_validate_region_payload_accepts_valid_bounds():
    validate_region_payload(DiagnosisRegionPayload(x=10, y=10, width=20, height=20))


def test_validate_region_payload_rejects_out_of_range_coords():
    with pytest.raises(ValidationError):
        validate_region_payload(DiagnosisRegionPayload(x=-1, y=10, width=20, height=20))
    with pytest.raises(ValidationError):
        validate_region_payload(DiagnosisRegionPayload(x=10, y=101, width=20, height=20))


def test_validate_region_payload_rejects_non_positive_dimensions():
    with pytest.raises(ValidationError):
        validate_region_payload(DiagnosisRegionPayload(x=10, y=10, width=0, height=20))


def test_validate_region_payload_rejects_region_outside_image():
    with pytest.raises(ValidationError):
        validate_region_payload(DiagnosisRegionPayload(x=90, y=10, width=20, height=20))


def _make_exam_and_diagnosis(session):
    patient = Patient(name="A", age=40, sex="F", weight=60, height=1.6, bmi=23.4)
    session.add(patient)
    session.commit()
    session.refresh(patient)

    exam = Exam(
        exam_code="ECG1",
        patient_id=patient.id,
        exam_date=date(2026, 1, 1),
        category="rotina",
        exam_type="repouso",
    )
    session.add(exam)
    session.commit()
    session.refresh(exam)

    diagnosis = Diagnosis(exam_id=exam.id, name="Infarto")
    session.add(diagnosis)
    session.commit()
    session.refresh(diagnosis)
    return exam, diagnosis


def test_sync_legacy_region_fields_uses_first_region(session, diagnosis_region_repository):
    exam, diagnosis = _make_exam_and_diagnosis(session)
    region = DiagnosisRegion(
        exam_id=exam.id,
        diagnosis_id=diagnosis.id,
        x=1,
        y=2,
        width=3,
        height=4,
        created_by_name="Dr",
    )
    session.add(region)
    session.commit()

    sync_legacy_region_fields(diagnosis_region_repository, diagnosis)

    assert diagnosis.region_x == 1
    assert diagnosis.region_y == 2
    assert diagnosis.region_width == 3
    assert diagnosis.region_height == 4


def test_sync_legacy_region_fields_clears_when_no_regions(session, diagnosis_region_repository):
    _, diagnosis = _make_exam_and_diagnosis(session)
    diagnosis.region_x = 1
    diagnosis.region_y = 1
    diagnosis.region_width = 1
    diagnosis.region_height = 1

    sync_legacy_region_fields(diagnosis_region_repository, diagnosis)

    assert diagnosis.region_x is None
    assert diagnosis.region_y is None
    assert diagnosis.region_width is None
    assert diagnosis.region_height is None
