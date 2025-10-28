from __future__ import annotations
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class MacroPoint(SQLModel, table=True):
    __tablename__ = "macro_points"
    id: Optional[int] = Field(default=None, primary_key=True)
    series: str = Field(index=True, max_length=32)  # ex: inflation, prime_rate
    country: str = Field(index=True, max_length=64)
    ref_date: Optional[datetime] = Field(default=None)
    value: Optional[float] = Field(default=None)
    raw: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
