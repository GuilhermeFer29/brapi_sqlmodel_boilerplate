from __future__ import annotations
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class CurrencySnapshot(SQLModel, table=True):
    __tablename__ = "currency_snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    pair: str = Field(index=True, max_length=32)  # ex: USD-BRL
    bid: Optional[float] = Field(default=None)
    ask: Optional[float] = Field(default=None)
    pct_change: Optional[float] = Field(default=None)
    time: Optional[datetime] = Field(default=None)
    raw: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
