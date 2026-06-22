"""Punto de entrada mínimo para Streamlit Cloud (health check)."""

from __future__ import annotations

import sys

import streamlit as st

if sys.version_info >= (3, 14):
    st.error(
        "SAVT no es compatible con Python 3.14 en Streamlit Cloud. "
        "Borrá la app y volvé a desplegarla con **Python 3.11** "
        "(Advanced settings al crear la app)."
    )
    st.stop()

st.set_page_config(
    page_title="SAVT — Auditoría de Tesis",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

from savt.streamlit_app import run_app

run_app()
