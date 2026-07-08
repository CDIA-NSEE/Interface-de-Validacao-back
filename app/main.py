from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from sqlalchemy import desc
from sqlmodel import Session, select

from app.auth import authenticate_user, create_access_token, get_current_active_user
from app.config_source import (
    active_validation_context,
    email_domain_allowed,
    load_support_contact,
    normalize_text,
    standardize_diagnosis,
)
from app.database import (
    create_db_and_tables,
    engine,
    get_session,
    reset_db_and_tables,
    should_reset_database_on_startup,
)
from app.metadata_source import load_diagnosis_options, load_metadata_image
from app.models import Diagnosis, DiagnosisValidation, Exam, Patient, Review, User
from app.schemas import (
    DiagnosisCreate,
    DiagnosisReview,
    ExamValidate,
    LoginRequest,
    StatusUpdate,
    TokenResponse,
    UserRead,
)
from app.seed import seed_database


VALID_STATUSES = {"nao_validado", "em_validacao", "valido"}
VALID_REVIEW_RESULTS = {"sem_alteracao", "alterado"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    if should_reset_database_on_startup():
        reset_db_and_tables()
    else:
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
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
    ],
    allow_origin_regex=r"^http://192\.168\.\d{1,3}\.\d{1,3}:517[3-5]$",
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


def _same_standard_text(left: str | None, right: str | None) -> bool:
    return normalize_text(left) == normalize_text(right)


def _latest_standard_validation(
    session: Session,
    exam_id: int,
    standard_text: str,
    cycle_key: str,
) -> DiagnosisValidation | None:
    validations = session.exec(
        select(DiagnosisValidation)
        .where(DiagnosisValidation.exam_id == exam_id)
        .where(DiagnosisValidation.cycle_key == cycle_key)
        .order_by(desc(DiagnosisValidation.updated_at))
    ).all()
    normalized_standard_text = normalize_text(standard_text)
    return next(
        (
            validation
            for validation in validations
            if normalize_text(validation.standard_text) == normalized_standard_text
        ),
        None,
    )


def _diagnosis_payload(
    diagnosis: Diagnosis,
    session: Session | None = None,
    context: dict | None = None,
) -> dict:
    context = context or active_validation_context()
    standard_text = standardize_diagnosis(diagnosis.name)
    is_grouped = not _same_standard_text(standard_text, diagnosis.name)
    validation = (
        _latest_standard_validation(session, diagnosis.exam_id, standard_text, context["cycle_key"])
        if session
        else None
    )
    active_standard_diagnosis = context.get("active_standard_diagnosis")
    validation_status = validation.review_status if validation else diagnosis.review_status

    return {
        "id": diagnosis.id,
        "exam_id": diagnosis.exam_id,
        "name": diagnosis.name,
        "standard_text": standard_text,
        "original_text": diagnosis.name,
        "is_grouped": is_grouped,
        "source": diagnosis.source,
        "review_status": validation_status,
        "legacy_review_status": diagnosis.review_status,
        "validation_status": validation_status,
        "validation_id": validation.id if validation else None,
        "validated_at": validation.updated_at if validation else None,
        "daily_required": bool(
            diagnosis.source == "original"
            and active_standard_diagnosis
            and _same_standard_text(standard_text, active_standard_diagnosis)
        ),
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


def _exam_payload(
    session: Session,
    exam: Exam,
    include_details: bool = False,
    context: dict | None = None,
) -> dict:
    context = context or active_validation_context()
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
        "image_endpoint": f"/exams/{exam.id}/image",
        "comments": exam.comments,
        "source_notes": exam.source_notes,
        "created_at": exam.created_at,
        "updated_at": exam.updated_at,
        "started_at": started_at,
        "completed_at": completed_at,
        "patient": _patient_payload(patient),
        "validation_context": context,
    }

    if include_details:
        diagnoses = session.exec(
            select(Diagnosis)
            .where(Diagnosis.exam_id == exam.id)
            .order_by(Diagnosis.created_at)
        ).all()
        payload["diagnoses"] = [
            _diagnosis_payload(diagnosis, session=session, context=context)
            for diagnosis in diagnoses
        ]

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


def _context_payload() -> dict:
    context = active_validation_context()
    return {
        **context,
        "support_contact": load_support_contact(),
    }


def _original_diagnoses(session: Session, exam_id: int) -> list[Diagnosis]:
    return session.exec(
        select(Diagnosis)
        .where(Diagnosis.exam_id == exam_id)
        .where(Diagnosis.source == "original")
        .order_by(Diagnosis.created_at)
    ).all()


def _required_diagnoses_for_context(
    session: Session,
    exam: Exam,
    context: dict,
) -> list[Diagnosis]:
    active_standard_diagnosis = context.get("active_standard_diagnosis")
    if not active_standard_diagnosis:
        return []

    return [
        diagnosis
        for diagnosis in _original_diagnoses(session, exam.id)
        if _same_standard_text(standardize_diagnosis(diagnosis.name), active_standard_diagnosis)
    ]


def _exam_pending_for_context(session: Session, exam: Exam, context: dict) -> bool:
    if not context.get("is_configured"):
        return False

    if context.get("is_general_review_day"):
        return exam.status_validation != "valido"

    required_diagnoses = _required_diagnoses_for_context(session, exam, context)
    if not required_diagnoses:
        return False

    active_standard_diagnosis = standardize_diagnosis(required_diagnoses[0].name)
    validation = _latest_standard_validation(
        session,
        exam.id,
        active_standard_diagnosis,
        context["cycle_key"],
    )
    return validation is None


