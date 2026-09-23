from __future__ import annotations

from typing import Any

from app.repositories.interfaces.exam_repository import ExamRepository
from app.services.exam_filters import ExamListFilters
from app.services.exam_payload_service import ExamPayloadService
from app.services.validation_context_service import ValidationContextService
from app.services.validation_queue_service import ValidationQueueService


class ExamQueryService:
    def __init__(
        self,
        exam_repository: ExamRepository,
        exam_payload_service: ExamPayloadService,
        validation_context_service: ValidationContextService,
        validation_queue_service: ValidationQueueService,
    ) -> None:
        self._exam_repository = exam_repository
        self._exam_payload_service = exam_payload_service
        self._validation_context_service = validation_context_service
        self._validation_queue_service = validation_queue_service

    def list_exams(self, filters: ExamListFilters) -> list[dict[str, Any]]:
        filters.validate()

        context = self._validation_context_service.active_context()
        exams = self._exam_repository.list_recent()
        normalized_search = filters.search.strip().lower() if filters.search else None
        results = []

        for exam in exams:
            if filters.status and exam.status_validation != filters.status:
                continue
            if filters.category and exam.category != filters.category:
                continue
            if filters.exam_type and exam.exam_type != filters.exam_type:
                continue
            if filters.review_result and exam.review_result != filters.review_result:
                continue
            if filters.source == "pending" and exam.status_validation == "valido":
                continue
            if filters.source == "reviewed" and exam.status_validation != "valido":
                continue
            if not self._validation_queue_service.exam_matches_queue_state(
                exam, context, filters.queue_state
            ):
                continue
            if not self._validation_queue_service.exam_matches_decision_region(
                exam, context, filters.decision, filters.region
            ):
                continue
            if normalized_search:
                haystack = f"{exam.id} {exam.exam_code}".lower()
                if normalized_search not in haystack:
                    continue

            results.append(self._exam_payload_service.build(exam, context=context))

        return results
