from datetime import date, datetime, timedelta, timezone
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

import app.main as main_module
from app.auth import get_current_active_user
from app.database import get_session
from app.models import (
    Diagnosis,
    DiagnosisRegion,
    DiagnosisValidation,
    Exam,
    ExamDraft,
    Patient,
    Review,
    User,
)


class ApiEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)
        self._seed_database()

        self.context = {
            "cycle_key": "cycle-2026",
            "cycle_label": "Ciclo 2026",
            "day_index": 1,
            "general_review_day": 30,
            "is_general_review_day": False,
            "active_standard_diagnosis": "Ritmo sinusal",
            "is_configured": True,
        }
        self.context_patcher = patch.object(
            main_module,
            "active_validation_context",
            return_value=self.context,
        )
        self.active_context = self.context_patcher.start()
        self.support_patcher = patch.object(
            main_module,
            "load_support_contact",
            return_value={"title": "Suporte", "description": "Ajuda", "channels": []},
        )
        self.support_patcher.start()
        self.options_patcher = patch.object(
            main_module,
            "load_diagnosis_options",
            return_value=["Ritmo sinusal", "Taquicardia sinusal", "Infarto agudo"],
        )
        self.options_patcher.start()

        def override_session():
            with Session(self.engine) as session:
                yield session

        self.previous_dependency_overrides = dict(main_module.app.dependency_overrides)
        main_module.app.dependency_overrides[get_session] = override_session
        main_module.app.dependency_overrides[get_current_active_user] = lambda: self.current_user
        self.previous_db_initialized = main_module._db_initialized
        main_module._db_initialized = True
        self.client = TestClient(main_module.app)

    def tearDown(self):
        self.client.close()
        main_module.app.dependency_overrides.clear()
        main_module.app.dependency_overrides.update(self.previous_dependency_overrides)
        main_module._db_initialized = self.previous_db_initialized
        self.options_patcher.stop()
        self.support_patcher.stop()
        self.context_patcher.stop()
        self.engine.dispose()

    def _session(self):
        return Session(self.engine)

    def _seed_database(self):
        with Session(self.engine) as session:
            user = User(
                username="cognito-doctor",
                full_name="Dra. Ana",
                role="doctor",
                is_active=True,
            )
            patient = Patient(
                name="Paciente Teste",
                birth_date="1980-01-01",
                age=46,
                sex="Feminino",
                weight=70,
                height=1.65,
                bmi=25.7,
            )
            session.add(user)
            session.add(patient)
            session.commit()
            session.refresh(user)
            session.refresh(patient)

            exams = [
                Exam(
                    exam_code="START001",
                    patient_id=patient.id,
                    exam_date=date(2026, 7, 21),
                    exam_time="10:00",
                    category="ECG",
                    exam_type="ECG repouso",
                    status_validation="nao_validado",
                    image_url="/fallback-start.svg",
                    metadata_id=101,
                    created_at=datetime(2026, 7, 21, 10, 0),
                    updated_at=datetime(2026, 7, 21, 10, 0),
                ),
                Exam(
                    exam_code="VALID001",
                    patient_id=patient.id,
                    exam_date=date(2026, 7, 20),
                    category="ECG",
                    exam_type="ECG repouso",
                    status_validation="em_validacao",
                    created_at=datetime(2026, 7, 20, 10, 0),
                    updated_at=datetime(2026, 7, 20, 10, 0),
                ),
                Exam(
                    exam_code="DONE001",
                    patient_id=patient.id,
                    exam_date=date(2026, 7, 19),
                    category="ECG",
                    exam_type="ECG repouso",
                    status_validation="valido",
                    review_result="alterado",
                    created_at=datetime(2026, 7, 19, 10, 0),
                    updated_at=datetime(2026, 7, 19, 10, 0),
                ),
                Exam(
                    exam_code="OTHER001",
                    patient_id=patient.id,
                    exam_date=date(2026, 7, 18),
                    category="ECG",
                    exam_type="ECG esforco",
                    status_validation="nao_validado",
                    created_at=datetime(2026, 7, 18, 10, 0),
                    updated_at=datetime(2026, 7, 18, 10, 0),
                ),
            ]
            session.add_all(exams)
            session.commit()
            for exam in exams:
                session.refresh(exam)

            diagnoses = [
                Diagnosis(
                    exam_id=exams[0].id,
                    name="Ritmo sinusal",
                    source="original",
                    review_status="pending",
                    created_at=datetime(2026, 7, 21, 10, 0),
                ),
                Diagnosis(
                    exam_id=exams[1].id,
                    name="Ritmo sinusal",
                    source="original",
                    review_status="confirmed",
                    created_at=datetime(2026, 7, 20, 10, 0),
                ),
                Diagnosis(
                    exam_id=exams[2].id,
                    name="Infarto agudo",
                    source="original",
                    review_status="confirmed",
                    is_abnormal=True,
                    created_at=datetime(2026, 7, 19, 10, 0),
                ),
                Diagnosis(
                    exam_id=exams[3].id,
                    name="Infarto agudo",
                    source="original",
                    review_status="pending",
                    is_abnormal=True,
                    created_at=datetime(2026, 7, 18, 10, 0),
                ),
                Diagnosis(
                    exam_id=exams[0].id,
                    name="Taquicardia sinusal",
                    source="doctor_added",
                    review_status="confirmed",
                    is_abnormal=True,
                    created_at=datetime(2026, 7, 21, 10, 1),
                ),
            ]
            session.add_all(diagnoses)
            session.commit()
            for diagnosis in diagnoses:
                session.refresh(diagnosis)

            session.add(
                DiagnosisValidation(
                    exam_id=exams[1].id,
                    diagnosis_id=diagnoses[1].id,
                    standard_text="Ritmo sinusal",
                    cycle_key="cycle-2026",
                    day_index=1,
                    review_status="confirmed",
                    reviewer_id=user.id,
                    reviewer_name=user.full_name,
                    created_at=datetime(2026, 7, 20, 10, 5),
                    updated_at=datetime(2026, 7, 20, 10, 5),
                )
            )
            session.add(
                DiagnosisRegion(
                    exam_id=exams[1].id,
                    diagnosis_id=diagnoses[1].id,
                    x=10,
                    y=10,
                    width=20,
                    height=20,
                    created_by_id=user.id,
                    created_by_name=user.full_name,
                )
            )
            session.add(
                DiagnosisRegion(
                    exam_id=exams[2].id,
                    diagnosis_id=diagnoses[2].id,
                    x=20,
                    y=20,
                    width=20,
                    height=20,
                    created_by_id=user.id,
                    created_by_name=user.full_name,
                )
            )
            session.add(
                Review(
                    exam_id=exams[1].id,
                    doctor_name=user.full_name,
                    status_before="nao_validado",
                    status_after="em_validacao",
                    created_at=datetime(2026, 7, 20, 10, 5),
                )
            )
            session.add(
                Review(
                    exam_id=exams[2].id,
                    doctor_name=user.full_name,
                    status_before="em_validacao",
                    status_after="valido",
                    review_result="alterado",
                    created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),
                )
            )
            session.commit()

            self.current_user = User(
                id=user.id,
                username=user.username,
                full_name=user.full_name,
                role=user.role,
                is_active=True,
            )
            self.start_exam_id = exams[0].id
            self.validated_exam_id = exams[1].id
            self.completed_exam_id = exams[2].id
            self.other_exam_id = exams[3].id
            self.start_diagnosis_id = diagnoses[0].id
            self.validated_diagnosis_id = diagnoses[1].id
            self.completed_diagnosis_id = diagnoses[2].id
            self.infarct_diagnosis_id = diagnoses[3].id
            self.doctor_diagnosis_id = diagnoses[4].id

    def test_identity_context_support_and_diagnosis_options(self):
        me = self.client.get("/auth/me")
        context = self.client.get("/validation/context")
        support = self.client.get("/support/contact")
        options = self.client.get("/diagnosis-options")

        self.assertEqual(me.status_code, 200)
        self.assertIsNone(me.json()["email"])
        self.assertEqual(me.json()["full_name"], "Dra. Ana")
        self.assertEqual(context.json()["cycle_key"], "cycle-2026")
        self.assertEqual(context.json()["support_contact"]["title"], "Suporte")
        self.assertEqual(support.json()["title"], "Suporte")
        self.assertIn("Infarto agudo", options.json())

    def test_validation_queue_next_and_progress(self):
        queue = self.client.get("/validation/queue")
        next_exam = self.client.get("/validation/next")

        self.assertEqual(queue.status_code, 200)
        self.assertEqual(queue.json()["total"], 1)
        self.assertEqual(queue.json()["items"][0]["exam_code"], "START001")
        self.assertEqual(
            queue.json()["progress"],
            {"total": 2, "remaining": 1, "completed": 1, "percent": 50},
        )
        self.assertEqual(next_exam.json()["exam"]["id"], self.start_exam_id)
        self.assertTrue(next_exam.json()["exam"]["diagnoses"][0]["daily_required"])

    def test_validation_queue_supports_general_and_unconfigured_contexts(self):
        general_context = {
            **self.context,
            "day_index": 30,
            "is_general_review_day": True,
            "active_standard_diagnosis": None,
        }
        self.active_context.return_value = general_context
        general_queue = self.client.get("/validation/queue")
        self.assertEqual(general_queue.json()["total"], 3)
        self.assertEqual(general_queue.json()["progress"]["total"], 4)

        self.active_context.return_value = {
            **self.context,
            "day_index": None,
            "active_standard_diagnosis": None,
            "is_configured": False,
        }
        empty_queue = self.client.get("/validation/queue")
        empty_next = self.client.get("/validation/next")
        self.assertEqual(empty_queue.json()["items"], [])
        self.assertEqual(empty_queue.json()["progress"]["percent"], 0)
        self.assertIsNone(empty_next.json()["exam"])

    def test_daily_review_creates_then_updates_validation(self):
        rejected = self.client.post(
            f"/validation/diagnoses/{self.start_diagnosis_id}/review",
            json={"review_status": "rejected", "notes": "Discordancia clinica"},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status_validation"], "em_validacao")

        confirmed = self.client.post(
            f"/validation/diagnoses/{self.start_diagnosis_id}/review",
            json={"review_status": "confirmed", "notes": None},
        )
        self.assertEqual(confirmed.status_code, 200)
        diagnosis = next(
            item for item in confirmed.json()["diagnoses"] if item["id"] == self.start_diagnosis_id
        )
        self.assertEqual(diagnosis["review_status"], "confirmed")

        with self._session() as session:
            validations = session.exec(
                select(DiagnosisValidation).where(
                    DiagnosisValidation.diagnosis_id == self.start_diagnosis_id
                )
            ).all()
            reviews = session.exec(
                select(Review).where(Review.exam_id == self.start_exam_id)
            ).all()
        self.assertEqual(len(validations), 1)
        self.assertEqual(validations[0].review_status, "confirmed")
        self.assertEqual(len(reviews), 1)

    def test_list_exams_applies_operational_filters(self):
        cases = {
            "": {"START001", "VALID001", "DONE001", "OTHER001"},
            "?status=valido": {"DONE001"},
            "?category=ECG&exam_type=ECG%20esforco": {"OTHER001"},
            "?review_result=alterado": {"DONE001"},
            "?source=pending": {"START001", "VALID001", "OTHER001"},
            "?source=reviewed": {"DONE001"},
            "?queue_state=start": {"START001"},
            "?queue_state=validated": {"VALID001"},
            "?queue_state=completed": {"DONE001"},
            "?decision=confirmed": {"VALID001"},
            "?region=with_region": {"VALID001"},
            "?region=without_region": {"START001"},
            "?search=VALID001": {"VALID001"},
        }

        for query, expected_codes in cases.items():
            with self.subTest(query=query):
                response = self.client.get(f"/exams{query}")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    {exam["exam_code"] for exam in response.json()},
                    expected_codes,
                )

    def test_list_exams_rejects_invalid_filters(self):
        invalid_queries = [
            "status=invalid",
            "review_result=invalid",
            "source=invalid",
            "queue_state=invalid",
            "decision=invalid",
            "region=invalid",
        ]
        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(f"/exams?{query}")
                self.assertEqual(response.status_code, 400)

    def test_exam_detail_and_draft_create_update_delete(self):
        detail = self.client.get(f"/exams/{self.start_exam_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIsNone(detail.json()["draft_notes"])
        self.assertEqual(len(detail.json()["diagnoses"]), 2)

        created = self.client.put(
            f"/exams/{self.start_exam_id}/draft",
            json={"notes": " Primeira observacao "},
        )
        updated = self.client.put(
            f"/exams/{self.start_exam_id}/draft",
            json={"notes": "Observacao atualizada"},
        )
        removed = self.client.put(
            f"/exams/{self.start_exam_id}/draft",
            json={"notes": "   "},
        )

        self.assertEqual(created.json()["draft_notes"], "Primeira observacao")
        self.assertEqual(updated.json()["draft_notes"], "Observacao atualizada")
        self.assertIsNone(removed.json()["draft_notes"])
        with self._session() as session:
            self.assertEqual(session.exec(select(ExamDraft)).all(), [])
        self.assertEqual(self.client.get("/exams/99999").status_code, 404)

    def test_exam_image_returns_binary_or_fallback_redirect(self):
        with patch.object(
            main_module,
            "load_metadata_image",
            return_value={"content": b"PNG-CONTENT", "media_type": "image/png"},
        ):
            image = self.client.get(f"/exams/{self.start_exam_id}/image")
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.content, b"PNG-CONTENT")
        self.assertEqual(image.headers["cache-control"], "private, max-age=3600")

        with patch.object(main_module, "load_metadata_image", return_value=None):
            fallback = self.client.get(
                f"/exams/{self.start_exam_id}/image",
                follow_redirects=False,
            )
        self.assertEqual(fallback.status_code, 307)
        self.assertEqual(fallback.headers["location"], "/fallback-start.svg")

    def test_status_update_records_only_real_transitions(self):
        changed = self.client.patch(
            f"/exams/{self.start_exam_id}/status",
            json={"status_validation": "em_validacao"},
        )
        unchanged = self.client.patch(
            f"/exams/{self.start_exam_id}/status",
            json={"status_validation": "em_validacao"},
        )
        forbidden = self.client.patch(
            f"/exams/{self.start_exam_id}/status",
            json={"status_validation": "valido"},
        )
        invalid = self.client.patch(
            f"/exams/{self.start_exam_id}/status",
            json={"status_validation": "invalid"},
        )

        self.assertEqual(changed.status_code, 200)
        self.assertEqual(unchanged.status_code, 200)
        self.assertEqual(forbidden.status_code, 400)
        self.assertEqual(invalid.status_code, 422)
        with self._session() as session:
            reviews = session.exec(
                select(Review).where(Review.exam_id == self.start_exam_id)
            ).all()
        self.assertEqual(len(reviews), 1)

    def test_add_diagnosis_validates_name_options_and_initial_region(self):
        empty = self.client.post(
            f"/exams/{self.start_exam_id}/diagnoses",
            json={"name": "   "},
        )
        disallowed = self.client.post(
            f"/exams/{self.start_exam_id}/diagnoses",
            json={"name": "Diagnostico livre"},
        )
        ordinary = self.client.post(
            f"/exams/{self.start_exam_id}/diagnoses",
            json={"name": "Taquicardia sinusal", "is_abnormal": True},
        )
        infarct = self.client.post(
            f"/exams/{self.start_exam_id}/diagnoses",
            json={"name": "Infarto agudo", "is_abnormal": True},
        )
        mapped = self.client.post(
            f"/exams/{self.start_exam_id}/diagnoses",
            json={
                "name": "Infarto agudo",
                "is_abnormal": True,
                "region_x": 10,
                "region_y": 20,
                "region_width": 30,
                "region_height": 40,
            },
        )

        self.assertEqual(empty.status_code, 400)
        self.assertEqual(disallowed.status_code, 400)
        self.assertEqual(ordinary.status_code, 201)
        self.assertEqual(ordinary.json()["review_status"], "confirmed")
        self.assertEqual(infarct.json()["review_status"], "pending")
        self.assertTrue(infarct.json()["region_required_missing"])
        self.assertEqual(mapped.json()["review_status"], "confirmed")
        self.assertEqual(mapped.json()["regions_count"], 1)
        self.assertEqual(mapped.json()["region_x"], 10)

    def test_region_payload_validation_rejects_invalid_geometry(self):
        payloads = [
            {"x": -1, "y": 0, "width": 10, "height": 10},
            {"x": 0, "y": 0, "width": 0, "height": 10},
            {"x": 90, "y": 0, "width": 20, "height": 10},
        ]
        for payload in payloads:
            with self.subTest(payload=payload):
                response = self.client.post(
                    f"/diagnoses/{self.doctor_diagnosis_id}/regions",
                    json=payload,
                )
                self.assertEqual(response.status_code, 400)

    def test_region_crud_syncs_legacy_fields_and_protects_confirmed_infarct(self):
        pending_infarct = self.client.post(
            f"/exams/{self.start_exam_id}/diagnoses",
            json={"name": "Infarto agudo", "is_abnormal": True},
        ).json()
        diagnosis_id = pending_infarct["id"]
        first = self.client.post(
            f"/diagnoses/{diagnosis_id}/regions",
            json={"x": 10, "y": 10, "width": 20, "height": 20},
        )
        second = self.client.post(
            f"/diagnoses/{diagnosis_id}/regions",
            json={"x": 40, "y": 40, "width": 20, "height": 20},
        )
        first_region_id = first.json()["regions"][0]["id"]
        second_region_id = max(region["id"] for region in second.json()["regions"])

        updated = self.client.patch(
            f"/diagnoses/{diagnosis_id}/regions/{first_region_id}",
            json={"x": 15, "y": 15, "width": 25, "height": 25},
        )
        deleted = self.client.delete(
            f"/diagnoses/{diagnosis_id}/regions/{second_region_id}"
        )
        blocked = self.client.delete(
            f"/diagnoses/{diagnosis_id}/regions/{first_region_id}"
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.json()["review_status"], "confirmed")
        self.assertEqual(updated.json()["region_x"], 15)
        self.assertEqual(deleted.json()["regions_count"], 1)
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(
            self.client.patch(
                f"/diagnoses/{diagnosis_id}/regions/99999",
                json={"x": 1, "y": 1, "width": 2, "height": 2},
            ).status_code,
            404,
        )

    def test_review_original_diagnosis_and_validation_rules(self):
        confirmed = self.client.patch(
            f"/exams/{self.start_exam_id}/diagnoses/{self.start_diagnosis_id}/review",
            json={"review_status": "confirmed"},
        )
        rejected = self.client.patch(
            f"/exams/{self.start_exam_id}/diagnoses/{self.start_diagnosis_id}/review",
            json={"review_status": "rejected", "notes": "Nao observado"},
        )
        doctor_added = self.client.patch(
            f"/exams/{self.start_exam_id}/diagnoses/{self.doctor_diagnosis_id}/review",
            json={"review_status": "confirmed"},
        )
        infarct_without_region = self.client.patch(
            f"/exams/{self.other_exam_id}/diagnoses/{self.infarct_diagnosis_id}/review",
            json={"review_status": "confirmed"},
        )
        missing = self.client.patch(
            f"/exams/{self.start_exam_id}/diagnoses/99999/review",
            json={"review_status": "confirmed"},
        )

        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(rejected.json()["review_status"], "rejected")
        self.assertEqual(doctor_added.status_code, 400)
        self.assertEqual(infarct_without_region.status_code, 400)
        self.assertEqual(missing.status_code, 404)

    def test_remove_diagnosis_preserves_originals(self):
        original = self.client.delete(
            f"/exams/{self.start_exam_id}/diagnoses/{self.start_diagnosis_id}"
        )
        missing = self.client.delete(
            f"/exams/{self.start_exam_id}/diagnoses/99999"
        )
        removed = self.client.delete(
            f"/exams/{self.start_exam_id}/diagnoses/{self.doctor_diagnosis_id}"
        )

        self.assertEqual(original.status_code, 400)
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(removed.json(), {"deleted": self.doctor_diagnosis_id})

    def test_validate_exam_consumes_draft_and_dashboard_reports_counts(self):
        dashboard = self.client.get("/dashboard/stats")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.json()["pending_total"], 2)
        self.assertEqual(dashboard.json()["in_validation_total"], 1)
        self.assertEqual(dashboard.json()["reviewed_total"], 1)
        self.assertEqual(dashboard.json()["reviewed_today"], 1)

        self.client.put(
            f"/exams/{self.start_exam_id}/draft",
            json={"notes": "Nota recuperada do rascunho"},
        )
        validated = self.client.post(
            f"/exams/{self.start_exam_id}/validate",
            json={"review_result": "sem_alteracao"},
        )
        invalid = self.client.post(
            f"/exams/{self.other_exam_id}/validate",
            json={"review_result": "invalid"},
        )

        self.assertEqual(validated.status_code, 200)
        self.assertEqual(validated.json()["status_validation"], "valido")
        self.assertIsNone(validated.json()["draft_notes"])
        self.assertEqual(invalid.status_code, 422)
        with self._session() as session:
            review = session.exec(
                select(Review)
                .where(Review.exam_id == self.start_exam_id)
                .where(Review.status_after == "valido")
            ).one()
            self.assertEqual(review.notes, "Nota recuperada do rascunho")

    def test_database_middleware_initializes_or_resets_non_public_requests(self):
        main_module._db_initialized = False
        with patch.object(main_module, "create_db_and_tables") as create, patch.object(
            main_module, "should_reset_database_on_startup", return_value=False
        ):
            response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        create.assert_called_once_with()

        main_module._db_initialized = False
        with patch.object(main_module, "reset_db_and_tables") as reset, patch.object(
            main_module, "should_reset_database_on_startup", return_value=True
        ):
            response = self.client.get("/auth/me")
        self.assertEqual(response.status_code, 200)
        reset.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
