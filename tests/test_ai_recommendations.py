import json
import os
import unittest
from datetime import date
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import config_source
from app.config_source import ai_suggested, load_ai_recommendations
from app.main import _context_payload, _diagnosis_payload, get_exam
from app.models import Diagnosis, Exam, Patient, User


class AiRecommendationsConfigTest(unittest.TestCase):
    def setUp(self):
        self.original_loader = config_source._load_json
        self.config = {
            "enabled": True,
            "suggestions": [
                {
                    "exam_code": " ECG-001 ",
                    "standard_diagnoses": [
                        "Possível sobrecarga atrial esquerda",
                        "",
                        42,
                    ],
                },
                {"exam_code": "", "standard_diagnoses": ["Ritmo sinusal"]},
                {"exam_code": "ECG-002", "standard_diagnoses": []},
            ],
        }

    def loader_for(self, ai_config):
        def load(name, default):
            if name == "ai_recommendations.json":
                if isinstance(ai_config, Exception):
                    raise ai_config
                return ai_config
            return self.original_loader(name, default)

        return load

    def test_loads_only_complete_entries_and_standardizes_diagnoses(self):
        with (
            patch("app.config_source._load_json", side_effect=self.loader_for(self.config)),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("AI_MODE_ENABLED", None)
            loaded = load_ai_recommendations()

        self.assertTrue(loaded["enabled"])
        self.assertEqual(len(loaded["suggestions"]), 1)
        self.assertEqual(loaded["suggestions"][0]["exam_code"], "ECG-001")
        self.assertEqual(
            loaded["suggestions"][0]["standard_diagnoses"],
            ["Sobrecarga atrial esquerda"],
        )

    def test_environment_override_can_enable_or_disable_mode(self):
        for override, expected in (("true", True), ("0", False)):
            with self.subTest(override=override):
                with (
                    patch(
                        "app.config_source._load_json",
                        side_effect=self.loader_for(self.config),
                    ),
                    patch.dict(os.environ, {"AI_MODE_ENABLED": override}),
                ):
                    self.assertEqual(load_ai_recommendations()["enabled"], expected)

    def test_unknown_environment_override_fails_closed(self):
        with (
            patch(
                "app.config_source._load_json",
                side_effect=self.loader_for(self.config),
            ),
            patch.dict(os.environ, {"AI_MODE_ENABLED": "maybe"}),
        ):
            self.assertEqual(
                load_ai_recommendations(),
                {"enabled": False, "suggestions": []},
            )

    def test_missing_invalid_or_malformed_configuration_fails_closed(self):
        invalid_sources = (
            None,
            {},
            {"enabled": "yes", "suggestions": []},
            {"enabled": True, "suggestions": "not-a-list"},
            FileNotFoundError("missing"),
            json.JSONDecodeError("invalid", "{", 0),
        )

        for source in invalid_sources:
            with self.subTest(source=source):
                loader = patch(
                    "app.config_source._load_json",
                    side_effect=self.loader_for(source),
                )
                with loader, patch.dict(os.environ, {}, clear=False):
                    os.environ.pop("AI_MODE_ENABLED", None)
                    self.assertEqual(
                        load_ai_recommendations(),
                        {"enabled": False, "suggestions": []},
                    )

    def test_matches_exam_and_equivalent_standardized_diagnosis_only_when_enabled(self):
        with (
            patch(
                "app.config_source._load_json",
                side_effect=self.loader_for(self.config),
            ),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("AI_MODE_ENABLED", None)
            recommendations = load_ai_recommendations()

        self.assertTrue(
            ai_suggested(
                "ecg-001",
                "POSSÍVEL SOBRECARGA ATRIAL ESQUERDA",
                recommendations,
            )
        )
        self.assertFalse(ai_suggested("ECG-999", "Sobrecarga atrial esquerda", recommendations))
        self.assertFalse(ai_suggested("ECG-001", "Ritmo sinusal", recommendations))
        self.assertFalse(
            ai_suggested(
                "ECG-001",
                "Sobrecarga atrial esquerda",
                {**recommendations, "enabled": False},
            )
        )

    def test_wildcard_matches_only_sinus_rhythm_for_any_exam(self):
        recommendations = {
            "enabled": True,
            "suggestions": [
                {
                    "exam_code": "*",
                    "standard_diagnoses": ["Ritmo sinusal"],
                }
            ],
        }

        for exam_code in ("ECG-001", "ECG-002", "NEW-EXAM-999"):
            with self.subTest(exam_code=exam_code):
                self.assertTrue(ai_suggested(exam_code, "Ritmo sinusal", recommendations))

        self.assertFalse(ai_suggested("ECG-001", "Bradicardia sinusal", recommendations))
        self.assertFalse(ai_suggested("ECG-002", "Taquicardia sinusal", recommendations))

    def test_versioned_config_is_disabled_by_default_and_works_when_enabled(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("AI_MODE_ENABLED", None)
            recommendations = load_ai_recommendations()

        self.assertEqual(recommendations, {"enabled": False, "suggestions": []})

        with patch.dict(os.environ, {"AI_MODE_ENABLED": "true"}):
            recommendations = load_ai_recommendations()

        self.assertEqual(
            recommendations,
            {
                "enabled": True,
                "suggestions": [
                    {
                        "exam_code": "*",
                        "standard_diagnoses": ["Ritmo sinusal"],
                    }
                ],
            },
        )
        self.assertTrue(ai_suggested("NEW-EXAM", "Ritmo sinusal", recommendations))
        self.assertFalse(ai_suggested("NEW-EXAM", "Bradicardia sinusal", recommendations))
        self.assertFalse(ai_suggested("NEW-EXAM", "Taquicardia sinusal", recommendations))


class AiRecommendationsPayloadTest(unittest.TestCase):
    def setUp(self):
        self.diagnosis = Diagnosis(
            id=7,
            exam_id=3,
            name="Possível sobrecarga atrial esquerda",
            source="original",
            review_status="pending",
        )
        self.context = {
            "cycle_key": "default",
            "active_standard_diagnosis": None,
        }
        self.recommendations = {
            "enabled": True,
            "suggestions": [
                {
                    "exam_code": "*",
                    "standard_diagnoses": ["Sobrecarga atrial esquerda"],
                }
            ],
        }

    def test_context_exposes_global_ai_mode(self):
        with (
            patch("app.main.active_validation_context", return_value={"cycle_key": "default"}),
            patch("app.main.load_support_contact", return_value={}),
            patch("app.main.load_ai_recommendations", return_value=self.recommendations),
        ):
            payload = _context_payload()

        self.assertTrue(payload["ai_mode_enabled"])

    def test_diagnosis_payload_marks_suggestion_without_changing_medical_decision(self):
        payload = _diagnosis_payload(
            self.diagnosis,
            context=self.context,
            exam_code="ECG-001",
            ai_recommendations=self.recommendations,
        )

        self.assertTrue(payload["ai_suggested"])
        self.assertEqual(payload["review_status"], "pending")
        self.assertEqual(payload["validation_status"], "pending")

    def test_diagnosis_payload_returns_false_when_mode_is_disabled(self):
        payload = _diagnosis_payload(
            self.diagnosis,
            context=self.context,
            exam_code="ECG-001",
            ai_recommendations={**self.recommendations, "enabled": False},
        )

        self.assertFalse(payload["ai_suggested"])

    def test_exam_payload_marks_existing_diagnosis_without_creating_or_deciding_it(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)

        with Session(engine) as session:
            patient = Patient(
                name="Paciente de teste",
                age=50,
                sex="Feminino",
                weight=70,
                height=1.65,
                bmi=25.7,
            )
            user = User(
                username="medico.teste",
                full_name="Medico Teste",
                hashed_password="hash",
            )
            session.add_all([patient, user])
            session.commit()
            session.refresh(patient)
            session.refresh(user)

            exam = Exam(
                exam_code="ECG-001",
                patient_id=patient.id,
                exam_date=date(2026, 8, 27),
                category="ECG",
                exam_type="ECG repouso",
            )
            session.add(exam)
            session.commit()
            session.refresh(exam)

            diagnosis = Diagnosis(
                exam_id=exam.id,
                name="Possível sobrecarga atrial esquerda",
                source="original",
                review_status="pending",
            )
            session.add(diagnosis)
            session.commit()

            with patch(
                "app.main.load_ai_recommendations",
                return_value=self.recommendations,
            ):
                payload = get_exam(exam.id, user, session)

            self.assertEqual(len(payload["diagnoses"]), 1)
            self.assertTrue(payload["diagnoses"][0]["ai_suggested"])
            self.assertEqual(payload["diagnoses"][0]["review_status"], "pending")
            self.assertEqual(len(session.exec(select(Diagnosis)).all()), 1)

            mutation_payload = _diagnosis_payload(
                diagnosis,
                session=session,
                context=self.context,
                ai_recommendations=self.recommendations,
            )
            self.assertTrue(mutation_payload["ai_suggested"])
            self.assertEqual(mutation_payload["review_status"], "pending")


if __name__ == "__main__":
    unittest.main()
