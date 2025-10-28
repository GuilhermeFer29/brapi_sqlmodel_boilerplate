from __future__ import annotations
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class CryptoSnapshot(SQLModel, table=True):
    __tablename__ = "crypto_snapshots"
    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True, max_length=64)
    currency: Optional[str] = Field(default=None, max_length=16)
    price: Optional[float] = Field(default=None)
    change: Optional[float] = Field(default=None)
    change_percent: Optional[float] = Field(default=None)
    time: Optional[datetime] = Field(default=None)
    raw: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
