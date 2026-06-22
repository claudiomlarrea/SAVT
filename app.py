"""Punto de entrada mínimo para Streamlit Cloud (health check)."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="SAVT — Auditoría de Tesis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from savt.streamlit_app import run_app

run_app()
