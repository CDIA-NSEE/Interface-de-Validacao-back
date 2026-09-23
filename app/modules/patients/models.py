from __future__ import annotations

from typing import Optional

from sqlmodel import Field, SQLModel


class Patient(SQLModel, table=True):
    __tablename__ = "patients"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    age: int
    sex: str
    weight: float
    height: float
    bmi: float
    birth_date: Optional[str] = None
