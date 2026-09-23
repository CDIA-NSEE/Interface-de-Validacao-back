from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


class ValidationCycle(SQLModel, table=True):
    __tablename__ = "validation_cycles"

    id: Optional[int] = Field(default=None, primary_key=True)
    cycle_key: str = Field(index=True, unique=True)
    label: str
    cycle_start_date: Optional[date] = None
    general_review_day: int = Field(default=30)
    is_active: bool = Field(default=True, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
