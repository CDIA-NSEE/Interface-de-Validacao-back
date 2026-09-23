from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models import DiagnosisRegion, DiagnosisValidation
from app.services.diagnosis_region_deleter import DiagnosisRegionDeleter
from tests.unit.services.conftest import make_diagnosis, make_exam


@pytest.fixture()
def deleter(
    diagnosis_repository,
    diagnosis_region_repository,
    exam_repository,
    diagnosis_standardizer,
    diagnosis_payload_service,
):
    return DiagnosisRegionDeleter(
        diagnosis_repository,
        diagnosis_region_repository,
        exam_repository,
        diagnosis_standardizer,
        diagnosis_payload_service,
    )


def _make_region(session, exam, diagnosis, **overrides):
    defaults = dict(x=1, y=1, width=2, height=2, created_by_name="Dr")
    defaults.update(overrides)
    region = DiagnosisRegion(exam_id=exam.id, diagnosis_id=diagnosis.id, **defaults)
    session.add(region)
    session.commit()
    session.refresh(region)
    return region


def test_delete_raises_not_found_for_mismatched_region(session, deleter):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam)
    other_diagnosis = make_diagnosis(session, exam)
    region = _make_region(session, exam, other_diagnosis)

    with pytest.raises(NotFoundError):
        deleter.delete(diagnosis.id, region.id)


def test_delete_blocks_removing_last_region_of_confirmed_infarto(
    session, deleter, validation_context_service
):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Infarto agudo")
    region = _make_region(session, exam, diagnosis)
    context = validation_context_service.active_context()
    session.add(
        DiagnosisValidation(
            exam_id=exam.id,
            diagnosis_id=diagnosis.id,
            standard_text="Infarto agudo",
            cycle_key=context.cycle_key,
            review_status="confirmed",
            reviewer_name="Dr",
        )
    )
    session.commit()

    with pytest.raises(ValidationError):
        deleter.delete(diagnosis.id, region.id)


def test_delete_allows_removing_region_when_not_last(session, deleter):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Infarto agudo")
    region_a = _make_region(session, exam, diagnosis, x=1)
    _make_region(session, exam, diagnosis, x=2)

    payload = deleter.delete(diagnosis.id, region_a.id)

    assert payload["regions_count"] == 1


def test_delete_clears_legacy_fields_when_last_non_required_region_removed(session, deleter):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Ritmo sinusal")
    region = _make_region(session, exam, diagnosis)

    payload = deleter.delete(diagnosis.id, region.id)

    assert payload["regions_count"] == 0
    assert diagnosis.region_x is None
