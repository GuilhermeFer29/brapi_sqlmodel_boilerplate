from __future__ import annotations
from typing import Optional, Dict, Any
from sqlmodel import SQLModel, Field, Column, JSON
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class ApiCall(SQLModel, table=True):
    __tablename__ = "api_calls"
    id: Optional[int] = Field(default=None, primary_key=True)
    endpoint: str = Field(index=True, max_length=64)
    tickers: Optional[str] = Field(default=None, index=True, max_length=512)
    params: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    cached: bool = Field(default=False, index=True)
    status_code: int = Field(default=200)
    error: Optional[str] = Field(default=None)
    response: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=utcnow, index=True)
