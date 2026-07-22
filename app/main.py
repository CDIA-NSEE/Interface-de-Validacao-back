from contextlib import asynccontextmanager
from datetime import datetime, timedelta
import os
import re
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from mangum import Mangum
from sqlalchemy import desc, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.api_docs import (
    AUTH_BAD_REQUEST_RESPONSES,
    AUTH_MUTATION_RESPONSES,
    AUTH_NOT_FOUND_RESPONSES,
    AUTH_RESPONSES,
    OPENAPI_TAGS,
    configure_openapi,
)
from app.auth import get_current_active_user
from app.config_source import (
    active_validation_context,
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
from app.models import (
    Diagnosis,
    DiagnosisRegion,
    DiagnosisValidation,
    Exam,
    ExamDraft,
    Patient,
    Review,
    User,
)
from app.schemas import (
    DiagnosisCreate,
    DiagnosisRegionPayload,
    DiagnosisReview,
    ErrorResponse,
    ExamDraftUpdate,
    ExamValidate,
    HealthResponse,
    StatusUpdate,
    UserRead,
)
from app.seed import seed_database


VALID_STATUSES = {"nao_validado", "em_validacao", "valido"}
VALID_REVIEW_RESULTS = {"sem_alteracao", "alterado"}
VALID_QUEUE_STATES = {"all", "start", "validated", "completed"}
VALID_DECISION_FILTERS = {"confirmed", "rejected"}
VALID_REGION_FILTERS = {"with_region", "without_region"}
DEFAULT_CORS_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:5175",
    "http://127.0.0.1:5175",
]
DEFAULT_CORS_ORIGIN_REGEX = r"^https://.*\.amplifyapp\.com$"
PUBLIC_SYSTEM_PATHS = {
    "/docs",
    "/docs/oauth2-redirect",
    "/health",
    "/openapi.json",
    "/redoc",
}


def _split_csv_env(value: str | None) -> list[str]:
    if value is None:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _cors_origins() -> list[str]:
    configured_origins = os.getenv("BACKEND_CORS_ORIGINS")
    if configured_origins is None:
        return DEFAULT_CORS_ORIGINS
    return _split_csv_env(configured_origins)


def _cors_origin_regex() -> str | None:
    configured_regex = os.getenv("BACKEND_CORS_ORIGIN_REGEX")
    if configured_regex is None:
        return DEFAULT_CORS_ORIGIN_REGEX
    return configured_regex.strip() or None


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
    description=(
        "API da Plataforma de Revisao de ECG para consulta de exames, "
        "validacao medica de diagnosticos e marcacao de regioes. "
        "Endpoints protegidos aceitam access tokens JWT do Amazon Cognito."
    ),
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    swagger_ui_parameters={"persistAuthorization": True},
)

configure_openapi(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=_cors_origin_regex(),
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


def _diagnosis_regions(session: Session, diagnosis: Diagnosis) -> list[DiagnosisRegion]:
    return session.exec(
        select(DiagnosisRegion)
        .where(DiagnosisRegion.diagnosis_id == diagnosis.id)
        .order_by(DiagnosisRegion.created_at, DiagnosisRegion.id)
    ).all()


def _legacy_region_payload(diagnosis: Diagnosis) -> dict | None:
    if diagnosis.region_width and diagnosis.region_height:
        return {
            "id": None,
            "x": diagnosis.region_x,
            "y": diagnosis.region_y,
            "width": diagnosis.region_width,
            "height": diagnosis.region_height,
            "created_at": diagnosis.created_at,
            "legacy": True,
        }
    return None


def _region_payload(region: DiagnosisRegion) -> dict:
    return {
        "id": region.id,
        "x": region.x,
        "y": region.y,
        "width": region.width,
        "height": region.height,
        "created_at": region.created_at,
        "legacy": False,
    }


def _diagnosis_region_payloads(session: Session | None, diagnosis: Diagnosis) -> list[dict]:
    if not session:
        legacy_region = _legacy_region_payload(diagnosis)
        return [legacy_region] if legacy_region else []

    regions = [_region_payload(region) for region in _diagnosis_regions(session, diagnosis)]
    if regions:
        return regions

    legacy_region = _legacy_region_payload(diagnosis)
    return [legacy_region] if legacy_region else []


def _diagnosis_requires_region(standard_text: str | None, original_text: str | None) -> bool:
    normalized_values = [normalize_text(standard_text), normalize_text(original_text)]
    for normalized_text in normalized_values:
        if "INFARTO" in normalized_text:
            return True

        tokens = re.findall(r"[A-Z0-9]+", normalized_text)
        if any(token == "IAM" or token.startswith("IAM") for token in tokens):
            return True

    return False


def _validate_region_payload(payload: DiagnosisRegionPayload) -> None:
    values = {
        "x": payload.x,
        "y": payload.y,
        "width": payload.width,
        "height": payload.height,
    }
    if any(value < 0 or value > 100 for value in values.values()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="As coordenadas da area devem estar entre 0 e 100.",
        )
    if payload.width <= 0 or payload.height <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A area selecionada deve ter largura e altura validas.",
        )
    if payload.x + payload.width > 100 or payload.y + payload.height > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A area selecionada deve ficar dentro da imagem do ECG.",
        )


