from __future__ import annotations

import pytest

from app.core.exceptions import NotFoundError
from app.schemas import ExamDraftUpdate
from app.services.exam_draft_service import ExamDraftService
from tests.unit.services.conftest import make_exam, make_user


@pytest.fixture()
def service(exam_repository, exam_draft_repository, exam_payload_service):
    return ExamDraftService(exam_repository, exam_draft_repository, exam_payload_service)


def test_save_creates_draft_when_notes_present(session, service, exam_draft_repository):
    exam = make_exam(session)
    user = make_user(session)

    service.save(exam.id, ExamDraftUpdate(notes="rascunho"), user)

    draft = exam_draft_repository.get_for_exam_and_reviewer(exam.id, user.id)
    assert draft.notes == "rascunho"


def test_save_updates_existing_draft(session, service, exam_draft_repository):
    exam = make_exam(session)
    user = make_user(session)
    service.save(exam.id, ExamDraftUpdate(notes="v1"), user)

    service.save(exam.id, ExamDraftUpdate(notes="v2"), user)

    draft = exam_draft_repository.get_for_exam_and_reviewer(exam.id, user.id)
    assert draft.notes == "v2"


def test_save_deletes_draft_when_notes_blank(session, service, exam_draft_repository):
    exam = make_exam(session)
    user = make_user(session)
    service.save(exam.id, ExamDraftUpdate(notes="v1"), user)

    service.save(exam.id, ExamDraftUpdate(notes="   "), user)

    assert exam_draft_repository.get_for_exam_and_reviewer(exam.id, user.id) is None


def test_save_not_found(session, service):
    user = make_user(session)
    with pytest.raises(NotFoundError):
        service.save(999, ExamDraftUpdate(notes="x"), user)
