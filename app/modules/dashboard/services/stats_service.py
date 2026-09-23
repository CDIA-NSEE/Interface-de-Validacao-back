from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.repositories.interfaces.exam_repository import ExamRepository
from app.repositories.interfaces.review_repository import ReviewRepository
from app.services.validation_context_service import ValidationContextService
from app.services.validation_queue_service import ValidationQueueService


class DashboardStatsService:
    def __init__(
        self,
        exam_repository: ExamRepository,
        review_repository: ReviewRepository,
        validation_context_service: ValidationContextService,
        validation_queue_service: ValidationQueueService,
    ) -> None:
        self._exam_repository = exam_repository
        self._review_repository = review_repository
        self._validation_context_service = validation_context_service
        self._validation_queue_service = validation_queue_service

    def stats(self) -> dict[str, Any]:
        exams = self._exam_repository.list_all()
        reviews = self._review_repository.list_completed()
        context = self._validation_context_service.active_context()
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        queue_state_counts = self._validation_queue_service.queue_state_counts(exams, context)
        cross_filter_counts = self._validation_queue_service.cross_filter_counts(exams, context)

        return {
            "reviewed_today": sum(1 for review in reviews if review.created_at >= today_start),
            "reviewed_week": sum(1 for review in reviews if review.created_at >= week_start),
            "pending_total": sum(1 for exam in exams if exam.status_validation == "nao_validado"),
            "in_validation_total": sum(1 for exam in exams if exam.status_validation == "em_validacao"),
            "reviewed_total": sum(1 for exam in exams if exam.status_validation == "valido"),
            "valid_without_change": sum(
                1
                for exam in exams
                if exam.status_validation == "valido" and exam.review_result == "sem_alteracao"
            ),
            "valid_with_change": sum(
                1 for exam in exams if exam.status_validation == "valido" and exam.review_result == "alterado"
            ),
            "queue_state_counts": queue_state_counts,
            "decision_counts": cross_filter_counts["decision"],
            "region_counts": cross_filter_counts["region"],
        }
