from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app._common import page_setup, require_database

page_setup("Coverage Map", "🗺️")
require_database()

from control_tower.config import DEFAULT_DB_PATH, MISSION_LABELS  # noqa: E402
from control_tower.coverage import coverage_view  # noqa: E402
from control_tower.db import read_frame  # noqa: E402

st.title("Coverage Map")
st.caption("Available eligible capacity ÷ expected demand, by day and mission type")

dates = read_frame("SELECT DISTINCT target_date FROM coverage_snapshots ORDER BY target_date", (), DEFAULT_DB_PATH)["target_date"].tolist()
selected_date = st.sidebar.selectbox("Forecast date", dates, index=0)
mission_type = st.sidebar.selectbox("Mission type", list(MISSION_LABELS), format_func=MISSION_LABELS.get)
frame = coverage_view(DEFAULT_DB_PATH, target_date=date.fromisoformat(selected_date))
frame = frame[frame.mission_type == mission_type].copy()

a, b, c, d = st.columns(4)
a.metric("Expected demand", f"{frame.expected_demand.sum():.1f}")
b.metric("Allocated capacity", f"{frame.available_capacity.sum():.1f}")
c.metric("Critical areas", int((frame.coverage_status == "critical").sum()))
d.metric("Healthy areas", int((frame.coverage_status == "healthy").sum()))

color_map = {"healthy": "#2ca02c", "watch": "#f5a623", "critical": "#d62728"}
fig = px.scatter_map(
    frame, lat="latitude", lon="longitude", color="coverage_status", size="expected_demand",
    hover_name="city", hover_data={"postal_code": True, "coverage_ratio": ":.2f",
                                    "available_capacity": ":.1f", "expected_demand": ":.1f",
                                    "latitude": False, "longitude": False},
    color_discrete_map=color_map, zoom=4.4, height=590, map_style="open-street-map",
)
fig.update_layout(margin={"r": 0, "t": 0, "l": 0, "b": 0})
st.plotly_chart(fig, width="stretch")

table = frame[["city", "postal_code", "available_capacity", "expected_demand", "coverage_ratio", "coverage_status"]]
st.dataframe(table.sort_values("coverage_ratio"), hide_index=True, width="stretch")
st.caption("Capacity is conservatively allocated across each partner's eligible zones and mission types to prevent double counting.")
