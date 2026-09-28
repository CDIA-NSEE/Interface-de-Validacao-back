from datetime import date
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.main import get_exam_image
from app.models import Exam, Patient, User


class ExamImageTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine) as session:
            patient = Patient(
                name="Paciente de teste",
                age=50,
                sex="Feminino",
                weight=70,
                height=1.65,
                bmi=25.7,
            )
            user = User(username="medico.um", full_name="Medico Um", hashed_password="hash")
            session.add_all([patient, user])
            session.commit()
            session.refresh(patient)
            session.refresh(user)

            exam = Exam(
                exam_code="IMG001",
                patient_id=patient.id,
                exam_date=date(2026, 7, 16),
                category="ECG",
                exam_type="ECG",
                metadata_id=7,
            )
            session.add(exam)
            session.commit()
            session.refresh(exam)

            self.exam_id = exam.id
            self.user = user

    def tearDown(self):
        self.engine.dispose()

    def test_returns_the_metadata_image(self):
        image = {"content": b"BM" + b"\x00" * 64, "media_type": "image/bmp"}

        with Session(self.engine) as session, patch("app.main.load_metadata_image", return_value=image):
            response = get_exam_image(self.exam_id, current_user=self.user, session=session)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, image["content"])
        self.assertEqual(response.media_type, "image/bmp")

    def test_responds_404_instead_of_a_sample_ecg_when_there_is_no_image(self):
        with Session(self.engine) as session, patch("app.main.load_metadata_image", return_value=None):
            with self.assertRaises(HTTPException) as context:
                get_exam_image(self.exam_id, current_user=self.user, session=session)

        self.assertEqual(context.exception.status_code, 404)
        self.assertEqual(context.exception.detail, "Imagem do ECG não encontrada.")


if __name__ == "__main__":
    unittest.main()
