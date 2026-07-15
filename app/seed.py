from datetime import datetime, timedelta
import os

from sqlmodel import Session, select

from app.auth import get_password_hash
from app.config_source import load_validation_calendar
from app.metadata_source import conclusion_items, load_metadata_records
from app.models import (
    Diagnosis,
    DiagnosisRegion,
    DiagnosisValidation,
    Exam,
    Patient,
    Review,
    User,
    ValidationCycle,
)


SIMULATED_CATEGORIES = {"Rotina", "Ambulatorial", "Ocupacional", "Emergencia"}
SIMULATED_EXAM_TYPES = {"ECG seriado", "ECG pre-operatorio"}
SIMULATED_EXAM_CODES = {
    "A03B5F",
    "43DA34",
    "A9FF32",
    "F3B234",
    "C91A77",
    "B18C22",
    "D77E90",
    "E10F45",
    "AA1209",
    "BB4421",
    "C0DE15",
    "FF210A",
}

DEFAULT_DATABASE_URL = "sqlite:///./ecg_review.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
DEFAULT_USER_USERNAME = os.getenv("DEFAULT_USER_USERNAME", "dr.joao").strip().lower()
DEFAULT_USER_FULL_NAME = os.getenv("DEFAULT_USER_FULL_NAME", "Dr. João").strip()
DEFAULT_USER_PASSWORD = os.getenv("DEFAULT_USER_PASSWORD")
if DEFAULT_USER_PASSWORD is None and DATABASE_URL == DEFAULT_DATABASE_URL:
    DEFAULT_USER_PASSWORD = "medpage123"
DEFAULT_ADMIN_USERNAME = os.getenv("DEFAULT_ADMIN_USERNAME", "admin").strip().lower()
DEFAULT_ADMIN_FULL_NAME = os.getenv("DEFAULT_ADMIN_FULL_NAME", "Administrador Operacional").strip()
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD")
if DEFAULT_ADMIN_PASSWORD is None and DATABASE_URL == DEFAULT_DATABASE_URL:
    DEFAULT_ADMIN_PASSWORD = "admin123"


def _bmi(weight: float, height: float) -> float:
    if not weight or not height:
        return 0
    if height > 3:
        height /= 100
    return round(weight / (height * height), 1)


def _parse_date(value: str) -> datetime:
    return datetime.strptime(value, "%d/%m/%Y")


def _is_abnormal(diagnosis: str) -> bool:
    return diagnosis not in {
        "RITMO SINUSAL",
        "ELETROCARDIOGRAMA DENTRO DOS LIMITES DA NORMALIDADE",
    }


def _remove_simulated_data(session: Session) -> None:
    exams = session.exec(select(Exam).where(Exam.exam_code.in_(SIMULATED_EXAM_CODES))).all()
    if not exams:
        return

    exam_ids = {exam.id for exam in exams}
    patient_ids = {exam.patient_id for exam in exams}

    for validation in session.exec(
        select(DiagnosisValidation).where(DiagnosisValidation.exam_id.in_(exam_ids))
    ).all():
        session.delete(validation)
    for region in session.exec(select(DiagnosisRegion).where(DiagnosisRegion.exam_id.in_(exam_ids))).all():
        session.delete(region)
    for diagnosis in session.exec(select(Diagnosis).where(Diagnosis.exam_id.in_(exam_ids))).all():
        session.delete(diagnosis)
    for review in session.exec(select(Review).where(Review.exam_id.in_(exam_ids))).all():
        session.delete(review)
    for exam in exams:
        session.delete(exam)
    session.flush()

    for patient_id in patient_ids:
        has_remaining_exam = session.exec(select(Exam).where(Exam.patient_id == patient_id)).first()
        if not has_remaining_exam:
            patient = session.get(Patient, patient_id)
            if patient:
                session.delete(patient)
    session.commit()


