from __future__ import annotations

import pytest

from app.core.exceptions import ValidationError
from app.models import DiagnosisRegion, DiagnosisValidation
from tests.unit.services.conftest import make_diagnosis, make_exam


def test_diagnosis_region_payloads_prefers_new_regions_over_legacy(
    session, diagnosis_payload_service, diagnosis_region_repository
):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, region_x=1, region_y=1, region_width=2, region_height=2)
    session.add(
        DiagnosisRegion(
            exam_id=exam.id, diagnosis_id=diagnosis.id, x=5, y=5, width=6, height=6, created_by_name="Dr"
        )
    )
    session.commit()

    payloads = diagnosis_payload_service.diagnosis_region_payloads(diagnosis)

    assert len(payloads) == 1
    assert payloads[0]["legacy"] is False
    assert payloads[0]["x"] == 5


def test_diagnosis_region_payloads_falls_back_to_legacy_fields(session, diagnosis_payload_service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, region_x=1, region_y=1, region_width=2, region_height=2)

    payloads = diagnosis_payload_service.diagnosis_region_payloads(diagnosis)

    assert len(payloads) == 1
    assert payloads[0]["legacy"] is True


def test_diagnosis_region_payloads_empty_when_no_regions(session, diagnosis_payload_service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam)

    assert diagnosis_payload_service.diagnosis_region_payloads(diagnosis) == []


def test_ensure_region_before_confirm_raises_for_infarto_without_region(session, diagnosis_payload_service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Infarto agudo")

    with pytest.raises(ValidationError):
        diagnosis_payload_service.ensure_region_before_confirm(diagnosis)


def test_ensure_region_before_confirm_passes_when_region_present(session, diagnosis_payload_service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Infarto agudo", region_width=1, region_height=1)

    diagnosis_payload_service.ensure_region_before_confirm(diagnosis)


def test_effective_review_status_uses_latest_validation(
    session, diagnosis_payload_service, validation_context_service
):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Ritmo sinusal", review_status="pending")
    context = validation_context_service.active_context()
    session.add(
        DiagnosisValidation(
            exam_id=exam.id,
            diagnosis_id=diagnosis.id,
            standard_text="Ritmo sinusal",
            cycle_key=context.cycle_key,
            review_status="confirmed",
            reviewer_name="Dr",
        )
    )
    session.commit()

    assert diagnosis_payload_service.effective_review_status(diagnosis, context) == "confirmed"


def test_build_includes_ai_suggested_and_daily_required_flags(
    session, diagnosis_payload_service, validation_context_service, fake_config_repository
):
    fake_config_repository._data["validation_calendar.json"] = {
        "cycle_key": "c1",
        "cycle_label": "Ciclo 1",
        "cycle_start_date": None,
        "active_day_index": 1,
        "general_review_day": 30,
        "days": [{"day_index": 1, "standard_diagnosis": "Ritmo sinusal"}],
    }
    exam = make_exam(session, exam_code="ECG-AI")
    diagnosis = make_diagnosis(session, exam, name="Ritmo sinusal")
    context = validation_context_service.active_context()
    recommendations = {
        "enabled": True,
        "suggestions": [{"exam_code": "ECG-AI", "standard_diagnoses": ["Ritmo sinusal"]}],
    }

    payload = diagnosis_payload_service.build(
        diagnosis, context=context, exam_code="ECG-AI", ai_recommendations=recommendations
    )

    assert payload["ai_suggested"] is True
    assert payload["daily_required"] is True
    assert payload["standard_text"] == "Ritmo sinusal"
