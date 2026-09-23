from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas import DiagnosisRegionPayload
from app.services.diagnosis_region_creator import DiagnosisRegionCreator
from tests.unit.services.conftest import make_diagnosis, make_exam, make_user


@pytest.fixture()
def creator(diagnosis_repository, diagnosis_region_repository, exam_repository, diagnosis_payload_service):
    return DiagnosisRegionCreator(
        diagnosis_repository, diagnosis_region_repository, exam_repository, diagnosis_payload_service
    )


def test_create_raises_for_invalid_payload(session, creator):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam)
    user = make_user(session)

    with pytest.raises(ValidationError):
        creator.create(diagnosis.id, DiagnosisRegionPayload(x=-1, y=0, width=10, height=10), user)


def test_create_raises_not_found_for_missing_diagnosis(session, creator):
    user = make_user(session)
    with pytest.raises(NotFoundError):
        creator.create(999, DiagnosisRegionPayload(x=1, y=1, width=10, height=10), user)


def test_create_auto_confirms_pending_doctor_added_diagnosis(session, creator):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, source="doctor_added", review_status="pending")
    user = make_user(session)

    payload = creator.create(diagnosis.id, DiagnosisRegionPayload(x=1, y=1, width=10, height=10), user)

    assert diagnosis.review_status == "confirmed"
    assert payload["regions_count"] == 1


def test_create_syncs_legacy_region_fields(session, creator):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam)
    user = make_user(session)

    creator.create(diagnosis.id, DiagnosisRegionPayload(x=2, y=3, width=10, height=10), user)

    assert diagnosis.region_x == 2
    assert diagnosis.region_y == 3
