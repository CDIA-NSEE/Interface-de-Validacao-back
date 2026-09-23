from typing import Literal, Optional

from pydantic import BaseModel


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
