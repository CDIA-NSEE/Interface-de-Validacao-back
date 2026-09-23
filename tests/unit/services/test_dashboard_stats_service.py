from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models import Review
from app.services.dashboard_stats_service import DashboardStatsService
from tests.unit.services.conftest import make_exam


@pytest.fixture()
def service(exam_repository, review_repository, validation_context_service, validation_queue_service):
    return DashboardStatsService(
        exam_repository, review_repository, validation_context_service, validation_queue_service
    )


def test_stats_counts_by_status_and_review_result(session, service):
    make_exam(session, status_validation="nao_validado")
    make_exam(session, status_validation="em_validacao")
    make_exam(session, status_validation="valido", review_result="sem_alteracao")
    make_exam(session, status_validation="valido", review_result="alterado")

    stats = service.stats()

    assert stats["pending_total"] == 1
    assert stats["in_validation_total"] == 1
    assert stats["reviewed_total"] == 2
    assert stats["valid_without_change"] == 1
    assert stats["valid_with_change"] == 1


def test_stats_reviewed_today_and_week(session, service):
    exam = make_exam(session, status_validation="valido")
    now = datetime.now(UTC)
    session.add(
        Review(
            exam_id=exam.id,
            doctor_name="Dr",
            status_before="em_validacao",
            status_after="valido",
            created_at=now,
        )
    )
    session.add(
        Review(
            exam_id=exam.id,
            doctor_name="Dr",
            status_before="em_validacao",
            status_after="valido",
            created_at=now - timedelta(days=3),
        )
    )
    session.add(
        Review(
            exam_id=exam.id,
            doctor_name="Dr",
            status_before="em_validacao",
            status_after="valido",
            created_at=now - timedelta(days=10),
        )
    )
    session.commit()

    stats = service.stats()

    assert stats["reviewed_today"] == 1
    assert stats["reviewed_week"] == 2


def test_stats_includes_queue_and_cross_filter_counts(session, service):
    make_exam(session)

    stats = service.stats()

    assert "queue_state_counts" in stats
    assert "decision_counts" in stats
    assert "region_counts" in stats
