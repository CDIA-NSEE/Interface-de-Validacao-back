from typing import Literal, Optional

from pydantic import BaseModel


class StatusUpdate(BaseModel):
    status_validation: Literal["nao_validado", "em_validacao", "valido"]


class ExamValidate(BaseModel):
    review_result: Literal["sem_alteracao", "alterado"]
    notes: Optional[str] = None
    doctor_name: Optional[str] = None


class ExamDraftUpdate(BaseModel):
    notes: Optional[str] = None
