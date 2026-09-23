from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas import DiagnosisCreate
from app.services.diagnosis_creator import DiagnosisCreator
from app.services.diagnosis_options_service import DiagnosisOptionsService
from tests.unit.services.conftest import make_exam, make_user


@pytest.fixture()
def creator(
    diagnosis_repository,
    diagnosis_region_repository,
    exam_repository,
    diagnosis_standardizer,
    fake_metadata_repository,
    null_cache_client,
    diagnosis_payload_service,
    fake_config_repository,
):
    fake_config_repository._data["diagnosis_groupings.json"] = [
        {"standard_text": "Infarto", "original_texts": []},
        {"standard_text": "Ritmo sinusal", "original_texts": []},
    ]
    options_service = DiagnosisOptionsService(
        fake_metadata_repository, diagnosis_standardizer, null_cache_client, 300
    )
    return DiagnosisCreator(
        diagnosis_repository,
        diagnosis_region_repository,
        exam_repository,
        diagnosis_standardizer,
        options_service,
        diagnosis_payload_service,
    )


def test_create_raises_not_found_for_missing_exam(session, creator):
    user = make_user(session)
    with pytest.raises(NotFoundError):
        creator.create(999, DiagnosisCreate(name="Ritmo sinusal"), user)


def test_create_raises_when_name_blank(session, creator):
    exam = make_exam(session)
    user = make_user(session)
    with pytest.raises(ValidationError):
        creator.create(exam.id, DiagnosisCreate(name="   "), user)


def test_create_raises_when_not_a_standardized_option(session, creator):
    exam = make_exam(session)
    user = make_user(session)
    with pytest.raises(ValidationError):
        creator.create(exam.id, DiagnosisCreate(name="Diagnostico invalido"), user)


def test_create_marks_confirmed_when_region_not_required(session, creator):
    exam = make_exam(session)
    user = make_user(session)

    payload = creator.create(exam.id, DiagnosisCreate(name="Ritmo sinusal"), user)

    assert payload["source"] == "doctor_added"
    assert payload["legacy_review_status"] == "confirmed"


def test_create_marks_pending_when_infarto_without_region(session, creator):
    exam = make_exam(session)
    user = make_user(session)

    payload = creator.create(exam.id, DiagnosisCreate(name="Infarto"), user)

    assert payload["legacy_review_status"] == "pending"


def test_create_with_inline_region_confirms_and_creates_region(session, creator):
    exam = make_exam(session)
    user = make_user(session)

    payload = creator.create(
        exam.id,
        DiagnosisCreate(name="Infarto", region_x=1, region_y=1, region_width=10, region_height=10),
        user,
    )

    assert payload["legacy_review_status"] == "confirmed"
    assert payload["regions_count"] == 1


def test_create_with_invalid_inline_region_raises(session, creator):
    exam = make_exam(session)
    user = make_user(session)

    with pytest.raises(ValidationError):
        creator.create(
            exam.id,
            DiagnosisCreate(name="Infarto", region_x=-1, region_y=1, region_width=10, region_height=10),
            user,
        )
