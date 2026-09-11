from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app._common import page_setup, require_database

page_setup("Quality Risk", "🔎")
require_database()

from control_tower.config import DEFAULT_DB_PATH, MODEL_PATH  # noqa: E402
from control_tower.db import read_frame  # noqa: E402

st.title("Quality Risk")

frame = read_frame(
    """
    SELECT qa.mission_id Mission, qa.risk_probability "Risk probability", qa.risk_level "Risk level",
           m.mission_type "Mission type", z.city City, p.name Partner, m.appointment_at Appointment,
           qa.model_version "Model version"
    FROM quality_assessments qa JOIN missions m USING(mission_id)
    JOIN zones z ON z.zone_id = m.zone_id
    LEFT JOIN assignments a USING(mission_id) LEFT JOIN partners p USING(partner_id)
    ORDER BY qa.risk_probability DESC
    """,
    (), DEFAULT_DB_PATH,
)
if frame.empty:
    st.info("No quality assessments are available. Rebuild the demo with quality modeling enabled.")
else:
    level = st.sidebar.multiselect("Risk level", ["high", "medium", "low"], default=["high"])
    filtered = frame[frame["Risk level"].isin(level)] if level else frame
    a, b, c = st.columns(3)
    a.metric("High-risk missions", int((frame["Risk level"] == "high").sum()))
    b.metric("Average predicted risk", f"{frame['Risk probability'].mean():.1%}")
    c.metric("Model artifact", "Available" if MODEL_PATH.exists() else "Missing")
    fig = px.histogram(frame, x="Risk probability", color="Risk level", nbins=30, title="Predicted risk distribution",
                       color_discrete_map={"high": "#d62728", "medium": "#f5a623", "low": "#2ca02c"})
    st.plotly_chart(fig, width="stretch")
    display = filtered.head(500).copy()
    display["Risk probability"] = display["Risk probability"].map(lambda value: f"{value:.1%}")
    st.dataframe(display, hide_index=True, width="stretch", height=520)
