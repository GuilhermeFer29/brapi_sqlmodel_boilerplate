"""Styling utilities shared across Streamlit pages."""
from __future__ import annotations

import streamlit as st


def apply_global_theme() -> None:
    """Apply page config and custom CSS for a finance dashboard look."""
    if not st.session_state.get("_page_configured", False):
        st.set_page_config(
            page_title="Painel Financeiro",
            page_icon="📈",
            layout="wide",
            initial_sidebar_state="expanded",
        )
        st.session_state["_page_configured"] = True

    st.markdown(
        """
        <style>
        body, .stApp {
            background-color: #0e1117;
            color: #f5f5f5;
        }
        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3 {
            color: #f5f5f5;
        }
        .metric-card {
            padding: 1.2rem;
            border-radius: 0.75rem;
            background: linear-gradient(145deg, #161b22 0%, #0f1115 100%);
            border: 1px solid rgba(46, 204, 113, 0.2);
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.35);
        }
        .stMetric label {
            color: #a0aec0;
            font-size: 0.9rem;
        }
        .stMetric .stMarkdown {
            color: #2ecc71 !important;
        }
        div[data-testid="stDataFrame"] div[role="grid"] {
            border: none;
        }
        .route-card {
            background: linear-gradient(135deg, #161b22, #101419);
            border: 1px solid rgba(46, 204, 113, 0.2);
            border-radius: 12px;
            padding: 1.1rem;
            margin-bottom: 1rem;
        }
        .route-card h3 {
            margin-bottom: 0.5rem;
        }
        .badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 999px;
            background-color: rgba(46, 204, 113, 0.15);
            color: #2ecc71;
            font-weight: 600;
            margin-right: 0.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