def _import_metadata_database(session: Session) -> bool:
    records = load_metadata_records()
    if not records:
        return False

    _remove_simulated_data(session)
    imported_hashes = {
        metadata_hash
        for metadata_hash in session.exec(select(Exam.metadata_hash)).all()
        if metadata_hash
    }

    for record in records:
        if record["hash"] in imported_hashes:
            continue

        weight = record["weight"] if record["weight_flag"] and record["weight"] else 0
        height = record["height"] if record["height_flag"] and record["height"] else 0
        patient = Patient(
            name="",
            birth_date=record["birth_date"] if record["birth_date_flag"] else None,
            age=record["age"] if record["age_flag"] and record["age"] else 0,
            sex=record["sex"] if record["sex_flag"] else "",
            weight=weight,
            height=height,
            bmi=_bmi(weight, height),
        )
        session.add(patient)
        session.commit()
        session.refresh(patient)

        exam_datetime = _parse_date(record["exam_date"])
        exam = Exam(
            exam_code=record["hash"][:8].upper(),
            patient_id=patient.id,
            exam_date=exam_datetime.date(),
            exam_time=record["exam_time"] if record["exam_time_flag"] else None,
            category="ECG",
            exam_type="ECG repouso",
            status_validation="nao_validado",
            image_url="/sample-ecg.svg",
            metadata_id=record["id"],
            metadata_hash=record["hash"],
            comments=record["comments"] if record["comments_flag"] else None,
            source_notes=record["notes"] if record["notes_flag"] else None,
            created_at=exam_datetime,
            updated_at=exam_datetime,
        )
        session.add(exam)
        session.commit()
        session.refresh(exam)

        if record["conclusions_flag"]:
            for diagnosis_name in conclusion_items(record["conclusions"]):
                session.add(
                    Diagnosis(
                        exam_id=exam.id,
                        name=diagnosis_name,
                        source="original",
                        review_status="pending",
                        is_abnormal=_is_abnormal(diagnosis_name),
                        created_at=exam_datetime,
                    )
                )
        session.commit()
        imported_hashes.add(record["hash"])

    return True


def _normalize_simulated_metadata(session: Session) -> None:
    exams = session.exec(select(Exam)).all()
    changed = False

    for exam in exams:
        exam_changed = False
        if exam.category in SIMULATED_CATEGORIES:
            exam.category = "ECG"
            exam_changed = True
        if exam.exam_type in SIMULATED_EXAM_TYPES:
            exam.exam_type = "ECG repouso"
            exam_changed = True
        if exam_changed:
            changed = True
            session.add(exam)

    if changed:
        session.commit()


def _seed_default_user(session: Session) -> None:
    if not DEFAULT_USER_USERNAME or not DEFAULT_USER_PASSWORD:
        return

    user = session.exec(select(User).where(User.username == DEFAULT_USER_USERNAME)).first()
    if user:
        changed = False
        if user.full_name != DEFAULT_USER_FULL_NAME:
            user.full_name = DEFAULT_USER_FULL_NAME
            changed = True
        if user.role != "doctor":
            user.role = "doctor"
            changed = True
        if changed:
            session.add(user)
            session.commit()
        return

    session.add(
        User(
            username=DEFAULT_USER_USERNAME,
            full_name=DEFAULT_USER_FULL_NAME or DEFAULT_USER_USERNAME,
            hashed_password=get_password_hash(DEFAULT_USER_PASSWORD),
            role="doctor",
        )
    )
    session.commit()


def _seed_admin_user(session: Session) -> None:
    if not DEFAULT_ADMIN_USERNAME or not DEFAULT_ADMIN_PASSWORD:
        return

    user = session.exec(select(User).where(User.username == DEFAULT_ADMIN_USERNAME)).first()
    if user:
        changed = False
        if user.full_name != DEFAULT_ADMIN_FULL_NAME:
            user.full_name = DEFAULT_ADMIN_FULL_NAME
            changed = True
        if user.role != "admin":
            user.role = "admin"
            changed = True
        if changed:
            session.add(user)
            session.commit()
        return

    session.add(
        User(
            username=DEFAULT_ADMIN_USERNAME,
            full_name=DEFAULT_ADMIN_FULL_NAME or DEFAULT_ADMIN_USERNAME,
            hashed_password=get_password_hash(DEFAULT_ADMIN_PASSWORD),
            role="admin",
        )
    )
    session.commit()


