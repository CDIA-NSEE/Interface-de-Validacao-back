import json
import unittest

from app.config_source import CONFIG_DIR, standardize_diagnosis


class DiagnosisGroupingsTest(unittest.TestCase):
    def test_groupings_file_does_not_contain_mojibake(self):
        content = (CONFIG_DIR / "diagnosis_groupings.json").read_text(encoding="utf-8")
        mojibake_sequences = (
            "\u00c3\u0087",
            "\u00c3\u0083",
            "\u00c3\u0095",
            "\u00c3\u0081",
            "\u00c3\u0089",
            "\u00c3\u008d",
            "\u00c3\u0093",
            "\u00c3\u009a",
            "\u00c3\u00a3",
        )
        for mojibake in mojibake_sequences:
            self.assertNotIn(mojibake, content)
        self.assertNotIn("\ufffd", content)

        json.loads(content)

    def test_standardizes_accented_diagnosis_variants(self):
        self.assertEqual(
            standardize_diagnosis("ALTERAÇÃO DA REPOLARIZAÇÃO VENTRICULAR COM ONDA T INVERTIDA obs"),
            "Onda T invertida parede inferior",
        )
        self.assertEqual(
            standardize_diagnosis("POSSÍVEL SOBRECARGA ATRIAL ESQUERDA"),
            "Sobrecarga atrial esquerda",
        )


if __name__ == "__main__":
    unittest.main()
