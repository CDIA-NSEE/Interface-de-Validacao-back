from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.schemas import DiagnosisReview
from app.services.diagnosis_review_service import DiagnosisReviewService
from tests.unit.services.conftest import make_diagnosis, make_exam, make_user


@pytest.fixture()
def service(
    diagnosis_repository,
    exam_repository,
    review_repository,
    diagnosis_validation_repository,
    diagnosis_standardizer,
    diagnosis_payload_service,
    exam_payload_service,
    validation_context_service,
):
    return DiagnosisReviewService(
        diagnosis_repository,
        exam_repository,
        review_repository,
        diagnosis_validation_repository,
        diagnosis_standardizer,
        diagnosis_payload_service,
        exam_payload_service,
        validation_context_service,
    )


def test_review_diagnosis_blocks_non_original_source(session, service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, source="doctor_added")

    with pytest.raises(ValidationError):
        service.review_diagnosis(exam.id, diagnosis.id, DiagnosisReview(review_status="confirmed"))


def test_review_diagnosis_blocks_confirming_infarto_without_region(session, service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, source="original", name="Infarto agudo")

    with pytest.raises(ValidationError):
        service.review_diagnosis(exam.id, diagnosis.id, DiagnosisReview(review_status="confirmed"))


def test_review_diagnosis_updates_status(session, service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, source="original", name="Ritmo sinusal")

    payload = service.review_diagnosis(exam.id, diagnosis.id, DiagnosisReview(review_status="rejected"))

    assert diagnosis.review_status == "rejected"
    assert payload["legacy_review_status"] == "rejected"


def test_review_diagnosis_not_found_for_mismatched_exam(session, service):
    exam = make_exam(session)
    other_exam = make_exam(session)
    diagnosis = make_diagnosis(session, other_exam, source="original")

    with pytest.raises(NotFoundError):
        service.review_diagnosis(exam.id, diagnosis.id, DiagnosisReview(review_status="confirmed"))


def test_review_validation_diagnosis_creates_validation_and_transitions_exam(session, service):
    exam = make_exam(session, status_validation="nao_validado")
    diagnosis = make_diagnosis(session, exam, name="Ritmo sinusal")
    user = make_user(session)

    payload = service.review_validation_diagnosis(
        diagnosis.id, DiagnosisReview(review_status="confirmed", notes="ok"), user
    )

    assert exam.status_validation == "em_validacao"
    assert diagnosis.review_status == "confirmed"
    assert payload["id"] == exam.id


def test_review_validation_diagnosis_reuses_existing_validation(
    session, service, diagnosis_validation_repository, validation_context_service
):
    exam = make_exam(session, status_validation="em_validacao")
    diagnosis = make_diagnosis(session, exam, name="Ritmo sinusal")
    user = make_user(session)
    context = validation_context_service.active_context()
    from app.models import DiagnosisValidation

    session.add(
        DiagnosisValidation(
            exam_id=exam.id,
            diagnosis_id=diagnosis.id,
            standard_text="Ritmo sinusal",
            cycle_key=context.cycle_key,
            review_status="rejected",
            reviewer_name="Old",
        )
    )
    session.commit()

    service.review_validation_diagnosis(diagnosis.id, DiagnosisReview(review_status="confirmed"), user)

    validations = diagnosis_validation_repository.list_for_exam_and_cycle(exam.id, context.cycle_key)
    assert len(validations) == 1
    assert validations[0].review_status == "confirmed"
    assert validations[0].reviewer_name == user.full_name


def test_review_validation_diagnosis_blocks_confirming_infarto_without_region(session, service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Infarto agudo")
    user = make_user(session)

    with pytest.raises(ValidationError):
        service.review_validation_diagnosis(diagnosis.id, DiagnosisReview(review_status="confirmed"), user)
