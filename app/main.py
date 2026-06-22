from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import desc
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine, get_session
from app.metadata_source import load_diagnosis_options
from app.models import Diagnosis, Exam, Patient, Review
from app.schemas import DiagnosisCreate, DiagnosisReview, ExamValidate, StatusUpdate
from app.seed import seed_database


VALID_STATUSES = {"nao_validado", "em_validacao", "valido"}
VALID_REVIEW_RESULTS = {"sem_alteracao", "alterado"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        seed_database(session)
    yield


app = FastAPI(
    title="ECG Review Platform API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _patient_payload(patient: Patient) -> dict:
    return {
        "id": patient.id,
        "birth_date": patient.birth_date,
        "age": patient.age or None,
        "sex": patient.sex or None,
        "weight": patient.weight or None,
        "height": patient.height or None,
        "bmi": patient.bmi or None,
    }


def _diagnosis_payload(diagnosis: Diagnosis) -> dict:
    return {
        "id": diagnosis.id,
        "exam_id": diagnosis.exam_id,
        "name": diagnosis.name,
        "source": diagnosis.source,
        "review_status": diagnosis.review_status,
        "is_abnormal": diagnosis.is_abnormal,
        "region_x": diagnosis.region_x,
        "region_y": diagnosis.region_y,
        "region_width": diagnosis.region_width,
        "region_height": diagnosis.region_height,
        "created_at": diagnosis.created_at,
    }


def _review_timestamps(session: Session, exam: Exam) -> tuple[Optional[datetime], Optional[datetime]]:
    if exam.status_validation == "nao_validado":
        return None, None

    reviews = session.exec(
        select(Review).where(Review.exam_id == exam.id).order_by(Review.created_at)
    ).all()

    if exam.status_validation == "em_validacao":
        started_at = next(
            (review.created_at for review in reviews if review.status_after == "em_validacao"),
            None,
        )
        return started_at, None

    completed_at = next(
        (review.created_at for review in reversed(reviews) if review.status_after == "valido"),
        None,
    )
    return None, completed_at


def _exam_payload(session: Session, exam: Exam, include_details: bool = False) -> dict:
    patient = session.get(Patient, exam.patient_id)
    started_at, completed_at = _review_timestamps(session, exam)
    payload = {
        "id": exam.id,
        "exam_code": exam.exam_code,
        "exam_date": exam.exam_date,
        "exam_time": exam.exam_time,
        "category": exam.category,
        "exam_type": exam.exam_type,
        "status_validation": exam.status_validation,
        "review_result": exam.review_result if exam.status_validation == "valido" else None,
        "image_url": exam.image_url,
        "comments": exam.comments,
        "source_notes": exam.source_notes,
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "patient": _patient_payload(patient),
    }

    if include_details:
        diagnoses = session.exec(
            select(Diagnosis)
            .where(Diagnosis.exam_id == exam.id)
            .order_by(Diagnosis.created_at)
        ).all()
        payload["diagnoses"] = [_diagnosis_payload(diagnosis) for diagnosis in diagnoses]

    return payload


def _get_exam_or_404(session: Session, exam_id: int) -> Exam:
    exam = session.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exame não encontrado.")
    return exam


def _validate_status(status_validation: str) -> None:
    if status_validation not in VALID_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="status_validation inválido.",
        )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/exams")
def list_exams(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    category: Optional[str] = None,
    exam_type: Optional[str] = None,
    source: Optional[str] = None,
    review_result: Optional[str] = None,
    search: Optional[str] = None,
    session: Session = Depends(get_session),
) -> list[dict]:
    if status_filter:
        _validate_status(status_filter)

    if review_result and review_result not in VALID_REVIEW_RESULTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="review_result inválido.",
        )

    if source and source not in {"pending", "reviewed", "all"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source deve ser pending, reviewed ou all.",
        )

    exams = session.exec(select(Exam).order_by(desc(Exam.exam_date), desc(Exam.created_at))).all()
    normalized_search = search.strip().lower() if search else None
    results = []

    for exam in exams:
        if status_filter and exam.status_validation != status_filter:
            continue
        if category and exam.category != category:
            continue
        if exam_type and exam.exam_type != exam_type:
            continue
        if review_result and exam.review_result != review_result:
            continue
        if source == "pending" and exam.status_validation == "valido":
            continue
        if source == "reviewed" and exam.status_validation != "valido":
            continue
        if normalized_search:
            haystack = f"{exam.id} {exam.exam_code}".lower()
            if normalized_search not in haystack:
                continue

        results.append(_exam_payload(session, exam))

    return results


@app.get("/exams/{exam_id}")
def get_exam(exam_id: int, session: Session = Depends(get_session)) -> dict:
    exam = _get_exam_or_404(session, exam_id)
    return _exam_payload(session, exam, include_details=True)


@app.get("/diagnosis-options")
def diagnosis_options() -> list[str]:
    return load_diagnosis_options()


