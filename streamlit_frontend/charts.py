"""Reusable chart builders for the Streamlit finance dashboard."""
from __future__ import annotations

from typing import Optional

import altair as alt
import pandas as pd


def asset_type_bar_chart(df: pd.DataFrame) -> alt.Chart:
    if df.empty:
        return alt.Chart(pd.DataFrame({"type": [], "total": []})).mark_bar()

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
        .encode(
            x=alt.X("total:Q", title="Quantidade"),
            y=alt.Y("type:N", sort="-x", title="Tipo de ativo"),
            color=alt.Color("type:N", legend=None, scale=alt.Scale(scheme="viridis")),
            tooltip=[alt.Tooltip("type:N", title="Tipo"), alt.Tooltip("total:Q", title="Quantidade")],
        )
        .properties(height=200)
    )
    return chart


def sector_distribution_chart(df: pd.DataFrame) -> alt.Chart:
    if df.empty:
        return alt.Chart(pd.DataFrame({"sector": [], "total": []})).mark_bar()

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
        .encode(
            y=alt.Y("sector:N", sort="-x", title="Setor"),
            x=alt.X("total:Q", title="Quantidade"),
            color=alt.Color("total:Q", legend=None, scale=alt.Scale(scheme="blues")),
            tooltip=[alt.Tooltip("sector:N", title="Setor"), alt.Tooltip("total:Q", title="Quantidade")],
        )
        .properties(height=260)
    )
    return chart


def price_line_chart(df: pd.DataFrame, ticker: str) -> alt.Chart:
    if df.empty:
        return alt.Chart(pd.DataFrame({"date": [], "close": []})).mark_line()

    chart = (
        alt.Chart(df)
        .mark_line(color="#2ecc71")
        .encode(
            x=alt.X("date:T", title="Data"),
            y=alt.Y("close:Q", title="Preço de fechamento"),
            tooltip=[
                alt.Tooltip("date:T", title="Data"),
                alt.Tooltip("open:Q", title="Abertura"),
                alt.Tooltip("close:Q", title="Fechamento"),
                alt.Tooltip("high:Q", title="Máximo"),
                alt.Tooltip("low:Q", title="Mínimo"),
            ],
        )
        .properties(title=f"Preço de fechamento - {ticker.upper()}")
    )
    return chart


def volume_area_chart(df: pd.DataFrame, ticker: str) -> alt.Chart:
    if df.empty:
        return alt.Chart(pd.DataFrame({"date": [], "volume": []})).mark_area()

    chart = (
        alt.Chart(df)
        .mark_area(opacity=0.3, color="#3498db")
        .encode(
            x=alt.X("date:T", title="Data"),
            y=alt.Y("volume:Q", title="Volume"),
            tooltip=[
                alt.Tooltip("date:T", title="Data"),
                alt.Tooltip("volume:Q", title="Volume"),
            ],
        )
        .properties(title=f"Volume negociado - {ticker.upper()}")
    )
    return chart


def api_calls_heatmap(df: pd.DataFrame) -> Optional[alt.Chart]:
    if df.empty:
        return None
    pivot = df.copy()
    pivot["hour"] = pd.to_datetime(pivot["hour"])
    chart = (
        alt.Chart(pivot)
        .mark_rect()
        .encode(
            x=alt.X("hour:T", title="Hora"),
            y=alt.Y("endpoint:N", title="Endpoint"),
            color=alt.Color("total:Q", title="Chamadas"),
            tooltip=[
                alt.Tooltip("hour:T", title="Hora"),
                alt.Tooltip("endpoint:N", title="Endpoint"),
                alt.Tooltip("total:Q", title="Chamadas"),
                alt.Tooltip("success:Q", title="Sucesso"),
                alt.Tooltip("cache_hits:Q", title="Cache hits"),
            ],
        )
        .properties(height=300)
    )
    return chart
