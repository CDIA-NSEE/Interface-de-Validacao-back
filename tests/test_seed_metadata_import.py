from datetime import datetime
import unittest
from unittest.mock import patch

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app import seed
from app.models import (
    Diagnosis,
    DiagnosisRegion,
    DiagnosisValidation,
    Exam,
    ExamDraft,
    Patient,
    Review,
    ValidationCycle,
)


def _metadata_record(row_id: int, hash_value: str) -> dict:
    return {
        "id": row_id,
        "archive_name": f"archive-{row_id}.pdf",
        "hash": hash_value,
        "image_path": f"image-{row_id}.png",
        "processed_at": "2026-07-14T20:00:00",
        "birth_date": "01/01/1980",
        "birth_date_flag": 1,
        "sex": "Feminino",
        "sex_flag": 1,
        "exam_date": "14/07/2026",
        "exam_date_flag": 1,
        "exam_time": "12:34",
        "exam_time_flag": 1,
        "comments": "Sem comentarios",
        "comments_flag": 1,
        "conclusions": "Ritmo sinusal",
        "conclusions_flag": 1,
        "notes": "Notas",
        "notes_flag": 1,
        "age": 46,
        "age_flag": 1,
        "weight": 70.5,
        "weight_flag": 1,
        "height": 1.7,
        "height_flag": 1,
    }


class SeedMetadataImportTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

    def _session(self):
        return Session(self.engine)

    def _seed_simulated_exam_with_related_rows(self, session: Session) -> tuple[int, int]:
        patient = Patient(
            name="Paciente Simulado",
            age=58,
            sex="Feminino",
            weight=68.0,
            height=1.62,
            bmi=25.9,
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        exam = Exam(
            exam_code="A03B5F",
            patient_id=patient.id,
            exam_date=datetime(2026, 7, 14).date(),
            category="ECG",
            exam_type="ECG repouso",
            status_validation="valido",
            review_result="sem_alteracao",
            image_url="/sample-ecg.svg",
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)

        diagnosis = Diagnosis(
            exam_id=exam.id,
            name="Ritmo sinusal",
            source="original",
            review_status="confirmed",
        )
        session.add(diagnosis)
        session.commit()
        session.refresh(diagnosis)

        session.add(
            DiagnosisRegion(
                exam_id=exam.id,
                diagnosis_id=diagnosis.id,
                x=10,
                y=10,
                width=20,
                height=20,
                created_by_name="Dr. Joao",
            )
        )
        session.add(
            DiagnosisValidation(
                exam_id=exam.id,
                diagnosis_id=diagnosis.id,
                standard_text="Ritmo sinusal",
                cycle_key="default",
                review_status="confirmed",
                reviewer_name="Dr. Joao",
            )
        )
        session.add(
            Review(
                exam_id=exam.id,
                doctor_name="Dr. Joao",
                status_before="em_validacao",
                status_after="valido",
            )
        )
        session.add(
            ExamDraft(
                exam_id=exam.id,
                reviewer_id=1,
                notes="Rascunho do exame simulado.",
            )
        )
        session.commit()
        return patient.id, exam.id

    def test_real_metadata_import_removes_simulated_seed_and_related_rows(self):
        records = [_metadata_record(10, "realhash1234567890")]

        with self._session() as session:
            self._seed_simulated_exam_with_related_rows(session)

            with patch.object(seed, "load_metadata_records", return_value=records):
                self.assertTrue(seed._import_metadata_database(session))

            exams = session.exec(select(Exam)).all()
            self.assertEqual(len(exams), 1)
            self.assertEqual(exams[0].metadata_id, 10)
            self.assertEqual(exams[0].metadata_hash, "realhash1234567890")
            self.assertEqual(exams[0].status_validation, "nao_validado")
            self.assertEqual(session.exec(select(DiagnosisRegion)).all(), [])
            self.assertEqual(session.exec(select(DiagnosisValidation)).all(), [])
            self.assertEqual(session.exec(select(Review)).all(), [])
            self.assertEqual(session.exec(select(ExamDraft)).all(), [])
            self.assertIsNone(session.exec(select(Exam).where(Exam.exam_code == "A03B5F")).first())
            self.assertIsNone(
                session.exec(select(Patient).where(Patient.name == "Paciente Simulado")).first()
            )

    def test_real_metadata_import_preserves_patient_with_non_simulated_exam(self):
        records = [_metadata_record(10, "realhash1234567890")]

        with self._session() as session:
            simulated_patient_id, _ = self._seed_simulated_exam_with_related_rows(session)
            session.add(
                Exam(
                    exam_code="REAL1234",
                    patient_id=simulated_patient_id,
                    exam_date=datetime(2026, 7, 15).date(),
                    category="ECG",
                    exam_type="ECG repouso",
                    status_validation="nao_validado",
                    metadata_id=99,
                    metadata_hash="already-real-hash",
                )
            )
            session.commit()

            with patch.object(seed, "load_metadata_records", return_value=records):
                self.assertTrue(seed._import_metadata_database(session))

            self.assertIsNotNone(session.get(Patient, simulated_patient_id))
            self.assertIsNotNone(session.exec(select(Exam).where(Exam.exam_code == "REAL1234")).first())
            self.assertIsNone(session.exec(select(Exam).where(Exam.exam_code == "A03B5F")).first())

    def test_real_metadata_import_is_idempotent_by_metadata_hash(self):
        records = [
            _metadata_record(10, "realhash1234567890"),
            _metadata_record(11, "secondhash123456789"),
        ]

        with self._session() as session:
            with patch.object(seed, "load_metadata_records", return_value=records):
                self.assertTrue(seed._import_metadata_database(session))
                self.assertTrue(seed._import_metadata_database(session))

            exams = session.exec(select(Exam).order_by(Exam.metadata_id)).all()
            self.assertEqual([exam.metadata_id for exam in exams], [10, 11])
            self.assertEqual([exam.metadata_hash for exam in exams], [record["hash"] for record in records])
            self.assertEqual(len(session.exec(select(Patient)).all()), 2)
            self.assertEqual(len(session.exec(select(Diagnosis)).all()), 2)

    def test_real_metadata_import_skips_duplicate_hashes_in_same_source(self):
        duplicate_hash = "duplicatedhash123456"
        records = [
            _metadata_record(10, duplicate_hash),
            _metadata_record(11, duplicate_hash),
        ]

        with self._session() as session:
            with patch.object(seed, "load_metadata_records", return_value=records):
                self.assertTrue(seed._import_metadata_database(session))

            exams = session.exec(select(Exam)).all()
            self.assertEqual(len(exams), 1)
            self.assertEqual(exams[0].metadata_id, 10)
            self.assertEqual(exams[0].metadata_hash, duplicate_hash)
            self.assertEqual(len(session.exec(select(Patient)).all()), 1)
            self.assertEqual(len(session.exec(select(Diagnosis)).all()), 1)

    def test_seed_helpers_handle_bmi_dates_and_abnormal_diagnoses(self):
        self.assertEqual(seed._bmi(0, 1.7), 0)
        self.assertEqual(seed._bmi(70, 0), 0)
        self.assertEqual(seed._bmi(70, 170), 24.2)
        self.assertEqual(seed._parse_date("21/07/2026"), datetime(2026, 7, 21))
        self.assertFalse(seed._is_abnormal("RITMO SINUSAL"))
        self.assertFalse(
            seed._is_abnormal("ELETROCARDIOGRAMA DENTRO DOS LIMITES DA NORMALIDADE")
        )
        self.assertTrue(seed._is_abnormal("INFARTO AGUDO"))

    def test_validation_cycle_is_created_then_updated(self):
        first_calendar = {
            "cycle_key": "cycle-test",
            "cycle_label": "Ciclo inicial",
            "general_review_day": 30,
        }
        updated_calendar = {
            **first_calendar,
            "cycle_label": "Ciclo atualizado",
            "general_review_day": 28,
        }

        with self._session() as session, patch.object(
            seed,
            "load_validation_calendar",
            side_effect=[first_calendar, updated_calendar],
        ):
            seed._seed_validation_cycle(session)
            seed._seed_validation_cycle(session)
            cycle = session.exec(select(ValidationCycle)).one()

        self.assertEqual(cycle.label, "Ciclo atualizado")
        self.assertEqual(cycle.general_review_day, 28)

    def test_existing_seed_is_normalized_when_metadata_is_unavailable(self):
        with self._session() as session:
            patient = Patient(
                name="Paciente legado",
                age=40,
                sex="Feminino",
                weight=60,
                height=1.6,
                bmi=23.4,
            )
            session.add(patient)
            session.commit()
            session.refresh(patient)
            exam = Exam(
                exam_code="LEGACY01",
                patient_id=patient.id,
                exam_date=datetime(2026, 7, 21).date(),
                category="Rotina",
                exam_type="ECG seriado",
            )
            session.add(exam)
            session.commit()

            with patch.object(seed, "_import_metadata_database", return_value=False), patch.object(
                seed,
                "load_validation_calendar",
                return_value={
                    "cycle_key": "default",
                    "cycle_label": "Ciclo",
                    "general_review_day": 30,
                },
            ):
                seed.seed_database(session)

            normalized = session.exec(select(Exam).where(Exam.exam_code == "LEGACY01")).one()
            self.assertEqual(normalized.category, "ECG")
            self.assertEqual(normalized.exam_type, "ECG repouso")

    def test_empty_database_receives_complete_simulated_fallback(self):
        with self._session() as session, patch.object(
            seed,
            "_import_metadata_database",
            return_value=False,
        ), patch.object(
            seed,
            "load_validation_calendar",
            return_value={
                "cycle_key": "default",
                "cycle_label": "Ciclo de teste",
                "general_review_day": 30,
            },
        ):
            seed.seed_database(session)

            exams = session.exec(select(Exam)).all()
            patients = session.exec(select(Patient)).all()
            diagnoses = session.exec(select(Diagnosis)).all()
            reviews = session.exec(select(Review)).all()
            cycle = session.exec(select(ValidationCycle)).one()

        self.assertEqual(len(exams), 12)
        self.assertEqual(len(patients), 12)
        self.assertEqual(len(diagnoses), 9)
        self.assertEqual(len(reviews), 7)
        self.assertTrue(all(exam.category == "ECG" for exam in exams))
        self.assertTrue(all(exam.exam_type == "ECG repouso" for exam in exams))
        self.assertEqual(cycle.label, "Ciclo de teste")


if __name__ == "__main__":
    unittest.main()