def _seed_validation_cycle(session: Session) -> None:
    calendar = load_validation_calendar()
    cycle = session.exec(
        select(ValidationCycle).where(ValidationCycle.cycle_key == calendar["cycle_key"])
    ).first()
    if cycle:
        cycle.label = calendar["cycle_label"]
        cycle.general_review_day = calendar["general_review_day"]
        session.add(cycle)
        session.commit()
        return

    session.add(
        ValidationCycle(
            cycle_key=calendar["cycle_key"],
            label=calendar["cycle_label"],
            general_review_day=calendar["general_review_day"],
        )
    )
    session.commit()


def seed_database(session: Session) -> None:
    _seed_default_user(session)
    _seed_admin_user(session)
    _seed_validation_cycle(session)

    if _import_metadata_database(session):
        return

    existing_exam = session.exec(select(Exam)).first()
    if existing_exam:
        _normalize_simulated_metadata(session)
        return

    now = datetime.utcnow()

    rows = [
        {
            "patient": ("Maria Oliveira", 58, "Feminino", 68.0, 1.62),
            "exam_code": "A03B5F",
            "days_ago": 0,
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Ritmo sinusal", False)],
        },
        {
            "patient": ("Carlos Mendes", 44, "Masculino", 82.0, 1.78),
            "exam_code": "43DA34",
            "days_ago": 1,
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Sem alterações significativas", False)],
        },
        {
            "patient": ("Ana Beatriz Souza", 35, "Feminino", 61.5, 1.67),
            "exam_code": "A9FF32",
            "days_ago": 2,
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "alterado",
            "diagnoses": [("Taquicardia sinusal", True)],
        },
        {
            "patient": ("Roberto Lima", 67, "Masculino", 88.4, 1.72),
            "exam_code": "F3B234",
            "days_ago": 0,
            "exam_type": "ECG repouso",
            "status_validation": "nao_validado",
            "review_result": None,
            "diagnoses": [],
        },
        {
            "patient": ("Helena Costa", 72, "Feminino", 70.2, 1.59),
            "exam_code": "C91A77",
            "days_ago": 0,
            "exam_type": "ECG repouso",
            "status_validation": "em_validacao",
            "review_result": None,
            "diagnoses": [("Possível alteração inespecífica", True)],
        },
        {
            "patient": ("Paulo Henrique", 51, "Masculino", 91.0, 1.81),
            "exam_code": "B18C22",
            "days_ago": 3,
            "exam_type": "ECG repouso",
            "status_validation": "nao_validado",
            "review_result": None,
            "diagnoses": [],
        },
        {
            "patient": ("Luciana Rocha", 63, "Feminino", 74.0, 1.65),
            "exam_code": "D77E90",
            "days_ago": 4,
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "alterado",
            "diagnoses": [("Extrassístoles ventriculares", True)],
        },
        {
            "patient": ("Marcos Vinicius", 29, "Masculino", 76.8, 1.75),
            "exam_code": "E10F45",
            "days_ago": 5,
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Ritmo sinusal", False)],
        },
        {
            "patient": ("Patricia Almeida", 49, "Feminino", 65.3, 1.61),
            "exam_code": "AA1209",
            "days_ago": 1,
            "exam_type": "ECG repouso",
            "status_validation": "em_validacao",
            "review_result": None,
            "diagnoses": [("Bradicardia sinusal", True)],
        },
        {
            "patient": ("Eduardo Nunes", 56, "Masculino", 85.5, 1.74),
            "exam_code": "BB4421",
            "days_ago": 2,
            "exam_type": "ECG repouso",
            "status_validation": "nao_validado",
            "review_result": None,
            "diagnoses": [],
        },
        {
            "patient": ("Renata Ferreira", 40, "Feminino", 59.0, 1.64),
            "exam_code": "C0DE15",
            "days_ago": 6,
            "exam_type": "ECG repouso",
            "status_validation": "valido",
            "review_result": "sem_alteracao",
            "diagnoses": [("Intervalos dentro da normalidade", False)],
        },
        {
            "patient": ("João Batista", 69, "Masculino", 79.7, 1.69),
            "exam_code": "FF210A",
            "days_ago": 7,
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
            category="ECG",
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
