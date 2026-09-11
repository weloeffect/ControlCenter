from __future__ import annotations

import sys
from pathlib import Path

import plotly.express as px
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app._common import page_setup, require_database

page_setup("Check and Visit Operations Center", "🎛️")

from control_tower.config import DEFAULT_DB_PATH  # noqa: E402
from control_tower.db import database_ready, read_frame  # noqa: E402
from control_tower.pipeline import build_demo  # noqa: E402

st.title("Check and Visit Operations Center")

if not database_ready(DEFAULT_DB_PATH):
    st.info("Build the reproducible demo dataset to start exploring the control tower.")
    if st.button("Build demo data", type="primary"):
        with st.status("Building the complete demo…", expanded=True) as status:
            summary = build_demo(DEFAULT_DB_PATH)
            st.write(f"Generated {summary['generated'].missions:,} missions.")
            st.write(f"Calculated {summary['score_rows']:,} partner score snapshots.")
            st.write(f"Created {summary['coverage_rows']:,} coverage forecasts.")
            status.update(label="Demo ready", state="complete")
        st.rerun()
    st.stop()

require_database()

latest = read_frame(
    """
    SELECT MAX(snapshot_date) snapshot_date FROM partner_score_snapshots WHERE window_days = 90
    """,
    (), DEFAULT_DB_PATH,
).iloc[0, 0]
summary = read_frame(
    """
    SELECT
      (SELECT COUNT(*) FROM partners WHERE status = 'active') active_partners,
      SUM(mission_count) scored_missions,
      SUM(acceptance_rate * mission_count) / NULLIF(SUM(mission_count), 0) acceptance_rate
    FROM partner_score_snapshots
    WHERE snapshot_date = :latest AND window_days = 90
    """,
    {"latest": latest}, DEFAULT_DB_PATH,
).iloc[0]

metrics = [
    ("Active partners", f"{int(summary.active_partners):,}"),
    ("Missions · 90d", f"{int(summary.scored_missions):,}"),
    ("Acceptance", f"{summary.acceptance_rate:.1%}"),
]
cols = st.columns(len(metrics))
for column, (label, value) in zip(cols, metrics):
    column.metric(label, value)

tier_counts = read_frame(
    """
    SELECT tier, COUNT(*) partners FROM partner_score_snapshots
    WHERE snapshot_date = :latest AND window_days = 90 GROUP BY tier
    """,
    {"latest": latest}, DEFAULT_DB_PATH,
)
figure = px.bar(tier_counts, x="tier", y="partners", color="tier", title="Partner tiers",
                category_orders={"tier": ["Elite", "Gold", "Silver", "Bronze", "Risk", "Insufficient data"]})
figure.update_layout(showlegend=False, xaxis_title=None)
st.plotly_chart(figure, width="stretch")

st.subheader("Top partners")
top = read_frame(
    """
    SELECT p.name Partner, z.city City, ROUND(s.reliability_score, 1) Score, s.tier Tier,
           s.mission_count Missions
    FROM partner_score_snapshots s JOIN partners p USING(partner_id)
    JOIN zones z ON z.zone_id = p.home_zone_id
    WHERE s.snapshot_date = :latest AND s.window_days = 90 AND s.mission_count >= 10
    ORDER BY s.reliability_score DESC LIMIT 10
    """,
    {"latest": latest}, DEFAULT_DB_PATH,
)
st.dataframe(top, hide_index=True, width="stretch")
