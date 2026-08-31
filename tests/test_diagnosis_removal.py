from datetime import date
import unittest

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.main import remove_diagnosis
from app.models import Diagnosis, DiagnosisRegion, Exam, Patient, User


class DiagnosisRemovalTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(self.engine)

        with Session(self.engine) as session:
            patient = Patient(name="Paciente", age=40, sex="Feminino", weight=65, height=1.65, bmi=23.9)
            user = User(username="medico", full_name="Médico", hashed_password="hash")
            session.add_all([patient, user])
            session.commit()
            session.refresh(patient)
            session.refresh(user)

            exam = Exam(
                exam_code="REMOVE001",
                patient_id=patient.id,
                exam_date=date(2026, 8, 30),
                category="ECG",
                exam_type="ECG repouso",
            )
            session.add(exam)
            session.commit()
            session.refresh(exam)

            diagnosis = Diagnosis(exam_id=exam.id, name="Fibrilação atrial", source="doctor_added")
            session.add(diagnosis)
            session.commit()
            session.refresh(diagnosis)
            session.add_all([
                DiagnosisRegion(exam_id=exam.id, diagnosis_id=diagnosis.id, x=10, y=10, width=20, height=20, created_by_name="Médico"),
                DiagnosisRegion(exam_id=exam.id, diagnosis_id=diagnosis.id, x=40, y=40, width=10, height=10, created_by_name="Médico"),
            ])
            session.commit()

            self.exam_id = exam.id
            self.diagnosis_id = diagnosis.id
            self.user_id = user.id

    def test_removes_doctor_diagnosis_and_all_regions_atomically(self):
        with Session(self.engine) as session:
            result = remove_diagnosis(
                self.exam_id,
                self.diagnosis_id,
                session.get(User, self.user_id),
                session,
            )

            self.assertEqual(result, {"deleted": self.diagnosis_id})
            self.assertIsNone(session.get(Diagnosis, self.diagnosis_id))
            self.assertEqual(
                session.exec(select(DiagnosisRegion).where(DiagnosisRegion.diagnosis_id == self.diagnosis_id)).all(),
                [],
            )


if __name__ == "__main__":
    unittest.main()
