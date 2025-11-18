"""Helper functions shared across Streamlit pages."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Iterable, List

import streamlit as st

from .config import get_settings

ASSET_TYPE_LABELS: Dict[str, str] = {
    "stock": "Ação",
    "fund": "Fundo Imobiliário",
    "bdr": "BDR",
    "etf": "ETF",
    "index": "Índice",
}


@st.cache_resource(show_spinner=False)
def get_cached_settings():
    """Return cached settings for Streamlit runtime."""
    return get_settings()


def humanize_asset_type(value: str | None) -> str:
    if not value:
        return "-"
    return ASSET_TYPE_LABELS.get(value.lower(), value.upper())


def format_currency(value: float | None) -> str:
    if value is None:
        return "-"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def format_datetime(dt) -> str:
    if not dt:
        return "-"
    return dt.strftime("%d/%m/%Y %H:%M")
