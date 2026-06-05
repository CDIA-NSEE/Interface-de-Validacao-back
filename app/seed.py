from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import Diagnosis, Exam, Patient, Review


def _bmi(weight: float, height: float) -> float:
    return round(weight / (height * height), 1)


def seed_database(session: Session) -> None:
    existing_exam = session.exec(select(Exam)).first()
    if existing_exam:
        return

    now = datetime.utcnow()

    rows = [
        {
            "patient": ("Maria Oliveira", 58, "Feminino", 68.0, 1.62),
            "exam_code": "A03B5F",
            "days_ago": 0,
            "category": "Rotina",
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Ritmo sinusal", False)],
        },
        {
            "patient": ("Carlos Mendes", 44, "Masculino", 82.0, 1.78),
            "exam_code": "43DA34",
            "days_ago": 1,
            "category": "Ambulatorial",
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Sem alterações significativas", False)],
        },
        {
            "patient": ("Ana Beatriz Souza", 35, "Feminino", 61.5, 1.67),
            "exam_code": "A9FF32",
            "days_ago": 2,
            "category": "Emergencia",
            "exam_type": "ECG seriado",
            "status_validation": "valido",
            "review_result": "alterado",
            "diagnoses": [("Taquicardia sinusal", True)],
        },
        {
            "patient": ("Roberto Lima", 67, "Masculino", 88.4, 1.72),
            "exam_code": "F3B234",
            "days_ago": 0,
            "category": "Rotina",
            "exam_type": "ECG repouso",
            "status_validation": "nao_validado",
            "review_result": None,
            "diagnoses": [],
        },
        {
            "patient": ("Helena Costa", 72, "Feminino", 70.2, 1.59),
            "exam_code": "C91A77",
            "days_ago": 0,
            "category": "Ambulatorial",
            "exam_type": "ECG pre-operatorio",
            "status_validation": "em_validacao",
            "review_result": None,
            "diagnoses": [("Possível alteração inespecífica", True)],
        },
        {
            "patient": ("Paulo Henrique", 51, "Masculino", 91.0, 1.81),
            "exam_code": "B18C22",
            "days_ago": 3,
            "category": "Rotina",
            "exam_type": "ECG repouso",
            "status_validation": "nao_validado",
            "review_result": None,
            "diagnoses": [],
        },
        {
            "patient": ("Luciana Rocha", 63, "Feminino", 74.0, 1.65),
            "exam_code": "D77E90",
            "days_ago": 4,
            "category": "Emergencia",
            "exam_type": "ECG seriado",
            "status_validation": "valido",
            "review_result": "alterado",
            "diagnoses": [("Extrassístoles ventriculares", True)],
        },
        {
            "patient": ("Marcos Vinicius", 29, "Masculino", 76.8, 1.75),
            "exam_code": "E10F45",
            "days_ago": 5,
            "category": "Ocupacional",
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Ritmo sinusal", False)],
        },
        {
            "patient": ("Patricia Almeida", 49, "Feminino", 65.3, 1.61),
            "exam_code": "AA1209",
            "days_ago": 1,
            "category": "Ambulatorial",
            "exam_type": "ECG seriado",
            "status_validation": "em_validacao",
            "review_result": None,
            "diagnoses": [("Bradicardia sinusal", True)],
        },
        {
            "patient": ("Eduardo Nunes", 56, "Masculino", 85.5, 1.74),
            "exam_code": "BB4421",
            "days_ago": 2,
            "category": "Ocupacional",
            "exam_type": "ECG repouso",
            "status_validation": "nao_validado",
            "review_result": None,
            "diagnoses": [],
        },
        {
            "patient": ("Renata Ferreira", 40, "Feminino", 59.0, 1.64),
            "exam_code": "C0DE15",
            "days_ago": 6,
            "category": "Rotina",
            "exam_type": "ECG pre-operatorio",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Intervalos dentro da normalidade", False)],
        },
        {
            "patient": ("João Batista", 69, "Masculino", 79.7, 1.69),
            "exam_code": "FF210A",
            "days_ago": 7,
            "category": "Emergencia",
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "alterado",
            "diagnoses": [("Bloqueio de ramo direito", True)],
        },
    ]

    for index, row in enumerate(rows):
        name, age, sex, weight, height = row["patient"]
        patient = Patient(
            name=name,
            age=age,
            sex=sex,
            weight=weight,
            height=height,
            bmi=_bmi(weight, height),
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        created_at = now - timedelta(days=row["days_ago"], hours=index)
        exam = Exam(
            exam_code=row["exam_code"],
            patient_id=patient.id,
            exam_date=created_at.date(),
            category=row["category"],
            exam_type=row["exam_type"],
            status_validation=row["status_validation"],
            review_result=row["review_result"],
            image_url="/sample-ecg.svg",
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)

        for diagnosis_name, is_abnormal in row["diagnoses"]:
            session.add(
                Diagnosis(
                    exam_id=exam.id,
                    name=diagnosis_name,
                    is_abnormal=is_abnormal,
                    created_at=created_at,
                )
            )

        if row["status_validation"] == "valido":
            session.add(
                Review(
                    exam_id=exam.id,
                    doctor_name="Dr. João",
                    status_before="em_validacao",
                    status_after="valido",
                    review_result=row["review_result"],
                    notes="Seed de revisão inicial.",
                    created_at=created_at,
                )
            )

        session.commit()

