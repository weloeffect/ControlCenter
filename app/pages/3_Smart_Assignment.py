from __future__ import annotations

import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app._common import page_setup, require_database

page_setup("Smart Assignment", "🎯")
require_database()

from control_tower.assignment import rank_partners, recommendation_reasons  # noqa: E402
from control_tower.config import DEFAULT_DB_PATH, MISSION_LABELS  # noqa: E402
from control_tower.db import read_frame  # noqa: E402

st.title("Smart Assignment")
st.caption("Mandatory eligibility filters first; weighted ranking second")

zones = read_frame("SELECT zone_id, city, postal_code FROM zones ORDER BY city", (), DEFAULT_DB_PATH)
zone_labels = {int(row.zone_id): f"{row.city} · {row.postal_code}" for row in zones.itertuples(index=False)}

col1, col2, col3, col4 = st.columns(4)
zone_id = col1.selectbox("Mission area", list(zone_labels), format_func=zone_labels.get)
mission_type = col2.selectbox("Mission type", list(MISSION_LABELS), format_func=MISSION_LABELS.get)
appointment_date = col3.date_input("Date", value=date.today() + timedelta(days=1), min_value=date.today(), max_value=date.today() + timedelta(days=14))
appointment_time = col4.time_input("Time", value=time(14, 0), step=1800)

if st.button("Rank eligible partners", type="primary"):
    appointment_at = datetime.combine(appointment_date, appointment_time)
    candidates = rank_partners(zone_id, mission_type, appointment_at, DEFAULT_DB_PATH, save=True)
    if candidates.empty:
        st.error("No partner satisfies all availability, capacity, zone and capability constraints.")
    else:
        winner = candidates.iloc[0]
        st.success(f"Recommended partner: {winner['name']} · assignment score {winner['assignment_score']:.1f}")
        st.write("Why this candidate leads:")
        for reason in recommendation_reasons(winner):
            st.write(f"• {reason}")
        display = candidates[[
            "rank", "name", "tier", "reliability_score", "distance_km",
            "available_slots", "booked_slots", "mission_experience", "assignment_score",
        ]].rename(columns={
            "rank": "Rank", "name": "Partner", "tier": "Tier", "reliability_score": "Reliability",
            "distance_km": "Distance km", "available_slots": "Slots", "booked_slots": "Booked",
            "mission_experience": "Experience", "assignment_score": "Assignment score",
        })
        st.dataframe(display, hide_index=True, width="stretch")
        with st.expander("See factor contributions"):
            st.dataframe(candidates[["name", "reliability_component", "availability_component", "distance_component",
                                     "workload_component", "experience_component"]], hide_index=True, width="stretch")