@app.patch("/exams/{exam_id}/status")
def update_exam_status(
    exam_id: int,
    payload: StatusUpdate,
    session: Session = Depends(get_session),
) -> dict:
    _validate_status(payload.status_validation)
    if payload.status_validation == "valido":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Use /validate para validar um exame e informar review_result.",
        )

    exam = _get_exam_or_404(session, exam_id)
    status_before = exam.status_validation
    exam.status_validation = payload.status_validation
    exam.review_result = None
    exam.updated_at = datetime.utcnow()
    session.add(exam)
    if status_before != payload.status_validation:
        session.add(
            Review(
                exam_id=exam.id,
                doctor_name="Dr. João",
                status_before=status_before,
                status_after=payload.status_validation,
                created_at=exam.updated_at,
            )
        )
    session.commit()
    session.refresh(exam)
    return _exam_payload(session, exam, include_details=True)


@app.post("/exams/{exam_id}/diagnoses", status_code=status.HTTP_201_CREATED)
def add_diagnosis(
    exam_id: int,
    payload: DiagnosisCreate,
    session: Session = Depends(get_session),
) -> dict:
    _get_exam_or_404(session, exam_id)
    diagnosis_name = payload.name.strip()
    if not diagnosis_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do diagnóstico é obrigatório.",
        )

    allowed_names = set(load_diagnosis_options())
    if diagnosis_name not in allowed_names:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selecione um diagnóstico padronizado.",
        )

    diagnosis = Diagnosis(
        exam_id=exam_id,
        name=diagnosis_name,
        source="doctor_added",
        review_status="confirmed",
        is_abnormal=payload.is_abnormal,
        region_x=payload.region_x,
        region_y=payload.region_y,
        region_width=payload.region_width,
        region_height=payload.region_height,
    )
    session.add(diagnosis)

    exam = _get_exam_or_404(session, exam_id)
    exam.updated_at = datetime.utcnow()
    session.add(exam)

    session.commit()
    session.refresh(diagnosis)
    return _diagnosis_payload(diagnosis)


@app.patch("/exams/{exam_id}/diagnoses/{diagnosis_id}/review")
def review_diagnosis(
    exam_id: int,
    diagnosis_id: int,
    payload: DiagnosisReview,
    session: Session = Depends(get_session),
) -> dict:
    exam = _get_exam_or_404(session, exam_id)
    diagnosis = session.get(Diagnosis, diagnosis_id)
    if not diagnosis or diagnosis.exam_id != exam_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnóstico não encontrado.",
        )
    if diagnosis.source != "original":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Somente diagnósticos originais podem ser confirmados ou rejeitados.",
        )

    diagnosis.review_status = payload.review_status
    exam.updated_at = datetime.utcnow()
    session.add(diagnosis)
    session.add(exam)
    session.commit()
    session.refresh(diagnosis)
    return _diagnosis_payload(diagnosis)


@app.delete("/exams/{exam_id}/diagnoses/{diagnosis_id}")
def remove_diagnosis(
    exam_id: int,
    diagnosis_id: int,
    session: Session = Depends(get_session),
) -> dict:
    _get_exam_or_404(session, exam_id)
    diagnosis = session.get(Diagnosis, diagnosis_id)
    if not diagnosis or diagnosis.exam_id != exam_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnóstico não encontrado.",
        )

    if diagnosis.source == "original":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O diagnóstico original do ECG não pode ser removido.",
        )

    session.delete(diagnosis)

    exam = _get_exam_or_404(session, exam_id)
    exam.updated_at = datetime.utcnow()
    session.add(exam)

    session.commit()
    return {"deleted": diagnosis_id}


@app.post("/exams/{exam_id}/validate")
def validate_exam(
    exam_id: int,
    payload: ExamValidate,
    session: Session = Depends(get_session),
) -> dict:
    if payload.review_result not in VALID_REVIEW_RESULTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="review_result inválido.",
        )

    exam = _get_exam_or_404(session, exam_id)
    status_before = exam.status_validation
    now = datetime.utcnow()

    exam.status_validation = "valido"
    exam.review_result = payload.review_result
    exam.updated_at = now
    session.add(exam)

    review = Review(
        exam_id=exam.id,
        doctor_name=payload.doctor_name or "Dr. João",
        status_before=status_before,
        status_after="valido",
        review_result=payload.review_result,
        notes=payload.notes,
        created_at=now,
    )
    session.add(review)
    session.commit()
    session.refresh(exam)
    return _exam_payload(session, exam, include_details=True)


@app.get("/dashboard/stats")
def dashboard_stats(session: Session = Depends(get_session)) -> dict:
    exams = session.exec(select(Exam)).all()
    reviews = session.exec(select(Review).where(Review.status_after == "valido")).all()
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    return {
        "reviewed_today": sum(1 for review in reviews if review.created_at >= today_start),
        "reviewed_week": sum(1 for review in reviews if review.created_at >= week_start),
        "pending_total": sum(1 for exam in exams if exam.status_validation == "nao_validado"),
        "in_validation_total": sum(1 for exam in exams if exam.status_validation == "em_validacao"),
        "reviewed_total": sum(1 for exam in exams if exam.status_validation == "valido"),
        "valid_without_change": sum(
            1
            for exam in exams
            if exam.status_validation == "valido" and exam.review_result == "sem_alteracao"
        ),
        "valid_with_change": sum(
            1
            for exam in exams
            if exam.status_validation == "valido" and exam.review_result == "alterado"
        ),
    }