def _sync_legacy_region_fields(session: Session, diagnosis: Diagnosis) -> None:
    first_region = session.exec(
        select(DiagnosisRegion)
        .where(DiagnosisRegion.diagnosis_id == diagnosis.id)
        .order_by(DiagnosisRegion.created_at, DiagnosisRegion.id)
    ).first()

    if first_region:
        diagnosis.region_x = first_region.x
        diagnosis.region_y = first_region.y
        diagnosis.region_width = first_region.width
        diagnosis.region_height = first_region.height
    else:
        diagnosis.region_x = None
        diagnosis.region_y = None
        diagnosis.region_width = None
        diagnosis.region_height = None


def _region_input_from_diagnosis_payload(payload: DiagnosisCreate) -> DiagnosisRegionPayload | None:
    if (
        payload.region_x is None
        or payload.region_y is None
        or payload.region_width is None
        or payload.region_height is None
    ):
        return None

    return DiagnosisRegionPayload(
        x=payload.region_x,
        y=payload.region_y,
        width=payload.region_width,
        height=payload.region_height,
    )


def _effective_review_status(session: Session, diagnosis: Diagnosis, context: dict | None = None) -> str:
    context = context or active_validation_context()
    standard_text = standardize_diagnosis(diagnosis.name)
    validation = _latest_standard_validation(session, diagnosis.exam_id, standard_text, context["cycle_key"])
    return validation.review_status if validation else diagnosis.review_status


def _ensure_region_before_confirm(session: Session, diagnosis: Diagnosis) -> None:
    standard_text = standardize_diagnosis(diagnosis.name)
    regions = _diagnosis_region_payloads(session, diagnosis)
    if _diagnosis_requires_region(standard_text, diagnosis.name) and not regions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Marque ao menos uma area do ECG antes de confirmar um diagnostico de infarto.",
        )


def _diagnosis_payload(
    diagnosis: Diagnosis,
    session: Session | None = None,
    context: dict | None = None,
) -> dict:
    context = context or active_validation_context()
    standard_text = standardize_diagnosis(diagnosis.name)
    is_grouped = not _same_standard_text(standard_text, diagnosis.name)
    regions = _diagnosis_region_payloads(session, diagnosis)
    requires_region = _diagnosis_requires_region(standard_text, diagnosis.name)
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
        "regions": regions,
        "regions_count": len(regions),
        "requires_region": requires_region,
        "region_required_missing": bool(requires_region and not regions),
        "source": diagnosis.source,
        "review_status": validation_status,
        "legacy_review_status": diagnosis.review_status,
        "validation_status": validation_status,
        "validation_id": validation.id if validation else None,
        "validated_at": validation.updated_at if validation else None,
        "review_notes": validation.notes if validation and validation.notes else None,
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


def _exam_draft_for_user(session: Session, exam_id: int, reviewer_id: int) -> ExamDraft | None:
    return session.exec(
        select(ExamDraft)
        .where(ExamDraft.exam_id == exam_id)
        .where(ExamDraft.reviewer_id == reviewer_id)
    ).first()


