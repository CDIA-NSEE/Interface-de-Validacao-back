from __future__ import annotations

from app.models import Diagnosis, Exam
from app.repositories.interfaces.diagnosis_repository import DiagnosisRepository
from app.repositories.interfaces.exam_repository import ExamRepository
from app.services.diagnosis_payload_service import DiagnosisPayloadService
from app.services.diagnosis_standardizer import DiagnosisStandardizer
from app.services.validation_context_service import ValidationContext


class ValidationQueueService:
    def __init__(
        self,
        exam_repository: ExamRepository,
        diagnosis_repository: DiagnosisRepository,
        diagnosis_standardizer: DiagnosisStandardizer,
        diagnosis_payload_service: DiagnosisPayloadService,
    ) -> None:
        self._exam_repository = exam_repository
        self._diagnosis_repository = diagnosis_repository
        self._diagnosis_standardizer = diagnosis_standardizer
        self._diagnosis_payload_service = diagnosis_payload_service

    def original_diagnoses(self, exam_id: int) -> list[Diagnosis]:
        return self._diagnosis_repository.list_original_for_exam(exam_id)

    def required_diagnoses_for_context(self, exam: Exam, context: ValidationContext) -> list[Diagnosis]:
        active_standard_diagnosis = context.active_standard_diagnosis
        if not active_standard_diagnosis:
            return []

        return [
            diagnosis
            for diagnosis in self.original_diagnoses(exam.id)
            if self._diagnosis_standardizer.same_standard_text(
                self._diagnosis_standardizer.standardize(diagnosis.name), active_standard_diagnosis
            )
        ]

    def exam_pending_for_context(self, exam: Exam, context: ValidationContext) -> bool:
        if not context.is_configured:
            return False

        if context.is_general_review_day:
            return exam.status_validation != "valido"

        required_diagnoses = self.required_diagnoses_for_context(exam, context)
        if not required_diagnoses:
            return False

        active_standard_diagnosis = self._diagnosis_standardizer.standardize(required_diagnoses[0].name)
        validation = self._diagnosis_payload_service.latest_standard_validation(
            exam.id, active_standard_diagnosis, context.cycle_key
        )
        return validation is None

    def queue(self, context: ValidationContext) -> list[Exam]:
        if not context.is_configured:
            return []

        exams = self._exam_repository.list_recent()
        pending_exams = [exam for exam in exams if self.exam_pending_for_context(exam, context)]
        return sorted(
            pending_exams,
            key=lambda exam: (
                {"em_validacao": 0, "nao_validado": 1}.get(exam.status_validation, 2),
                exam.created_at,
            ),
        )

    def progress(self, context: ValidationContext, queue: list[Exam]) -> dict:
        if not context.is_configured:
            return {"total": 0, "remaining": 0, "completed": 0, "percent": 0}

        if context.is_general_review_day:
            total = len(self._exam_repository.list_all())
            remaining = len(queue)
        else:
            active_standard_diagnosis = context.active_standard_diagnosis
            if not active_standard_diagnosis:
                total = 0
                remaining = 0
            else:
                total = 0
                remaining = 0
                for exam in self._exam_repository.list_all():
                    required_diagnoses = self.required_diagnoses_for_context(exam, context)
                    if not required_diagnoses:
                        continue

                    total += 1
                    standard_text = self._diagnosis_standardizer.standardize(required_diagnoses[0].name)
                    validation = self._diagnosis_payload_service.latest_standard_validation(
                        exam.id, standard_text, context.cycle_key
                    )
                    if validation is None:
                        remaining += 1

        completed = max(total - remaining, 0)
        percent = round((completed / total) * 100) if total else 0
        return {"total": total, "remaining": remaining, "completed": completed, "percent": percent}

    def diagnoses_for_queue_filters(self, exam: Exam, context: ValidationContext) -> list[Diagnosis]:
        if context.is_configured and context.active_standard_diagnosis:
            return self.required_diagnoses_for_context(exam, context)
        return self.original_diagnoses(exam.id)

    def exam_has_context_validation(self, exam: Exam, context: ValidationContext) -> bool:
        required_diagnoses = self.required_diagnoses_for_context(exam, context)
        if not required_diagnoses:
            return False

        standard_text = self._diagnosis_standardizer.standardize(required_diagnoses[0].name)
        validation = self._diagnosis_payload_service.latest_standard_validation(
            exam.id, standard_text, context.cycle_key
        )
        return validation is not None

    def exam_matches_queue_state(
        self, exam: Exam, context: ValidationContext, queue_state: str | None
    ) -> bool:
        if not queue_state or queue_state == "all":
            return True

        if queue_state == "completed":
            return exam.status_validation == "valido"

        if queue_state == "start":
            return self.exam_pending_for_context(exam, context)

        if queue_state == "validated":
            return exam.status_validation != "valido" and self.exam_has_context_validation(exam, context)

        return True

    def exam_queue_state(self, exam: Exam, context: ValidationContext) -> str:
        if exam.status_validation == "valido":
            return "completed"

        if self.exam_has_context_validation(exam, context):
            return "validated"

        return "start"

    def exam_matches_decision_region(
        self,
        exam: Exam,
        context: ValidationContext,
        decision: str | None,
        region: str | None,
    ) -> bool:
        if not decision and not region:
            return True

        diagnoses = self.diagnoses_for_queue_filters(exam, context)
        for diagnosis in diagnoses:
            diagnosis_status = self._diagnosis_payload_service.effective_review_status(diagnosis, context)
            regions_count = len(self._diagnosis_payload_service.diagnosis_region_payloads(diagnosis))

            if decision and diagnosis_status != decision:
                continue
            if region == "with_region" and regions_count == 0:
                continue
            if region == "without_region" and regions_count > 0:
                continue

            return True

        return False

    def queue_state_counts(self, exams: list[Exam], context: ValidationContext) -> dict:
        return {
            "all": len(exams),
            "start": sum(1 for exam in exams if self.exam_matches_queue_state(exam, context, "start")),
            "validated": sum(
                1 for exam in exams if self.exam_matches_queue_state(exam, context, "validated")
            ),
            "completed": sum(
                1 for exam in exams if self.exam_matches_queue_state(exam, context, "completed")
            ),
        }

    def cross_filter_counts(self, exams: list[Exam], context: ValidationContext) -> dict:
        return {
            "decision": {
                "confirmed": sum(
                    1 for exam in exams if self.exam_matches_decision_region(exam, context, "confirmed", None)
                ),
                "rejected": sum(
                    1 for exam in exams if self.exam_matches_decision_region(exam, context, "rejected", None)
                ),
            },
            "region": {
                "with_region": sum(
                    1
                    for exam in exams
                    if self.exam_matches_decision_region(exam, context, None, "with_region")
                ),
                "without_region": sum(
                    1
                    for exam in exams
                    if self.exam_matches_decision_region(exam, context, None, "without_region")
                ),
            },
        }
