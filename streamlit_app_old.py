from __future__ import annotations

import os
import pandas as pd
import streamlit as st
import httpx
from dotenv import load_dotenv

load_dotenv()

from app.agent.mcp_agent import build_agent_sync, run_sync

st.set_page_config(page_title="MVP • Agno + MCP brapi", layout="wide")
st.title("MVP • Agno + MCP brapi + Streamlit")

# Estado
if "agent" not in st.session_state:
    try:
        st.session_state.agent = build_agent_sync()
    except Exception as e:
        st.error(f"Falha ao iniciar agente: {e}")
        st.stop()

if "messages" not in st.session_state:
    st.session_state.messages = []

backend_base = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")

tab_chat, tab_routes = st.tabs(["💬 Chat (Agno + MCP)", "🧪 Testes de Rotas (seu backend)"])

# === Chat ===
with tab_chat:
    st.subheader("Agente conversacional • Gemini 2.5 Flash + MCP da brapi")

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_msg = st.chat_input("Pergunte algo… ex.: 'Cotação de PETR4 nos últimos 3 meses'")
    if user_msg:
        st.session_state.messages.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)

        with st.chat_message("assistant"):
            with st.spinner("Consultando MCP + respondendo…"):
                try:
                    reply = run_sync(st.session_state.agent, user_msg)
                except Exception as e:
                    reply = f"Erro ao consultar agente/MCP: {e}"
                st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "content": reply})

    st.caption("Observação: ferramentas premium (FX/crypto/prime-rate) podem exigir plano na brapi.")

# === Rotas diretas ===
with tab_routes:
    st.subheader("Teste rápido das suas rotas FastAPI")

    # /api/quote/history
    c1, c2, c3 = st.columns(3)
    with c1:
        ticker = st.text_input("Ticker", value="HGLG11")
    with c2:
        period = st.selectbox("Período", ["3mo", "6mo", "1y", "2y"], index=0)
    with c3:
        interval = st.selectbox("Intervalo", ["1d", "1wk", "1mo"], index=0)

    if st.button("GET /api/quote/history"):
        url = f"{backend_base}/api/quote/history"
        params = {"ticker": ticker, "period": period, "interval": interval}
        try:
            with httpx.Client(timeout=30) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
            st.success("OK")
            st.json(data)

            items = data.get("items", [])
            if items:
                df = pd.DataFrame(items)
                if {"date", "close"}.issubset(df.columns):
                    df["date"] = pd.to_datetime(df["date"])
                    df.set_index("date", inplace=True)
                    st.line_chart(df["close"], height=240)
        except httpx.HTTPError as e:
            st.error(f"Erro HTTP: {e}")
        except Exception as e:
            st.error(f"Erro: {e}")

    st.divider()

    # /api/macro/prime-rate/scan
    c4, c5 = st.columns(2)
    with c4:
        include_latest = st.checkbox("include_latest", value=True)
    with c5:
        concurrency = st.slider("concurrency", min_value=1, max_value=16, value=6)

    if st.button("GET /api/macro/prime-rate/scan"):
        url = f"{backend_base}/api/macro/prime-rate/scan"
        params = {"include_latest": str(include_latest).lower(), "concurrency": concurrency}
        try:
            with httpx.Client(timeout=60) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                data = r.json()
            st.success("OK")
            st.json(data)

            results = data.get("results", [])
            rows = [
                {"country": x.get("country"), "date": x.get("date"), "value": x.get("value")}
                for x in results if not x.get("error")
            ]
            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True)
        except httpx.HTTPError as e:
            st.error(f"Erro HTTP: {e}")
        except Exception as e:
            st.error(f"Erro: {e}")

st.write("© MVP Agno + MCP brapi • Streamlit")
