from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from control_tower.config import DEFAULT_DB_PATH  # noqa: E402
from control_tower.db import database_ready  # noqa: E402


def page_setup(title: str, icon: str) -> None:
    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    st.markdown(
        """
        <style>
        .block-container {padding-top: 2rem; padding-bottom: 3rem;}
        [data-testid="stMetric"] {background:#f7f8fa; border:1px solid #e8eaed; padding:12px; border-radius:12px;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def require_database() -> None:
    if not database_ready(DEFAULT_DB_PATH):
        st.error("The demo database has not been generated yet.")
        st.code("python scripts/setup_demo.py", language="bash")
        st.stop()

def percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"
