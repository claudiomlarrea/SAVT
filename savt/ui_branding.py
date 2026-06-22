from __future__ import annotations

from pathlib import Path

import streamlit as st

# Manual de identidad visual UCCuyo v1.0 (2017)
UCCUYO_GREEN = "#06492f"
UCCUYO_GREEN_DARK = "#03482e"
UCCUYO_GREEN_SHIELD = "#17452e"
UCCUYO_RED = "#741520"
UCCUYO_ORANGE = "#e17d16"
UCCUYO_TERRACOTTA = "#b53521"
UCCUYO_GRAY = "#808080"
UCCUYO_TEXT = "#333333"
UCCUYO_BG_SOFT = "#eef4f0"

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "oia_uccuyo_logo.jpg"


def inject_branding() -> None:
    st.markdown(
        f"""
        <style>
        html, body, [class*="css"] {{
            font-family: "Montserrat", "Helvetica Neue", Arial, sans-serif;
        }}

        .block-container {{
            padding-top: 1.5rem;
            max-width: 1100px;
        }}

        [data-testid="stSidebar"] {{
            background: linear-gradient(180deg, {UCCUYO_BG_SOFT} 0%, #ffffff 100%);
            border-right: 1px solid #d8e6de;
        }}

        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
        [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {{
            color: {UCCUYO_GREEN};
        }}

        .savt-hero {{
            background: linear-gradient(135deg, {UCCUYO_GREEN} 0%, {UCCUYO_GREEN_DARK} 100%);
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            margin-bottom: 1.25rem;
            color: #ffffff;
            border-left: 6px solid {UCCUYO_ORANGE};
        }}

        .savt-hero h1 {{
            color: #ffffff !important;
            font-size: 2rem;
            font-weight: 700;
            margin: 0 0 0.25rem 0;
            letter-spacing: 0.04em;
        }}

        .savt-hero .savt-subtitle {{
            color: #e8f3ed;
            font-size: 0.95rem;
            margin: 0 0 0.75rem 0;
        }}

        .savt-hero .savt-desc {{
            color: #f4faf7;
            font-size: 0.92rem;
            line-height: 1.55;
            margin: 0;
        }}

        .savt-institution {{
            color: #cfe3d8;
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-top: 0.75rem;
        }}

        h2, h3 {{
            color: {UCCUYO_GREEN_SHIELD};
        }}

        hr {{
            border: none;
            border-top: 2px solid {UCCUYO_BG_SOFT};
            margin: 1.5rem 0;
        }}

        div[data-testid="stAlert"] {{
            border-left: 4px solid {UCCUYO_GREEN};
        }}

        div[data-testid="stAlert"][data-baseweb="notification"] {{
            background-color: {UCCUYO_BG_SOFT};
        }}

        .stButton > button[kind="primary"] {{
            background-color: {UCCUYO_GREEN};
            border: 1px solid {UCCUYO_GREEN_DARK};
            color: #ffffff;
            font-weight: 600;
        }}

        .stButton > button[kind="primary"]:hover {{
            background-color: {UCCUYO_GREEN_DARK};
            border-color: {UCCUYO_GREEN_SHIELD};
        }}

        .stDownloadButton > button {{
            border-color: {UCCUYO_GREEN};
            color: {UCCUYO_GREEN};
        }}

        .stProgress > div > div > div {{
            background-color: {UCCUYO_ORANGE};
        }}

        [data-testid="stFileUploader"] section {{
            border: 1px dashed #b8cfc2;
            background: {UCCUYO_BG_SOFT};
        }}

        [data-testid="stMetricValue"] {{
            color: {UCCUYO_GREEN};
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )
