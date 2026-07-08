from typing import Literal, Optional

from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str

    @property
    def identifier(self) -> str:
        return (self.email or self.username or "").strip().lower()


class UserRead(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    full_name: str
    role: str
    is_active: bool


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


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
