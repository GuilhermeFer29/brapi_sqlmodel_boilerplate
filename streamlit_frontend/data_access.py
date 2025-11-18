"""Utility functions to access the relational database and FastAPI backend."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd
import requests
import streamlit as st
from requests import HTTPError
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from .config import get_settings


@st.cache_resource(show_spinner=False)
def get_engine() -> Engine:
    settings = get_settings()
    engine = create_engine(settings.database_url_sync, pool_pre_ping=True, future=True)
    return engine


@contextmanager
def get_connection():
    engine = get_engine()
    with engine.connect() as conn:
        yield conn


@st.cache_data(show_spinner=False, ttl=120)
def fetch_assets_dataframe(
    *,
    asset_type: str | None = None,
    sector: str | None = None,
    search: str | None = None,
    limit: int = 1000,
) -> pd.DataFrame:
    """Return assets filtered according to optional parameters."""

    query = [
        "SELECT id, ticker, name, type, sector, segment, isin, logo_url, updated_at",
        "FROM assets",
    ]
    conditions: List[str] = []
    params: Dict[str, Any] = {"limit": limit}

    if asset_type:
        conditions.append("type = :type")
        params["type"] = asset_type

    if sector:
        conditions.append("sector = :sector")
        params["sector"] = sector

    if search:
        conditions.append("(ticker LIKE :search OR name LIKE :search)")
        params["search"] = f"%{search}%"

    if conditions:
        query.append("WHERE " + " AND ".join(conditions))

    query.append("ORDER BY updated_at DESC")
    query.append("LIMIT :limit")
    compiled = "\n".join(query)

    with get_connection() as conn:
        df = pd.read_sql(
            text(compiled),
            conn,
            params=params,
            parse_dates=["updated_at"],
        )
    return df


@st.cache_data(show_spinner=False, ttl=120)
def fetch_asset_summary() -> dict[str, Any]:
    """Return aggregated indicators for the overview page."""

    queries = {
        "total_assets": "SELECT COUNT(*) FROM assets",
        "by_type": "SELECT type, COUNT(*) AS total FROM assets GROUP BY type ORDER BY total DESC",
        "by_sector": "SELECT sector, COUNT(*) AS total FROM assets WHERE sector IS NOT NULL GROUP BY sector ORDER BY total DESC LIMIT 10",
        "latest_update": "SELECT MAX(updated_at) FROM assets",
    }

    summary: dict[str, Any] = {}
    with get_connection() as conn:
        for key, sql in queries.items():
            result = conn.execute(text(sql))
            if key in {"total_assets"}:
                summary[key] = result.scalar() or 0
            elif key == "latest_update":
                summary[key] = result.scalar()
            else:
                rows = result.fetchall()
                summary[key] = [dict(row._mapping) for row in rows]
    return summary


@st.cache_data(show_spinner=False, ttl=120)
def fetch_recent_prices(sample_size: int = 12) -> pd.DataFrame:
    """Return the latest close price per ticker for trend cards."""
    sql = text(
        """
        SELECT sub.ticker,
               sub.date,
               sub.close,
               a.name,
               a.type,
               ROW_NUMBER() OVER (PARTITION BY sub.ticker ORDER BY sub.date DESC) AS rn
        FROM quote_ohlcv AS sub
        JOIN assets a ON a.ticker = sub.ticker
        WHERE sub.date >= :cutoff
        """
    )
    cutoff = datetime.utcnow() - timedelta(days=sample_size * 2)
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params={"cutoff": cutoff}, parse_dates=["date"])
    if df.empty:
        return df
    df = df[df["rn"] <= sample_size]
    df = df.sort_values(["ticker", "date"])
    return df


@st.cache_data(show_spinner=False, ttl=120)
def fetch_ohlcv_timeseries(
    ticker: str,
    *,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    limit: int | None = None,
) -> pd.DataFrame:
    """Return OHLCV data for a specific ticker."""

    clauses = ["ticker = :ticker"]
    params: Dict[str, Any] = {"ticker": ticker.upper()}

    if start_date:
        clauses.append("date >= :start_date")
        params["start_date"] = start_date
    if end_date:
        clauses.append("date <= :end_date")
        params["end_date"] = end_date

    sql_parts = [
        "SELECT date, open, high, low, close, volume, adj_close",
        "FROM quote_ohlcv",
        "WHERE " + " AND ".join(clauses),
        "ORDER BY date ASC",
    ]
    if limit:
        sql_parts.append("LIMIT :limit")
        params["limit"] = limit
    sql = text("\n".join(sql_parts))

    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params=params, parse_dates=["date"])
    return df


VALID_DISTINCT_COLUMNS: dict[str, set[str]] = {
    "assets": {"ticker", "type", "sector"},
    "quote_ohlcv": {"ticker"},
}


@st.cache_data(show_spinner=False, ttl=120)
def fetch_distinct_values(column: str, table: str = "assets") -> List[str]:
    allowed = VALID_DISTINCT_COLUMNS.get(table)
    if not allowed or column not in allowed:
        raise ValueError(f"Column '{column}' not allowed for table '{table}'")

    sql = text(
        f"SELECT DISTINCT {column} FROM {table} "
        f"WHERE {column} IS NOT NULL ORDER BY {column}"
    )
    with get_connection() as conn:
        rows = conn.execute(sql).scalars().all()
    return [value for value in rows if value]


@st.cache_data(show_spinner=False, ttl=120)
def fetch_api_call_stats(hours: int = 24) -> pd.DataFrame:
    sql = text(
        """
        SELECT DATE_FORMAT(created_at, '%Y-%m-%d %H:00:00') AS hour,
               endpoint,
               COUNT(*) AS total,
               SUM(CASE WHEN status_code BETWEEN 200 AND 299 THEN 1 ELSE 0 END) AS success,
               SUM(CASE WHEN cached THEN 1 ELSE 0 END) AS cache_hits
        FROM api_calls
        WHERE created_at >= (UTC_TIMESTAMP() - INTERVAL :hours HOUR)
        GROUP BY hour, endpoint
        ORDER BY hour ASC
        """
    )
    with get_connection() as conn:
        df = pd.read_sql(sql, conn, params={"hours": hours}, parse_dates=["hour"])
    return df


@st.cache_data(show_spinner=False, ttl=120)
def fetch_openapi_schema() -> dict[str, Any]:
    settings = get_settings()
    url = f"{settings.api_base_url}/openapi.json"
    headers = {"Authorization": f"Bearer {settings.brapi_token}"} if settings.brapi_token else {}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    return response.json()


def test_api_endpoint(method: str, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    settings = get_settings()
    url = f"{settings.api_base_url}{path}"
    headers = {"Authorization": f"Bearer {settings.brapi_token}"} if settings.brapi_token else {}

    request_method = method.lower()
    try:
        response = requests.request(request_method, url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        return {"status": response.status_code, "data": response.json()}
    except HTTPError as exc:
        return {"status": exc.response.status_code if exc.response else None, "error": str(exc)}
    except Exception as exc:
        return {"status": None, "error": str(exc)}
