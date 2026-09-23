from __future__ import annotations

from datetime import date

from app.services.diagnosis_standardizer import DiagnosisStandardizer
from app.services.validation_context_service import ValidationContextService


def _service(fake_config_repository, settings):
    return ValidationContextService(
        fake_config_repository, settings, DiagnosisStandardizer(fake_config_repository)
    )


def test_active_context_uses_env_cycle_day_over_calendar(fake_config_repository, settings):
    fake_config_repository._data["validation_calendar.json"] = {
        "cycle_key": "c1",
        "cycle_label": "Ciclo 1",
        "cycle_start_date": None,
        "active_day_index": 5,
        "general_review_day": 30,
        "days": [{"day_index": 5, "standard_diagnosis": "Should not be used"}],
    }
    settings.validation.cycle_day = "12"
    settings.validation.active_diagnosis = "Ritmo sinusal"

    context = _service(fake_config_repository, settings).active_context(date(2026, 1, 1))

    assert context.day_index == 12
    assert context.active_standard_diagnosis == "Ritmo sinusal"
    assert context.is_configured is True


def test_active_context_falls_back_to_cycle_start_date(fake_config_repository, settings):
    fake_config_repository._data["validation_calendar.json"] = {
        "cycle_key": "c1",
        "cycle_label": "Ciclo 1",
        "cycle_start_date": "2026-01-01",
        "active_day_index": None,
        "general_review_day": 30,
        "days": [{"day_index": 3, "standard_diagnosis": "Infarto"}],
    }

    context = _service(fake_config_repository, settings).active_context(date(2026, 1, 3))

    assert context.day_index == 3
    assert context.active_standard_diagnosis == "Infarto"


def test_active_context_general_review_day(fake_config_repository, settings):
    fake_config_repository._data["validation_calendar.json"] = {
        "cycle_key": "c1",
        "cycle_label": "Ciclo 1",
        "cycle_start_date": None,
        "active_day_index": 30,
        "general_review_day": 30,
        "days": [],
    }

    context = _service(fake_config_repository, settings).active_context()

    assert context.is_general_review_day is True
    assert context.is_configured is True


def test_active_context_not_configured_when_no_day_or_diagnosis(fake_config_repository, settings):
    context = _service(fake_config_repository, settings).active_context()

    assert context.day_index is None
    assert context.is_configured is False


def test_load_ai_recommendations_disabled_when_malformed(fake_config_repository, settings):
    fake_config_repository._data["ai_recommendations.json"] = {"enabled": "not-a-bool"}

    recommendations = _service(fake_config_repository, settings).load_ai_recommendations()

    assert recommendations == {"enabled": False, "suggestions": []}


def test_load_ai_recommendations_env_override_disables(fake_config_repository, settings):
    fake_config_repository._data["ai_recommendations.json"] = {
        "enabled": True,
        "suggestions": [{"exam_code": "ECG1", "standard_diagnoses": ["Infarto"]}],
    }
    settings.validation.ai_mode_enabled = "false"

    recommendations = _service(fake_config_repository, settings).load_ai_recommendations()

    assert recommendations == {"enabled": False, "suggestions": []}


def test_load_ai_recommendations_dedupes_normalized_diagnoses(fake_config_repository, settings):
    fake_config_repository._data["ai_recommendations.json"] = {
        "enabled": True,
        "suggestions": [{"exam_code": "ECG1", "standard_diagnoses": ["Infarto", "infarto", "Outro"]}],
    }

    recommendations = _service(fake_config_repository, settings).load_ai_recommendations()

    assert recommendations["enabled"] is True
    assert recommendations["suggestions"][0]["standard_diagnoses"] == ["Infarto", "Outro"]


def test_ai_suggested_matches_all_exams_wildcard(fake_config_repository, settings):
    service = _service(fake_config_repository, settings)
    recommendations = {
        "enabled": True,
        "suggestions": [{"exam_code": "*", "standard_diagnoses": ["Infarto"]}],
    }

    assert service.ai_suggested("ECG-999", "infarto", recommendations) is True
    assert service.ai_suggested("ECG-999", "outro", recommendations) is False


def test_ai_suggested_false_when_recommendations_disabled(fake_config_repository, settings):
    service = _service(fake_config_repository, settings)
    assert service.ai_suggested("ECG1", "Infarto", {"enabled": False, "suggestions": []}) is False


def test_load_support_contact_env_override_replaces_channels(fake_config_repository, settings):
    fake_config_repository._data["support_contact.json"] = {
        "title": "Suporte",
        "description": "desc",
        "channels": [{"label": "Old", "type": "email", "value": "old@old.com"}],
    }
    settings.support.label = "Novo"
    settings.support.value = "novo@novo.com"
    settings.support.type = "email"

    contact = _service(fake_config_repository, settings).load_support_contact()

    assert contact["channels"] == [{"label": "Novo", "type": "email", "value": "novo@novo.com"}]


def test_load_support_contact_filters_incomplete_channels(fake_config_repository, settings):
    fake_config_repository._data["support_contact.json"] = {
        "title": "Suporte",
        "description": "desc",
        "channels": [
            {"label": "", "type": "email", "value": "missing-label@x.com"},
            {"label": "Ok", "type": "email", "value": "ok@x.com"},
        ],
    }

    contact = _service(fake_config_repository, settings).load_support_contact()

    assert contact["channels"] == [{"label": "Ok", "type": "email", "value": "ok@x.com"}]


def test_context_payload_combines_context_ai_and_support(fake_config_repository, settings):
    fake_config_repository._data["ai_recommendations.json"] = {"enabled": True, "suggestions": []}

    payload = _service(fake_config_repository, settings).context_payload()

    assert payload["ai_mode_enabled"] is True
    assert "support_contact" in payload
    assert "cycle_key" in payload
