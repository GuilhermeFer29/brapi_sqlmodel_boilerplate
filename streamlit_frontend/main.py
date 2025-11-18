"""Entry point for the Streamlit finance dashboard."""
from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Callable, Dict
import sys

import pandas as pd
import streamlit as st

if __package__ in (None, ""):
    PACKAGE_ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(PACKAGE_ROOT.parent))

    import streamlit_frontend.data_access as data_access
    from streamlit_frontend.charts import (
        api_calls_heatmap,
        asset_type_bar_chart,
        price_line_chart,
        sector_distribution_chart,
        volume_area_chart,
    )
    from streamlit_frontend.theme import apply_global_theme
    from streamlit_frontend.utils import get_cached_settings, humanize_asset_type
else:
    from . import data_access
    from .charts import (
        api_calls_heatmap,
        asset_type_bar_chart,
        price_line_chart,
        sector_distribution_chart,
        volume_area_chart,
    )
    from .theme import apply_global_theme
    from .utils import get_cached_settings, humanize_asset_type


Page = Callable[[], None]


def render_overview() -> None:
    summary = data_access.fetch_asset_summary()
    recent_prices = data_access.fetch_recent_prices()

    cols = st.columns(4)
    with cols[0]:
        st.metric("Ativos cadastrados", f"{summary['total_assets']:,}".replace(",", "."))
    with cols[1]:
        latest_update = summary.get("latest_update")
        formatted = latest_update.strftime("%d/%m/%Y") if latest_update else "-"
        st.metric("Última atualização", formatted)
    with cols[2]:
        most_common_type = summary.get("by_type", [{}])[0] if summary.get("by_type") else {}
        st.metric(
            "Tipo predominante",
            humanize_asset_type(most_common_type.get("type")),
        )
    with cols[3]:
        most_common_sector = summary.get("by_sector", [{}])[0] if summary.get("by_sector") else {}
        st.metric("Setor predominante", most_common_sector.get("sector", "-"))

    st.markdown("### Distribuição por tipo")
    st.altair_chart(asset_type_bar_chart(pd.DataFrame(summary.get("by_type", []))), use_container_width=True)

    st.markdown("### Top 10 setores")
    st.altair_chart(sector_distribution_chart(pd.DataFrame(summary.get("by_sector", []))), use_container_width=True)

    if not recent_prices.empty:
        st.markdown("### Tendência recente (últimos fechamentos)")
        latest = (
            recent_prices.sort_values(["ticker", "date"], ascending=[True, False])
            .groupby("ticker")
            .head(1)
        )
        st.dataframe(
            latest[["ticker", "name", "type", "date", "close"]]
            .rename(
                columns={
                    "ticker": "Ticker",
                    "name": "Nome",
                    "type": "Tipo",
                    "date": "Data",
                    "close": "Fechamento",
                }
            )
            .assign(Data=lambda df: df["Data"].dt.strftime("%d/%m/%Y"), Fechamento=lambda df: df["Fechamento"].map(lambda v: f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")))
        )
    else:
        st.info("Nenhum dado de preço encontrado. Execute o backfill de OHLCV para visualizar gráficos.")


def render_assets() -> None:
    st.markdown("### Catálogo de ativos")
    types = data_access.fetch_distinct_values("type")
    sectors = data_access.fetch_distinct_values("sector")

    col1, col2, col3 = st.columns(3)
    with col1:
        type_filter = st.selectbox("Tipo", options=["Todos"] + types, index=0)
    with col2:
        sector_filter = st.selectbox("Setor", options=["Todos"] + sectors, index=0)
    with col3:
        search = st.text_input("Buscar por ticker ou nome")

    df = data_access.fetch_assets_dataframe(
        asset_type=None if type_filter == "Todos" else type_filter,
        sector=None if sector_filter == "Todos" else sector_filter,
        search=search or None,
    )

    if df.empty:
        st.warning("Nenhum ativo encontrado para os filtros selecionados.")
        return

    df_display = df.rename(
        columns={
            "ticker": "Ticker",
            "name": "Nome",
            "type": "Categoria",
            "sector": "Setor",
            "segment": "Segmento",
            "logo_url": "Logo",
            "isin": "ISIN",
            "updated_at": "Atualizado em",
        }
    )
    df_display["Categoria"] = df_display["Categoria"].map(humanize_asset_type)
    df_display["Logo"] = df_display["Logo"].fillna("")
    df_display["Atualizado em"] = pd.to_datetime(df_display["Atualizado em"]).dt.strftime("%d/%m/%Y %H:%M")
    st.dataframe(
        df_display,
        use_container_width=True,
        column_config={
            "Logo": st.column_config.ImageColumn("Logo", width="small", help="Logo oficial do ativo"),
        },
    )


def render_history() -> None:
    st.markdown("### Histórico de preços")
    tickers = data_access.fetch_distinct_values("ticker")
    if not tickers:
        st.warning("Nenhum ticker disponível. Sincronize o catálogo primeiro.")
        return

    ticker = st.selectbox("Ticker", options=tickers)
    periods = {
        "1 mês": dt.timedelta(days=30),
        "3 meses": dt.timedelta(days=90),
        "6 meses": dt.timedelta(days=180),
        "1 ano": dt.timedelta(days=365),
        "2 anos": dt.timedelta(days=730),
    }
    period_choice = st.selectbox("Período", options=list(periods.keys()), index=1)
    end_date = dt.datetime.utcnow()
    start_date = end_date - periods[period_choice]

    df = data_access.fetch_ohlcv_timeseries(ticker, start_date=start_date, end_date=end_date)
    if df.empty:
        st.warning("Sem dados OHLCV para o período selecionado.")
        return

    st.altair_chart(price_line_chart(df, ticker), use_container_width=True)
    st.altair_chart(volume_area_chart(df, ticker), use_container_width=True)

    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    stats_col1.metric("Máximo", f"R$ {df['high'].max():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    stats_col2.metric("Mínimo", f"R$ {df['low'].min():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    stats_col3.metric("Fechamento médio", f"R$ {df['close'].mean():,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    stats_col4.metric("Volume total", f"{df['volume'].sum():,.0f}".replace(",", "."))


def render_routes() -> None:
    st.markdown("### Catálogo de rotas da API")
    schema = data_access.fetch_openapi_schema()
    paths: Dict[str, Dict[str, Dict]] = schema.get("paths", {})

    st.caption("Clique em uma rota para testar uma chamada rápida.")
    for path, operations in paths.items():
        for method, definition in operations.items():
            with st.expander(f"{method.upper()} {path}"):
                st.markdown(definition.get("summary", "Sem descrição"))
                params = definition.get("parameters", [])
                param_values = {}
                if params:
                    st.markdown("**Parâmetros:**")
                    for param in params:
                        pname = param.get("name")
                        required = param.get("required", False)
                        default = param.get("schema", {}).get("default")
                        value = st.text_input(
                            f"{pname} ({'obrigatório' if required else 'opcional'})",
                            value="" if default is None else str(default),
                            key=f"param_{method}_{path}_{pname}",
                        )
                        if value:
                            param_values[pname] = value
                if st.button("Testar rota", key=f"call_{method}_{path}"):
                    result = data_access.test_api_endpoint(method, path, params=param_values)
                    if result.get("data"):
                        st.success(f"Status {result['status']}")
                        st.json(result["data"])
                    else:
                        st.error(f"Falha: {result.get('status')} - {result.get('error')}")


def render_monitoring() -> None:
    st.markdown("### Monitoramento de chamadas à API")
    df = data_access.fetch_api_call_stats()
    chart = api_calls_heatmap(df)
    if chart:
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Nenhum registro de chamadas nas últimas 24 horas.")


PAGES: Dict[str, Page] = {
    "Visão Geral": render_overview,
    "Explorar Ativos": render_assets,
    "Histórico": render_history,
    "Rotas da API": render_routes,
    "Monitoramento": render_monitoring,
}


def main() -> None:
    apply_global_theme()
    settings = get_cached_settings()

    with st.sidebar:
        st.header("Painel Financeiro")
        st.caption("Dados sincronizados via brapi.dev")
        st.divider()
        selection = st.radio("Seções", options=list(PAGES.keys()), index=0)
        st.markdown("---")
        st.markdown(f"**API**: {settings.api_base_url}")

    PAGES[selection]()


if __name__ == "__main__":
    main()
