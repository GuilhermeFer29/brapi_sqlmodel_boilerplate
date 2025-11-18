"""Streamlit frontend configuration utilities.

Leverages environment variables already used by the backend so both
applications share the same credentials. Falls back to sensible defaults
for local development, following Streamlit guidance on secrets management.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class FrontendSettings:
    """Settings propagated to Streamlit pages."""

    database_url_async: str
    api_base_url: str
    brapi_token: str | None
    app_name: str = "Painel Financeiro"
    app_icon: str = "📈"

    @property
    def database_url_sync(self) -> str:
        """Return a SQLAlchemy sync URL compatible with st.connection."""
        if self.database_url_async.startswith("mysql+asyncmy"):
            return self.database_url_async.replace("mysql+asyncmy", "mysql+pymysql", 1)
        if self.database_url_async.startswith("sqlite+aiosqlite"):
            return self.database_url_async.replace("sqlite+aiosqlite", "sqlite", 1)
        return self.database_url_async

    @property
    def streamlit_theme(self) -> dict[str, str]:
        return {
            "primaryColor": "#2ecc71",
            "backgroundColor": "#0e1117",
            "secondaryBackgroundColor": "#161b22",
            "textColor": "#f5f5f5",
        }


@lru_cache(maxsize=1)
def get_settings() -> FrontendSettings:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        from dotenv import load_dotenv

        load_dotenv(env_path, override=False)

    database_url = os.getenv("DATABASE_URL", "mysql+asyncmy://user:pass@localhost:3306/brapi_db")
    api_base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    brapi_token = os.getenv("BRAPI_TOKEN")

    return FrontendSettings(
        database_url_async=database_url,
        api_base_url=api_base_url.rstrip("/"),
        brapi_token=brapi_token,
    )
