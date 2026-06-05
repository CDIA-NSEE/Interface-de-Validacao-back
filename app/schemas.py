from typing import Literal, Optional

from pydantic import BaseModel


class StatusUpdate(BaseModel):
    status_validation: Literal["nao_validado", "em_validacao", "valido"]


class DiagnosisCreate(BaseModel):
    name: str
    is_abnormal: bool = False
    region_x: Optional[float] = None
    region_y: Optional[float] = None
    region_width: Optional[float] = None
    region_height: Optional[float] = None


class ExamValidate(BaseModel):
    review_result: Literal["sem_alteracao", "alterado"]
    notes: Optional[str] = None
    doctor_name: str = "Dr. João"

