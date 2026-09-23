from __future__ import annotations

from app.models import ExamDraft, Review
from tests.unit.services.conftest import make_diagnosis, make_exam, make_patient, make_user


def test_build_basic_fields_and_patient(session, exam_payload_service):
    patient = make_patient(session, name="Joana")
    exam = make_exam(session, patient=patient)

    payload = exam_payload_service.build(exam)

    assert payload["id"] == exam.id
    assert payload["exam_code"] == exam.exam_code
    assert payload["patient"]["id"] == patient.id
    assert payload["image_endpoint"] == f"/exams/{exam.id}/image"
    assert "diagnoses" not in payload


def test_build_review_result_hidden_unless_valido(session, exam_payload_service):
    exam = make_exam(session, status_validation="em_validacao", review_result="alterado")

    payload = exam_payload_service.build(exam)

    assert payload["review_result"] is None

    exam.status_validation = "valido"
    payload = exam_payload_service.build(exam)
    assert payload["review_result"] == "alterado"


def test_build_started_at_for_em_validacao(session, exam_payload_service):
    exam = make_exam(session, status_validation="em_validacao")
    session.add(
        Review(
            exam_id=exam.id,
            doctor_name="Dr",
            status_before="nao_validado",
            status_after="em_validacao",
        )
    )
    session.commit()

    payload = exam_payload_service.build(exam)

    assert payload["started_at"] is not None
    assert payload["completed_at"] is None


def test_build_completed_at_for_valido(session, exam_payload_service):
    exam = make_exam(session, status_validation="valido", review_result="sem_alteracao")
    session.add(
        Review(
            exam_id=exam.id,
            doctor_name="Dr",
            status_before="em_validacao",
            status_after="valido",
        )
    )
    session.commit()

    payload = exam_payload_service.build(exam)

    assert payload["completed_at"] is not None
    assert payload["started_at"] is None


def test_build_includes_draft_notes_for_current_user(session, exam_payload_service):
    exam = make_exam(session)
    user = make_user(session)
    session.add(ExamDraft(exam_id=exam.id, reviewer_id=user.id, notes="rascunho"))
    session.commit()

    payload = exam_payload_service.build(exam, current_user=user)

    assert payload["draft_notes"] == "rascunho"


def test_build_include_details_adds_diagnoses(session, exam_payload_service):
    exam = make_exam(session)
    make_diagnosis(session, exam, name="Ritmo sinusal")

    payload = exam_payload_service.build(exam, include_details=True)

    assert len(payload["diagnoses"]) == 1
    assert payload["diagnoses"][0]["name"] == "Ritmo sinusal"
