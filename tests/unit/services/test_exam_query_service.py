from __future__ import annotations

import pytest

from app.services.exam_filters import ExamListFilters
from app.services.exam_query_service import ExamQueryService
from tests.unit.services.conftest import make_exam


@pytest.fixture()
def service(exam_repository, exam_payload_service, validation_context_service, validation_queue_service):
    return ExamQueryService(
        exam_repository, exam_payload_service, validation_context_service, validation_queue_service
    )


def test_list_exams_filters_by_status(session, service):
    make_exam(session, status_validation="nao_validado")
    make_exam(session, status_validation="valido")

    results = service.list_exams(ExamListFilters(status="valido"))

    assert len(results) == 1
    assert results[0]["status_validation"] == "valido"


def test_list_exams_filters_by_source_pending_and_reviewed(session, service):
    make_exam(session, status_validation="nao_validado")
    make_exam(session, status_validation="valido")

    pending = service.list_exams(ExamListFilters(source="pending"))
    reviewed = service.list_exams(ExamListFilters(source="reviewed"))

    assert len(pending) == 1
    assert pending[0]["status_validation"] == "nao_validado"
    assert len(reviewed) == 1
    assert reviewed[0]["status_validation"] == "valido"


def test_list_exams_filters_by_search(session, service):
    exam = make_exam(session, exam_code="ECG-SEARCHME")
    make_exam(session, exam_code="ECG-OTHER")

    results = service.list_exams(ExamListFilters(search="searchme"))

    assert len(results) == 1
    assert results[0]["id"] == exam.id


def test_list_exams_filters_by_category_and_exam_type(session, service):
    make_exam(session, category="rotina", exam_type="repouso")
    make_exam(session, category="urgencia", exam_type="esforco")

    results = service.list_exams(ExamListFilters(category="urgencia"))

    assert len(results) == 1
    assert results[0]["category"] == "urgencia"


def test_list_exams_no_filters_returns_all(session, service):
    make_exam(session)
    make_exam(session)

    assert len(service.list_exams(ExamListFilters())) == 2
