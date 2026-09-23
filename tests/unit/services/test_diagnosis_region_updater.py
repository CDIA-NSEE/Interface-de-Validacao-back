from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models import DiagnosisRegion
from app.schemas import DiagnosisRegionPayload
from app.services.diagnosis_region_updater import DiagnosisRegionUpdater
from tests.unit.services.conftest import make_diagnosis, make_exam


@pytest.fixture()
def updater(diagnosis_repository, diagnosis_region_repository, exam_repository, diagnosis_payload_service):
    return DiagnosisRegionUpdater(
        diagnosis_repository, diagnosis_region_repository, exam_repository, diagnosis_payload_service
    )


def _make_region(session, exam, diagnosis):
    region = DiagnosisRegion(
        exam_id=exam.id, diagnosis_id=diagnosis.id, x=1, y=1, width=2, height=2, created_by_name="Dr"
    )
    session.add(region)
    session.commit()
    session.refresh(region)
    return region


def test_update_raises_for_invalid_payload(session, updater):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam)
    region = _make_region(session, exam, diagnosis)

    with pytest.raises(ValidationError):
        updater.update(diagnosis.id, region.id, DiagnosisRegionPayload(x=-1, y=0, width=10, height=10))


def test_update_raises_not_found_for_mismatched_region(session, updater):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam)
    other_diagnosis = make_diagnosis(session, exam)
    region = _make_region(session, exam, other_diagnosis)

    with pytest.raises(NotFoundError):
        updater.update(diagnosis.id, region.id, DiagnosisRegionPayload(x=1, y=1, width=10, height=10))


def test_update_persists_new_coordinates_and_syncs_legacy(session, updater):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam)
    region = _make_region(session, exam, diagnosis)

    payload = updater.update(diagnosis.id, region.id, DiagnosisRegionPayload(x=5, y=6, width=7, height=8))

    assert diagnosis.region_x == 5
    assert diagnosis.region_y == 6
    assert payload["regions"][0]["x"] == 5
