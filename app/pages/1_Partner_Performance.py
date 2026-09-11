from __future__ import annotations

import plotly.express as px
import streamlit as st

from app._common import page_setup, require_database

page_setup("Partner Performance", "🏅")
require_database()

from control_tower.config import DEFAULT_DB_PATH  # noqa: E402
from control_tower.db import read_frame  # noqa: E402

st.title("Partner Performance")

latest = read_frame("SELECT MAX(snapshot_date) d FROM partner_score_snapshots WHERE window_days=90", (), DEFAULT_DB_PATH).iloc[0, 0]
frame = read_frame(
    """
    WITH prior AS (
      SELECT partner_id, reliability_score prior_score FROM partner_score_snapshots
      WHERE snapshot_date = date(:latest, '-30 days') AND window_days = 90
    )
    SELECT p.name Partner, z.city City, z.postal_code "Postal code", s.tier Tier,
           s.reliability_score Score, ROUND(s.reliability_score - prior.prior_score, 1) Trend,
           s.acceptance_rate "Acceptance rate", s.punctuality_rate "Punctuality rate",
           s.compliance_rate "Compliance rate", s.no_show_rate "No-show rate",
           ROUND(s.average_delivery_hours, 1) "Delivery hours", s.complaint_rate "Complaint rate",
           s.mission_count Missions, ROUND(s.confidence, 2) Confidence
    FROM partner_score_snapshots s JOIN partners p USING(partner_id)
    JOIN zones z ON z.zone_id = p.home_zone_id LEFT JOIN prior USING(partner_id)
    WHERE s.snapshot_date = :latest AND s.window_days = 90
    """,
    {"latest": latest}, DEFAULT_DB_PATH,
)

city = st.sidebar.multiselect("City", sorted(frame.City.unique()))
tier = st.sidebar.multiselect("Tier", ["Elite", "Gold", "Silver", "Bronze", "Risk", "Insufficient data"])
minimum = st.sidebar.slider("Minimum mission count", 0, int(frame.Missions.max()), 10)
filtered = frame[frame.Missions >= minimum]
if city:
    filtered = filtered[filtered.City.isin(city)]
if tier:
    filtered = filtered[filtered.Tier.isin(tier)]

a, b = st.columns(2)
a.metric("Partners shown", len(filtered))
b.metric("Average score", f"{filtered.Score.mean():.1f}" if len(filtered) else "—")

fig = px.histogram(filtered, x="Score", color="Tier", nbins=25, title="Score distribution")
st.plotly_chart(fig, width="stretch")

display = filtered.sort_values("Score", ascending=False).copy()
for column in ["Acceptance rate", "Punctuality rate", "Compliance rate", "No-show rate", "Complaint rate"]:
    display[column] = display[column].map(lambda value: "—" if value != value else f"{value:.1%}")
st.dataframe(display, hide_index=True, width="stretch", height=520)
