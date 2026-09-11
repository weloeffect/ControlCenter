from __future__ import annotations

# Temporarily hidden from Streamlit navigation. Move back to app/pages to restore.

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app._common import page_setup, require_database

page_setup("Automated Alerts", "🚨")
require_database()

from control_tower.alerts import alert_view, detect_alerts  # noqa: E402
from control_tower.config import DEFAULT_DB_PATH  # noqa: E402

st.title("Automated Alerts")

if st.button("Run alert rules now"):
    detected = detect_alerts(DEFAULT_DB_PATH)
    st.toast(f"Evaluated rules; {len(detected)} conditions are currently active.")

include_resolved = st.sidebar.checkbox("Include resolved alerts", False)
frame = alert_view(DEFAULT_DB_PATH, include_resolved=include_resolved)

if frame.empty:
    st.success("No alerts match the current view.")
else:
    a, b, c, d = st.columns(4)
    a.metric("Open alerts", int((frame.status == "open").sum()))
    b.metric("Critical", int(((frame.severity == "critical") & (frame.status != "resolved")).sum()))
    c.metric("High", int(((frame.severity == "high") & (frame.status != "resolved")).sum()))
    d.metric("Resolved shown", int((frame.status == "resolved").sum()))
    counts = frame.groupby(["alert_type", "severity"], as_index=False).size()
    fig = px.bar(counts, x="alert_type", y="size", color="severity", title="Alerts by rule",
                 color_discrete_map={"critical": "#d62728", "high": "#ef6c00", "medium": "#fbc02d", "low": "#2ca02c"})
    fig.update_layout(xaxis_title=None, yaxis_title="Alerts")
    st.plotly_chart(fig, width="stretch")
    st.dataframe(frame, hide_index=True, width="stretch", height=520)

st.caption("Rules are idempotent: repeated runs update existing alerts instead of creating duplicates.")
