from typing import Literal, Optional

from pydantic import BaseModel


class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: str
    role: str
    is_active: bool


class StatusUpdate(BaseModel):
    status_validation: Literal["nao_validado", "em_validacao", "valido"]


class DiagnosisCreate(BaseModel):
    name: str
    is_abnormal: bool = False
    region_x: Optional[float] = None
    region_y: Optional[float] = None
    region_width: Optional[float] = None
    region_height: Optional[float] = None


class DiagnosisReview(BaseModel):
    review_status: Literal["confirmed", "rejected"]
    notes: Optional[str] = None


class DiagnosisRegionPayload(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ExamValidate(BaseModel):
    review_result: Literal["sem_alteracao", "alterado"]
    notes: Optional[str] = None
    doctor_name: Optional[str] = None


class ExamDraftUpdate(BaseModel):
    notes: Optional[str] = None


class HealthResponse(BaseModel):
    status: Literal["ok"]
    database: Literal["connected"]


class ErrorResponse(BaseModel):
    detail: str
