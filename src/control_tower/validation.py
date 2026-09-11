from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import DEFAULT_DB_PATH
from .db import read_frame


CHECKS = {
    "missing_partner_fields": """
        SELECT COUNT(*) failures FROM partners
        WHERE name IS NULL OR home_zone_id IS NULL OR max_daily_capacity IS NULL OR status IS NULL
    """,
    "duplicate_postal_codes": """
        SELECT COUNT(*) failures FROM (SELECT postal_code FROM zones GROUP BY postal_code HAVING COUNT(*) > 1)
    """,
    "invalid_postal_codes": """
        SELECT COUNT(*) failures FROM zones WHERE length(postal_code) != 5 OR postal_code GLOB '*[^0-9]*'
    """,
    "incoherent_mission_dates": """
        SELECT COUNT(*) failures FROM missions
        WHERE datetime(created_at) >= datetime(appointment_at)
           OR (completed_at IS NOT NULL AND datetime(completed_at) < datetime(appointment_at, '-1 hour'))
           OR (delivered_at IS NOT NULL AND datetime(delivered_at) < datetime(completed_at))
    """,
    "assignments_without_accepted_offer": """
        SELECT COUNT(*) failures FROM assignments a
        WHERE NOT EXISTS (
          SELECT 1 FROM mission_offers o
          WHERE o.mission_id = a.mission_id AND o.partner_id = a.partner_id AND o.response_status = 'accepted'
        )
    """,
    "multiple_accepted_offers": """
        SELECT COUNT(*) failures FROM (
          SELECT mission_id FROM mission_offers WHERE response_status = 'accepted'
          GROUP BY mission_id HAVING COUNT(*) > 1
        )
    """,
    "capacity_overbooked": """
        SELECT COUNT(*) failures FROM availability WHERE booked_slots > available_slots
    """,
    "completed_without_partner": """
        SELECT COUNT(*) failures FROM missions m
        WHERE m.status = 'completed' AND NOT EXISTS (SELECT 1 FROM assignments a WHERE a.mission_id = m.mission_id)
    """,
    "negative_durations": """
        SELECT COUNT(*) failures FROM missions
        WHERE completed_at IS NOT NULL AND delivered_at IS NOT NULL
          AND julianday(delivered_at) < julianday(completed_at)
    """,
}


def validate_database(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    rows = []
    for name, query in CHECKS.items():
        failures = int(read_frame(query, (), db_path).iloc[0, 0])
        rows.append({"check": name, "failures": failures, "status": "pass" if failures == 0 else "fail"})
    return pd.DataFrame(rows)