def _exam_payload(
    session: Session,
    exam: Exam,
    include_details: bool = False,
    context: dict | None = None,
    current_user: User | None = None,
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
        "queue_state": _exam_queue_state(session, exam, context),
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

    if current_user and current_user.id is not None:
        draft = _exam_draft_for_user(session, exam.id, current_user.id)
        payload["draft_notes"] = draft.notes if draft else None

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


def _get_diagnosis_or_404(session: Session, diagnosis_id: int) -> Diagnosis:
    diagnosis = session.get(Diagnosis, diagnosis_id)
    if not diagnosis:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diagnostico nao encontrado.",
        )
    return diagnosis


def _get_region_or_404(session: Session, diagnosis_id: int, region_id: int) -> DiagnosisRegion:
    region = session.get(DiagnosisRegion, region_id)
    if not region or region.diagnosis_id != diagnosis_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Area do diagnostico nao encontrada.",
        )
    return region


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


def _validation_progress(session: Session, context: dict, queue: list[Exam]) -> dict:
    if not context.get("is_configured"):
        return {
            "total": 0,
            "remaining": 0,
            "completed": 0,
            "percent": 0,
        }

    if context.get("is_general_review_day"):
        exams = session.exec(select(Exam)).all()
        total = len(exams)
        remaining = len(queue)
    else:
        active_standard_diagnosis = context.get("active_standard_diagnosis")
        if not active_standard_diagnosis:
            total = 0
            remaining = 0
        else:
            exams = session.exec(select(Exam)).all()
            total = 0
            remaining = 0
            for exam in exams:
                required_diagnoses = _required_diagnoses_for_context(session, exam, context)
                if not required_diagnoses:
                    continue

                total += 1
                standard_text = standardize_diagnosis(required_diagnoses[0].name)
                validation = _latest_standard_validation(
                    session,
                    exam.id,
                    standard_text,
                    context["cycle_key"],
                )
                if validation is None:
                    remaining += 1

    completed = max(total - remaining, 0)
    percent = round((completed / total) * 100) if total else 0
    return {
        "total": total,
        "remaining": remaining,
        "completed": completed,
        "percent": percent,
    }


def _diagnoses_for_queue_filters(session: Session, exam: Exam, context: dict) -> list[Diagnosis]:
    if context.get("is_configured") and context.get("active_standard_diagnosis"):
        return _required_diagnoses_for_context(session, exam, context)
    return _original_diagnoses(session, exam.id)


def _exam_has_context_validation(session: Session, exam: Exam, context: dict) -> bool:
    required_diagnoses = _required_diagnoses_for_context(session, exam, context)
    if not required_diagnoses:
        return False

    standard_text = standardize_diagnosis(required_diagnoses[0].name)
    validation = _latest_standard_validation(
        session,
        exam.id,
        standard_text,
        context["cycle_key"],
    )
    return validation is not None


def _exam_matches_queue_state(session: Session, exam: Exam, context: dict, queue_state: str | None) -> bool:
    if not queue_state or queue_state == "all":
        return True

    if queue_state == "completed":
        return exam.status_validation == "valido"

    if queue_state == "start":
        return _exam_pending_for_context(session, exam, context)

    if queue_state == "validated":
        return exam.status_validation != "valido" and _exam_has_context_validation(session, exam, context)

    return True


def _exam_queue_state(session: Session, exam: Exam, context: dict) -> str:
    if exam.status_validation == "valido":
        return "completed"

    if _exam_has_context_validation(session, exam, context):
        return "validated"

    if _exam_pending_for_context(session, exam, context):
        return "start"

    return "start"


def _exam_matches_decision_region(
    session: Session,
    exam: Exam,
    context: dict,
    decision: str | None,
    region: str | None,
) -> bool:
    if not decision and not region:
        return True

    diagnoses = _diagnoses_for_queue_filters(session, exam, context)
    for diagnosis in diagnoses:
        diagnosis_status = _effective_review_status(session, diagnosis, context)
        regions_count = len(_diagnosis_region_payloads(session, diagnosis))

        if decision and diagnosis_status != decision:
            continue
        if region == "with_region" and regions_count == 0:
            continue
        if region == "without_region" and regions_count > 0:
            continue

        return True

    return False


