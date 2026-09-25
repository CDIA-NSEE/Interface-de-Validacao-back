from datetime import date
import unittest

from app.main import _age_at, _patient_payload
from app.models import Patient


class PatientAgeTest(unittest.TestCase):
    def test_computes_age_at_exam_date_before_and_after_birthday(self):
        self.assertEqual(_age_at("06/07/1935", date(2025, 5, 17)), 89)
        self.assertEqual(_age_at("06/07/1935", date(2025, 7, 6)), 90)
        self.assertEqual(_age_at("1935-07-06", date(2025, 7, 5)), 89)

    def test_returns_none_without_usable_birth_or_exam_date(self):
        self.assertIsNone(_age_at(None, date(2025, 5, 17)))
        self.assertIsNone(_age_at("", date(2025, 5, 17)))
        self.assertIsNone(_age_at("data inválida", date(2025, 5, 17)))
        self.assertIsNone(_age_at("06/07/1935", None))
        self.assertIsNone(_age_at("06/07/2030", date(2025, 5, 17)))

    def test_payload_keeps_source_age_and_fills_missing_age_from_birth_date(self):
        with_age = Patient(name="Paciente", age=47, sex="Masculino", weight=0, height=0, bmi=0, birth_date="08/07/1977")
        without_age = Patient(name="Paciente", age=0, sex="Masculino", weight=0, height=0, bmi=0, birth_date="20/02/1969")

        self.assertEqual(_patient_payload(with_age, date(2030, 1, 1))["age"], 47)
        self.assertEqual(_patient_payload(without_age, date(2023, 11, 24))["age"], 54)
        self.assertIsNone(_patient_payload(without_age)["age"])


if __name__ == "__main__":
    unittest.main()
