from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError, ValidationError
from app.models import ExamDraft
from app.schemas import ExamValidate, StatusUpdate
from app.services.exam_status_service import ExamStatusService
from tests.unit.services.conftest import make_exam, make_user


@pytest.fixture()
def service(exam_repository, review_repository, exam_draft_repository, exam_payload_service):
    return ExamStatusService(exam_repository, review_repository, exam_draft_repository, exam_payload_service)


def test_update_status_rejects_valido(session, service):
    exam = make_exam(session)
    user = make_user(session)
    with pytest.raises(ValidationError):
        service.update_status(exam.id, StatusUpdate(status_validation="valido"), user)


def test_update_status_not_found(session, service):
    user = make_user(session)
    with pytest.raises(NotFoundError):
        service.update_status(999, StatusUpdate(status_validation="em_validacao"), user)


def test_update_status_records_review_on_transition(session, service, review_repository):
    exam = make_exam(session, status_validation="nao_validado")
    user = make_user(session)

    service.update_status(exam.id, StatusUpdate(status_validation="em_validacao"), user)

    assert exam.status_validation == "em_validacao"
    assert exam.review_result is None
    reviews = review_repository.list_for_exam(exam.id)
    assert len(reviews) == 1
    assert reviews[0].status_after == "em_validacao"


def test_update_status_no_review_when_status_unchanged(session, service, review_repository):
    exam = make_exam(session, status_validation="em_validacao")
    user = make_user(session)

    service.update_status(exam.id, StatusUpdate(status_validation="em_validacao"), user)

    assert review_repository.list_for_exam(exam.id) == []


def test_validate_sets_valido_and_creates_review(session, service, review_repository):
    exam = make_exam(session, status_validation="em_validacao")
    user = make_user(session)

    payload = service.validate(exam.id, ExamValidate(review_result="sem_alteracao"), user)

    assert exam.status_validation == "valido"
    assert exam.review_result == "sem_alteracao"
    assert payload["review_result"] == "sem_alteracao"
    reviews = review_repository.list_for_exam(exam.id)
    assert reviews[-1].status_after == "valido"


def test_validate_uses_draft_notes_as_fallback_and_deletes_draft(
    session, service, review_repository, exam_draft_repository
):
    exam = make_exam(session, status_validation="em_validacao")
    user = make_user(session)
    session.add(ExamDraft(exam_id=exam.id, reviewer_id=user.id, notes="rascunho"))
    session.commit()

    service.validate(exam.id, ExamValidate(review_result="alterado"), user)

    reviews = review_repository.list_for_exam(exam.id)
    assert reviews[-1].notes == "rascunho"
    assert exam_draft_repository.get_for_exam_and_reviewer(exam.id, user.id) is None


def test_validate_not_found(session, service):
    user = make_user(session)
    with pytest.raises(NotFoundError):
        service.validate(999, ExamValidate(review_result="sem_alteracao"), user)