def _queue_state_counts(session: Session, exams: list[Exam], context: dict) -> dict:
    return {
        "all": len(exams),
        "start": sum(1 for exam in exams if _exam_matches_queue_state(session, exam, context, "start")),
        "validated": sum(1 for exam in exams if _exam_matches_queue_state(session, exam, context, "validated")),
        "completed": sum(1 for exam in exams if _exam_matches_queue_state(session, exam, context, "completed")),
    }


def _cross_filter_counts(session: Session, exams: list[Exam], context: dict) -> dict:
    return {
        "decision": {
            "confirmed": sum(
                1
                for exam in exams
                if _exam_matches_decision_region(session, exam, context, "confirmed", None)
            ),
            "rejected": sum(
                1
                for exam in exams
                if _exam_matches_decision_region(session, exam, context, "rejected", None)
            ),
        },
        "region": {
            "with_region": sum(
                1
                for exam in exams
                if _exam_matches_decision_region(session, exam, context, None, "with_region")
            ),
            "without_region": sum(
                1
                for exam in exams
                if _exam_matches_decision_region(session, exam, context, None, "without_region")
            ),
        },
    }


def _database_connection_is_available() -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


@app.get(
    "/health",
    tags=["Sistema"],
    summary="Verificar disponibilidade da API",
    description="Confirma que a API esta acessivel e consegue consultar o banco de dados.",
    response_model=HealthResponse,
    responses={
        503: {
            "model": ErrorResponse,
            "description": "Banco de dados indisponivel.",
        }
    },
)
def health() -> HealthResponse:
    if not _database_connection_is_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Banco de dados indisponivel.",
        )
    return HealthResponse(status="ok", database="connected")


def _user_read(user: User) -> UserRead:
    return UserRead(
        id=user.id,
        username=user.username,
        email=user.username if "@" in user.username else None,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
    )


@app.get(
    "/auth/me",
    tags=["Autenticacao"],
    summary="Consultar usuario autenticado",
    description="Retorna o perfil local associado ao access token validado pelo Amazon Cognito.",
    response_model=UserRead,
    responses=AUTH_RESPONSES,
)
def read_current_user(current_user: User = Depends(get_current_active_user)) -> UserRead:
    return _user_read(current_user)


