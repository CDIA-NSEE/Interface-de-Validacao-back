from __future__ import annotations

from app.models import DiagnosisValidation
from app.services.validation_context_service import ValidationContext
from tests.unit.services.conftest import make_diagnosis, make_exam


def _context(**overrides):
    defaults = dict(
        cycle_key="c1",
        cycle_label="Ciclo 1",
        day_index=1,
        general_review_day=30,
        is_general_review_day=False,
        active_standard_diagnosis="Infarto",
        is_configured=True,
    )
    defaults.update(overrides)
    return ValidationContext(**defaults)


def test_required_diagnoses_for_context_filters_by_active_diagnosis(session, validation_queue_service):
    exam = make_exam(session)
    make_diagnosis(session, exam, name="Infarto", source="original")
    make_diagnosis(session, exam, name="Ritmo sinusal", source="original")

    required = validation_queue_service.required_diagnoses_for_context(exam, _context())

    assert len(required) == 1
    assert required[0].name == "Infarto"


def test_required_diagnoses_for_context_empty_when_no_active_diagnosis(session, validation_queue_service):
    exam = make_exam(session)
    make_diagnosis(session, exam, name="Infarto", source="original")

    required = validation_queue_service.required_diagnoses_for_context(
        exam, _context(active_standard_diagnosis=None)
    )

    assert required == []


def test_exam_pending_for_context_false_when_not_configured(session, validation_queue_service):
    exam = make_exam(session)
    assert validation_queue_service.exam_pending_for_context(exam, _context(is_configured=False)) is False


def test_exam_pending_for_context_general_review_day(session, validation_queue_service):
    exam = make_exam(session, status_validation="nao_validado")
    context = _context(is_general_review_day=True)
    assert validation_queue_service.exam_pending_for_context(exam, context) is True

    exam.status_validation = "valido"
    assert validation_queue_service.exam_pending_for_context(exam, context) is False


def test_exam_pending_for_context_pending_when_no_validation_exists(session, validation_queue_service):
    exam = make_exam(session)
    make_diagnosis(session, exam, name="Infarto", source="original")

    assert validation_queue_service.exam_pending_for_context(exam, _context()) is True


def test_exam_pending_for_context_not_pending_once_validated(session, validation_queue_service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Infarto", source="original")
    session.add(
        DiagnosisValidation(
            exam_id=exam.id,
            diagnosis_id=diagnosis.id,
            standard_text="Infarto",
            cycle_key="c1",
            review_status="confirmed",
            reviewer_name="Dr",
        )
    )
    session.commit()

    assert validation_queue_service.exam_pending_for_context(exam, _context()) is False


def test_queue_orders_em_validacao_before_nao_validado(session, validation_queue_service):
    exam_a = make_exam(session, status_validation="nao_validado")
    exam_b = make_exam(session, status_validation="em_validacao")
    make_diagnosis(session, exam_a, name="Infarto", source="original")
    make_diagnosis(session, exam_b, name="Infarto", source="original")

    queue = validation_queue_service.queue(_context())

    assert [exam.id for exam in queue] == [exam_b.id, exam_a.id]


def test_queue_empty_when_not_configured(session, validation_queue_service):
    assert validation_queue_service.queue(_context(is_configured=False)) == []


def test_progress_general_review_day(session, validation_queue_service):
    make_exam(session, status_validation="nao_validado")
    make_exam(session, status_validation="valido")
    context = _context(is_general_review_day=True)
    queue = validation_queue_service.queue(context)

    progress = validation_queue_service.progress(context, queue)

    assert progress["total"] == 2
    assert progress["remaining"] == 1
    assert progress["completed"] == 1
    assert progress["percent"] == 50


def test_progress_zero_when_not_configured(session, validation_queue_service):
    assert validation_queue_service.progress(_context(is_configured=False), []) == {
        "total": 0,
        "remaining": 0,
        "completed": 0,
        "percent": 0,
    }


def test_exam_matches_queue_state_start_validated_completed(session, validation_queue_service):
    exam = make_exam(session, status_validation="nao_validado")
    diagnosis = make_diagnosis(session, exam, name="Infarto", source="original")
    context = _context()

    assert validation_queue_service.exam_matches_queue_state(exam, context, "start") is True
    assert validation_queue_service.exam_matches_queue_state(exam, context, "validated") is False
    assert validation_queue_service.exam_matches_queue_state(exam, context, "completed") is False
    assert validation_queue_service.exam_matches_queue_state(exam, context, None) is True

    session.add(
        DiagnosisValidation(
            exam_id=exam.id,
            diagnosis_id=diagnosis.id,
            standard_text="Infarto",
            cycle_key="c1",
            review_status="confirmed",
            reviewer_name="Dr",
        )
    )
    session.commit()

    assert validation_queue_service.exam_matches_queue_state(exam, context, "validated") is True

    exam.status_validation = "valido"
    assert validation_queue_service.exam_matches_queue_state(exam, context, "completed") is True
    assert validation_queue_service.exam_matches_queue_state(exam, context, "validated") is False


def test_exam_queue_state_transitions(session, validation_queue_service):
    exam = make_exam(session, status_validation="nao_validado")
    make_diagnosis(session, exam, name="Infarto", source="original")
    context = _context()

    assert validation_queue_service.exam_queue_state(exam, context) == "start"

    exam.status_validation = "valido"
    assert validation_queue_service.exam_queue_state(exam, context) == "completed"


def test_exam_matches_decision_region_filters_by_status_and_region(session, validation_queue_service):
    exam = make_exam(session)
    diagnosis = make_diagnosis(session, exam, name="Infarto", source="original")
    context = _context()

    assert validation_queue_service.exam_matches_decision_region(exam, context, None, None) is True
    assert validation_queue_service.exam_matches_decision_region(exam, context, "confirmed", None) is False
    assert (
        validation_queue_service.exam_matches_decision_region(exam, context, None, "without_region") is True
    )

    session.add(
        DiagnosisValidation(
            exam_id=exam.id,
            diagnosis_id=diagnosis.id,
            standard_text="Infarto",
            cycle_key="c1",
            review_status="confirmed",
            reviewer_name="Dr",
        )
    )
    session.commit()

    assert validation_queue_service.exam_matches_decision_region(exam, context, "confirmed", None) is True


def test_queue_state_counts_and_cross_filter_counts(session, validation_queue_service):
    exam_pending = make_exam(session, status_validation="nao_validado")
    exam_done = make_exam(session, status_validation="valido")
    make_diagnosis(session, exam_pending, name="Infarto", source="original")
    context = _context()

    counts = validation_queue_service.queue_state_counts([exam_pending, exam_done], context)
    assert counts["all"] == 2
    assert counts["start"] == 1
    assert counts["completed"] == 1

    cross = validation_queue_service.cross_filter_counts([exam_pending, exam_done], context)
    assert cross["decision"]["confirmed"] == 0
    assert cross["region"]["without_region"] == 1
