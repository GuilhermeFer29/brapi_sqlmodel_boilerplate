from __future__ import annotations
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class QuoteSnapshot(SQLModel, table=True):
    __tablename__ = "quote_snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, max_length=32)
    short_name: Optional[str] = Field(default=None, max_length=255)
    currency: Optional[str] = Field(default=None, max_length=16)
    regular_market_price: Optional[float] = Field(default=None)
    previous_close: Optional[float] = Field(default=None)
    market_change: Optional[float] = Field(default=None)
    market_change_percent: Optional[float] = Field(default=None)
    regular_market_time: Optional[datetime] = Field(default=None)
    raw: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