@app.get(
    "/validation/context",
    tags=["Validacao"],
    summary="Consultar contexto de validacao",
    description="Retorna o dia ativo, o diagnostico padronizado e os dados do ciclo atual.",
    responses=AUTH_RESPONSES,
)
def validation_context(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return _context_payload()


@app.get(
    "/validation/queue",
    tags=["Validacao"],
    summary="Consultar fila de validacao",
    description="Lista os exames pendentes do contexto ativo e o progresso consolidado da fila.",
    responses=AUTH_RESPONSES,
)
def validation_queue(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    context = active_validation_context()
    queue = _validation_queue(session, context)
    progress = _validation_progress(session, context, queue)
    return {
        "context": context,
        "items": [_exam_payload(session, exam, include_details=False, context=context) for exam in queue],
        "total": len(queue),
        "progress": progress,
    }


@app.get(
    "/validation/next",
    tags=["Validacao"],
    summary="Consultar proximo exame",
    description="Retorna o primeiro exame ainda pendente no contexto diario de validacao.",
    responses=AUTH_RESPONSES,
)
def validation_next(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    context = active_validation_context()
    queue = _validation_queue(session, context)
    next_exam = queue[0] if queue else None
    return {
        "context": context,
        "exam": _exam_payload(
            session,
            next_exam,
            include_details=True,
            context=context,
            current_user=current_user,
        )
        if next_exam
        else None,
    }


@app.post(
    "/validation/diagnoses/{diagnosis_id}/review",
    tags=["Validacao"],
    summary="Registrar decisao do ciclo",
    description="Confirma ou rejeita um diagnostico no ciclo ativo e atualiza a fila do exame.",
    responses=AUTH_MUTATION_RESPONSES,
)
def review_validation_diagnosis(
    diagnosis_id: int,
    payload: DiagnosisReview,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    diagnosis = _get_diagnosis_or_404(session, diagnosis_id)

    exam = _get_exam_or_404(session, diagnosis.exam_id)
    context = active_validation_context()
    standard_text = standardize_diagnosis(diagnosis.name)
    if payload.review_status == "confirmed":
        _ensure_region_before_confirm(session, diagnosis)

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
    return _exam_payload(
        session,
        exam,
        include_details=True,
        context=context,
        current_user=current_user,
    )


@app.get(
    "/support/contact",
    tags=["Suporte"],
    summary="Consultar contato de suporte",
    description="Retorna os canais de suporte configurados para a plataforma.",
    responses=AUTH_RESPONSES,
)
def support_contact(
    current_user: User = Depends(get_current_active_user),
) -> dict:
    return load_support_contact()


@app.get(
    "/exams",
    tags=["Exames"],
    summary="Listar exames",
    description="Lista os exames aplicando filtros de fila, decisao, mapeamento e busca por codigo.",
    responses=AUTH_BAD_REQUEST_RESPONSES,
)
def list_exams(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    category: Optional[str] = None,
    exam_type: Optional[str] = None,
    source: Optional[str] = None,
    review_result: Optional[str] = None,
    queue_state: Optional[str] = None,
    decision: Optional[str] = None,
    region: Optional[str] = None,
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

    if queue_state and queue_state not in VALID_QUEUE_STATES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="queue_state invalido.",
        )

    if decision and decision not in VALID_DECISION_FILTERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="decision deve ser confirmed ou rejected.",
        )

    if region and region not in VALID_REGION_FILTERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="region deve ser with_region ou without_region.",
        )

    context = active_validation_context()
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
        if not _exam_matches_queue_state(session, exam, context, queue_state):
            continue
        if not _exam_matches_decision_region(session, exam, context, decision, region):
            continue
        if normalized_search:
            haystack = f"{exam.id} {exam.exam_code}".lower()
            if normalized_search not in haystack:
                continue

        results.append(_exam_payload(session, exam, context=context))

    return results


@app.get(
    "/exams/{exam_id}",
    tags=["Exames"],
    summary="Consultar exame",
    description="Retorna metadados, paciente, diagnosticos, regioes e rascunho do usuario autenticado.",
    responses=AUTH_NOT_FOUND_RESPONSES,
)
def get_exam(
    exam_id: int,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    exam = _get_exam_or_404(session, exam_id)
    return _exam_payload(session, exam, include_details=True, current_user=current_user)


@app.put(
    "/exams/{exam_id}/draft",
    tags=["Exames"],
    summary="Salvar rascunho do exame",
    description="Cria, atualiza ou remove as observacoes em rascunho do usuario para o exame.",
    responses=AUTH_NOT_FOUND_RESPONSES,
)
def save_exam_draft(
    exam_id: int,
    payload: ExamDraftUpdate,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    exam = _get_exam_or_404(session, exam_id)
    notes = (payload.notes or "").strip() or None
    draft = _exam_draft_for_user(session, exam.id, current_user.id)

    if draft and notes is None:
        session.delete(draft)
    elif draft:
        draft.notes = notes
        draft.updated_at = datetime.utcnow()
        session.add(draft)
    elif notes is not None:
        session.add(
            ExamDraft(
                exam_id=exam.id,
                reviewer_id=current_user.id,
                notes=notes,
            )
        )

    session.commit()
    session.refresh(exam)
    return _exam_payload(session, exam, include_details=True, current_user=current_user)


@app.get(
    "/exams/{exam_id}/image",
    tags=["Exames"],
    summary="Obter imagem do ECG",
    description="Entrega a imagem real armazenada nos metadados ou redireciona para a imagem alternativa.",
    response_model=None,
    responses={
        **AUTH_NOT_FOUND_RESPONSES,
        200: {"description": "Conteudo binario da imagem do ECG."},
        307: {"description": "Redirecionamento para a imagem alternativa."},
    },
)
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


@app.get(
    "/diagnosis-options",
    tags=["Diagnosticos"],
    summary="Listar diagnosticos padronizados",
    description="Retorna as opcoes permitidas para diagnosticos adicionados pelo medico.",
    responses=AUTH_RESPONSES,
)
def diagnosis_options(current_user: User = Depends(get_current_active_user)) -> list[str]:
    return load_diagnosis_options()


@app.patch(
    "/exams/{exam_id}/status",
    tags=["Exames"],
    summary="Atualizar status do exame",
    description="Atualiza o estado operacional do exame sem executar sua validacao final.",
    responses=AUTH_MUTATION_RESPONSES,
)
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
    return _exam_payload(session, exam, include_details=True, current_user=current_user)


@app.post(
    "/exams/{exam_id}/diagnoses",
    tags=["Diagnosticos"],
    summary="Adicionar diagnostico medico",
    description="Adiciona ao exame um diagnostico padronizado informado pelo medico.",
    status_code=status.HTTP_201_CREATED,
    responses=AUTH_MUTATION_RESPONSES,
)
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

    region_payload = _region_input_from_diagnosis_payload(payload)
    if region_payload:
        _validate_region_payload(region_payload)

    requires_region = _diagnosis_requires_region(diagnosis_name, requested_diagnosis_name)
    initial_review_status = "confirmed" if region_payload or not requires_region else "pending"
    diagnosis = Diagnosis(
        exam_id=exam_id,
        name=diagnosis_name,
        source="doctor_added",
        review_status=initial_review_status,
        is_abnormal=payload.is_abnormal,
    )
    session.add(diagnosis)
    session.flush()

    if region_payload:
        session.add(
            DiagnosisRegion(
                exam_id=exam_id,
                diagnosis_id=diagnosis.id,
                x=region_payload.x,
                y=region_payload.y,
                width=region_payload.width,
                height=region_payload.height,
                created_by_id=current_user.id,
                created_by_name=current_user.full_name,
            )
        )
        _sync_legacy_region_fields(session, diagnosis)

    exam = _get_exam_or_404(session, exam_id)
    exam.updated_at = datetime.utcnow()
    session.add(exam)

    session.commit()
    session.refresh(diagnosis)
    return _diagnosis_payload(diagnosis, session=session)


@app.post(
    "/diagnoses/{diagnosis_id}/regions",
    tags=["Diagnosticos"],
    summary="Adicionar regiao ao diagnostico",
    description="Vincula ao diagnostico uma area percentual selecionada sobre a imagem do ECG.",
    status_code=status.HTTP_201_CREATED,
    responses=AUTH_MUTATION_RESPONSES,
)
def create_diagnosis_region(
    diagnosis_id: int,
    payload: DiagnosisRegionPayload,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    _validate_region_payload(payload)
    diagnosis = _get_diagnosis_or_404(session, diagnosis_id)
    region = DiagnosisRegion(
        exam_id=diagnosis.exam_id,
        diagnosis_id=diagnosis.id,
        x=payload.x,
        y=payload.y,
        width=payload.width,
        height=payload.height,
        created_by_id=current_user.id,
        created_by_name=current_user.full_name,
    )
    session.add(region)

    if diagnosis.source == "doctor_added" and diagnosis.review_status == "pending":
        diagnosis.review_status = "confirmed"

    _sync_legacy_region_fields(session, diagnosis)
    exam = _get_exam_or_404(session, diagnosis.exam_id)
    exam.updated_at = datetime.utcnow()
    session.add(diagnosis)
    session.add(exam)
    session.commit()
    session.refresh(diagnosis)
    return _diagnosis_payload(diagnosis, session=session)


@app.patch(
    "/diagnoses/{diagnosis_id}/regions/{region_id}",
    tags=["Diagnosticos"],
    summary="Atualizar regiao do diagnostico",
    description="Altera as coordenadas percentuais de uma area ja vinculada ao diagnostico.",
    responses=AUTH_MUTATION_RESPONSES,
)
def update_diagnosis_region(
    diagnosis_id: int,
    region_id: int,
    payload: DiagnosisRegionPayload,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    _validate_region_payload(payload)
    diagnosis = _get_diagnosis_or_404(session, diagnosis_id)
    region = _get_region_or_404(session, diagnosis_id, region_id)
    region.x = payload.x
    region.y = payload.y
    region.width = payload.width
    region.height = payload.height
    region.updated_at = datetime.utcnow()
    session.add(region)
    _sync_legacy_region_fields(session, diagnosis)

    exam = _get_exam_or_404(session, diagnosis.exam_id)
    exam.updated_at = datetime.utcnow()
    session.add(diagnosis)
    session.add(exam)
    session.commit()
    session.refresh(diagnosis)
    return _diagnosis_payload(diagnosis, session=session)


@app.delete(
    "/diagnoses/{diagnosis_id}/regions/{region_id}",
    tags=["Diagnosticos"],
    summary="Remover regiao do diagnostico",
    description="Remove uma area, preservando a exigencia de mapeamento para diagnosticos confirmados.",
    responses=AUTH_MUTATION_RESPONSES,
)
def delete_diagnosis_region(
    diagnosis_id: int,
    region_id: int,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    diagnosis = _get_diagnosis_or_404(session, diagnosis_id)
    region = _get_region_or_404(session, diagnosis_id, region_id)
    regions = _diagnosis_region_payloads(session, diagnosis)
    standard_text = standardize_diagnosis(diagnosis.name)
    if (
        len(regions) <= 1
        and _diagnosis_requires_region(standard_text, diagnosis.name)
        and _effective_review_status(session, diagnosis) == "confirmed"
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nao e possivel remover a ultima area de um infarto confirmado.",
        )

    session.delete(region)
    session.flush()
    _sync_legacy_region_fields(session, diagnosis)
    exam = _get_exam_or_404(session, diagnosis.exam_id)
    exam.updated_at = datetime.utcnow()
    session.add(diagnosis)
    session.add(exam)
    session.commit()
    session.refresh(diagnosis)
    return _diagnosis_payload(diagnosis, session=session)


@app.patch(
    "/exams/{exam_id}/diagnoses/{diagnosis_id}/review",
    tags=["Diagnosticos"],
    summary="Revisar diagnostico original",
    description="Confirma ou rejeita um diagnostico original vinculado ao exame informado.",
    responses=AUTH_MUTATION_RESPONSES,
)
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

    if payload.review_status == "confirmed":
        _ensure_region_before_confirm(session, diagnosis)

    diagnosis.review_status = payload.review_status
    exam.updated_at = datetime.utcnow()
    session.add(diagnosis)
    session.add(exam)
    session.commit()
    session.refresh(diagnosis)
    return _diagnosis_payload(diagnosis, session=session)


@app.delete(
    "/exams/{exam_id}/diagnoses/{diagnosis_id}",
    tags=["Diagnosticos"],
    summary="Remover diagnostico medico",
    description="Remove um diagnostico adicionado pelo medico; diagnosticos originais sao preservados.",
    responses=AUTH_MUTATION_RESPONSES,
)
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


@app.post(
    "/exams/{exam_id}/validate",
    tags=["Exames"],
    summary="Concluir validacao do exame",
    description="Finaliza o exame, incorpora o rascunho do usuario e registra o resultado da revisao.",
    responses=AUTH_MUTATION_RESPONSES,
)
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
    draft = _exam_draft_for_user(session, exam.id, current_user.id)
    status_before = exam.status_validation
    now = datetime.utcnow()
    review_notes = payload.notes if payload.notes is not None else (draft.notes if draft else None)

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
        notes=review_notes,
        created_at=now,
    )
    session.add(review)
    if draft:
        session.delete(draft)
    session.commit()
    session.refresh(exam)
    return _exam_payload(session, exam, include_details=True, current_user=current_user)


@app.get(
    "/dashboard/stats",
    tags=["Dashboard"],
    summary="Consultar indicadores do dashboard",
    description="Retorna contagens de fila, decisoes, mapeamentos e exames revisados no periodo.",
    responses=AUTH_RESPONSES,
)
def dashboard_stats(
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session),
) -> dict:
    exams = session.exec(select(Exam)).all()
    reviews = session.exec(select(Review).where(Review.status_after == "valido")).all()
    context = active_validation_context()
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    queue_state_counts = _queue_state_counts(session, exams, context)
    cross_filter_counts = _cross_filter_counts(session, exams, context)

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
        "queue_state_counts": queue_state_counts,
        "decision_counts": cross_filter_counts["decision"],
        "region_counts": cross_filter_counts["region"],
    }


# Initialize DB on first request (since lifespan is off)
_db_initialized = False


@app.middleware("http")
async def init_db_middleware(request, call_next):
    global _db_initialized
    request_path = request.url.path.rstrip("/") or "/"
    if request_path not in PUBLIC_SYSTEM_PATHS and not _db_initialized:
        if should_reset_database_on_startup():
            reset_db_and_tables()
        else:
            create_db_and_tables()
        _db_initialized = True
    response = await call_next(request)
    return response


handler = Mangum(app, lifespan="off")
