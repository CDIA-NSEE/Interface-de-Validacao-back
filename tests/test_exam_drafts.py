from datetime import date
import unittest

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.main import get_exam, save_exam_draft, validate_exam
from app.models import Exam, ExamDraft, Patient, Review, User
from app.schemas import ExamDraftUpdate, ExamValidate


class ExamDraftTest(unittest.TestCase):
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
            owner = User(
                username="medico.um",
                full_name="Medico Um",
                hashed_password="hash",
            )
            other_user = User(
                username="medico.dois",
                full_name="Medico Dois",
                hashed_password="hash",
            )
            session.add_all([patient, owner, other_user])
            session.commit()
            session.refresh(patient)
            session.refresh(owner)
            session.refresh(other_user)

            exam = Exam(
                exam_code="DRAFT001",
                patient_id=patient.id,
                exam_date=date(2026, 7, 16),
                category="ECG",
                exam_type="ECG repouso",
            )
            session.add(exam)
            session.commit()
            session.refresh(exam)

            self.exam_id = exam.id
            self.owner_id = owner.id
            self.other_user_id = other_user.id

    def _session(self):
        return Session(self.engine)

    def test_saves_draft_and_exposes_it_only_to_its_owner(self):
        with self._session() as session:
            owner = session.get(User, self.owner_id)
            other_user = session.get(User, self.other_user_id)

            saved = save_exam_draft(
                self.exam_id,
                ExamDraftUpdate(notes="Revisar derivacao V2."),
                owner,
                session,
            )
            owner_exam = get_exam(self.exam_id, owner, session)
            other_user_exam = get_exam(self.exam_id, other_user, session)

            self.assertEqual(saved["draft_notes"], "Revisar derivacao V2.")
            self.assertEqual(owner_exam["draft_notes"], "Revisar derivacao V2.")
            self.assertIsNone(other_user_exam["draft_notes"])
            self.assertEqual(session.exec(select(ExamDraft)).one().reviewer_id, owner.id)

    def test_final_validation_uses_and_clears_owners_draft(self):
        with self._session() as session:
            owner = session.get(User, self.owner_id)

            save_exam_draft(
                self.exam_id,
                ExamDraftUpdate(notes="Observacao do rascunho."),
                owner,
                session,
            )
            validated = validate_exam(
                self.exam_id,
                ExamValidate(review_result="sem_alteracao"),
                owner,
                session,
            )

            review = session.exec(select(Review)).one()
            self.assertEqual(review.notes, "Observacao do rascunho.")
            self.assertIsNone(validated["draft_notes"])
            self.assertEqual(session.exec(select(ExamDraft)).all(), [])


if __name__ == "__main__":
    unittest.main()