def _validation_queue(session: Session, context: dict) -> list[Exam]:
    if not context.get("is_configured"):
        return []

    exams = session.exec(select(Exam).order_by(desc(Exam.exam_date), desc(Exam.created_at))).all()
    pending_exams = [exam for exam in exams if _exam_pending_for_context(session, exam, context)]
    return sorted(
        pending_exams,
        key=lambda exam: (
            {"em_validacao": 0, "nao_validado": 1}.get(exam.status_validation, 2),
            exam.created_at,
        ),
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.username if "@" in user.username else None,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: Session = Depends(get_session)) -> TokenResponse:
    identifier = payload.identifier
    if not identifier or not payload.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Informe e-mail/usuario e senha.",
        )

    user = authenticate_user(session, identifier, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if user.role != "admin" and not email_domain_allowed(user.username):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-mail fora do dominio institucional BP configurado.",
        )

    return TokenResponse(
        access_token=create_access_token(user.username),
        user=_user_read(user),
    )


@app.get("/auth/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> UserRead:
    return _user_read(current_user)


@app.get("/validation/context")
def validation_context(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return _context_payload()


@app.get("/validation/queue")
def validation_queue(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    context = active_validation_context()
    queue = _validation_queue(session, context)
    return {
        "context": context,
        "items": [_exam_payload(session, exam, include_details=False, context=context) for exam in queue],
        "total": len(queue),
    }


@app.get("/validation/next")
def validation_next(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    context = active_validation_context()
    queue = _validation_queue(session, context)
    next_exam = queue[0] if queue else None
    return {
        "context": context,
        "exam": _exam_payload(session, next_exam, include_details=True, context=context)
        if next_exam
        else None,
    }


@app.post("/validation/diagnoses/{diagnosis_id}/review")
def review_validation_diagnosis(
    diagnosis_id: int,
    payload: DiagnosisReview,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    diagnosis = session.get(Diagnosis, diagnosis_id)
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostico nao encontrado.",
        )

    exam = _get_exam_or_404(session, diagnosis.exam_id)
    context = active_validation_context()
    standard_text = standardize_diagnosis(diagnosis.name)
    now = datetime.utcnow()
    validation = _latest_standard_validation(
        session,
        exam.id,
        standard_text,
        context["cycle_key"],
    )

    if validation:
        validation.diagnosis_id = diagnosis.id
        validation.review_status = payload.review_status
        validation.reviewer_id = current_user.id
        validation.reviewer_name = current_user.full_name
        validation.notes = payload.notes
        validation.day_index = context.get("day_index")
        validation.updated_at = now
    else:
        validation = DiagnosisValidation(
            exam_id=exam.id,
            diagnosis_id=diagnosis.id,
            standard_text=standard_text,
            cycle_key=context["cycle_key"],
            day_index=context.get("day_index"),
            review_status=payload.review_status,
            reviewer_id=current_user.id,
            reviewer_name=current_user.full_name,
            notes=payload.notes,
            created_at=now,
            updated_at=now,
        )

    diagnosis.review_status = payload.review_status
    status_before = exam.status_validation
    if exam.status_validation == "nao_validado":
        exam.status_validation = "em_validacao"
        session.add(
            Review(
                exam_id=exam.id,
                doctor_name=current_user.full_name,
                status_before=status_before,
                status_after="em_validacao",
                created_at=now,
            )
        )

    exam.updated_at = now
    session.add(validation)
    session.add(diagnosis)
    session.add(exam)
    session.commit()
    session.refresh(exam)
    return _exam_payload(session, exam, include_details=True, context=context)


@app.get("/support/contact")
def support_contact(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return load_support_contact()


@app.get("/exams")
def list_exams(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    category: Optional[str] = None,
    exam_type: Optional[str] = None,
    source: Optional[str] = None,
    review_result: Optional[str] = None,
    search: Optional[str] = None,
    current_user: User = Depends(get_current_active_user),
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
def get_exam(
    exam_id: int,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    exam = _get_exam_or_404(session, exam_id)
    return _exam_payload(session, exam, include_details=True)


@app.get("/exams/{exam_id}/image", response_model=None)
def get_exam_image(
    exam_id: int,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
):
    exam = _get_exam_or_404(session, exam_id)
    image = load_metadata_image(exam.metadata_id)
    if image:
        return Response(
            content=image["content"],
            media_type=image["media_type"],
            headers={"Cache-Control": "private, max-age=3600"},
        )
    return RedirectResponse(url=exam.image_url or "/sample-ecg.svg")


@app.get("/diagnosis-options")
def diagnosis_options(current_user: User = Depends(get_current_active_user)) -> list[str]:
    return load_diagnosis_options()


@app.patch("/exams/{exam_id}/status")
def update_exam_status(
    exam_id: int,
    payload: StatusUpdate,
    current_user: User = Depends(get_current_active_user),
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
                doctor_name=current_user.full_name,
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
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    _get_exam_or_404(session, exam_id)
    requested_diagnosis_name = payload.name.strip()
    if not requested_diagnosis_name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="O nome do diagnóstico é obrigatório.",
        )

    allowed_names = set(load_diagnosis_options())
    diagnosis_name = standardize_diagnosis(requested_diagnosis_name)
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
    return _diagnosis_payload(diagnosis, session=session)


@app.patch("/exams/{exam_id}/diagnoses/{diagnosis_id}/review")
def review_diagnosis(
    exam_id: int,
    diagnosis_id: int,
    payload: DiagnosisReview,
    current_user: User = Depends(get_current_active_user),
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
    return _diagnosis_payload(diagnosis, session=session)


@app.delete("/exams/{exam_id}/diagnoses/{diagnosis_id}")
def remove_diagnosis(
    exam_id: int,
    diagnosis_id: int,
    current_user: User = Depends(get_current_active_user),
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
    current_user: User = Depends(get_current_active_user),
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
        doctor_name=current_user.full_name,
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
def dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
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
