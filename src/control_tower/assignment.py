from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ASSIGNMENT_WEIGHTS, DEFAULT_DB_PATH
from .db import read_frame, transaction


def rank_partners(
    zone_id: int,
    mission_type: str,
    appointment_at: datetime,
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    mission_id: int | None = None,
    limit: int = 5,
    save: bool = False,
) -> pd.DataFrame:
    """Apply eligibility constraints, then rank candidates on a 0–100 scale."""
    query = """
    WITH latest_scores AS (
        SELECT s.*
        FROM partner_score_snapshots s
        JOIN (
            SELECT partner_id, MAX(snapshot_date) snapshot_date
            FROM partner_score_snapshots
            WHERE snapshot_date <= :appointment_date
            GROUP BY partner_id
        ) latest ON latest.partner_id = s.partner_id AND latest.snapshot_date = s.snapshot_date
        WHERE s.window_days = 90
    ), experience AS (
        SELECT a.partner_id, COUNT(*) mission_experience
        FROM assignments a
        JOIN missions m ON m.mission_id = a.mission_id
        WHERE a.status = 'completed' AND m.mission_type = :mission_type
        GROUP BY a.partner_id
    )
    SELECT p.partner_id, p.name, p.max_daily_capacity, psz.distance_km,
           a.available_slots, a.booked_slots,
           COALESCE(s.reliability_score, 75.0) reliability_score,
           COALESCE(s.tier, 'Insufficient data') tier,
           COALESCE(e.mission_experience, 0) mission_experience
    FROM partners p
    JOIN partner_capabilities pc ON pc.partner_id = p.partner_id AND pc.mission_type = :mission_type
    JOIN partner_service_zones psz ON psz.partner_id = p.partner_id AND psz.zone_id = :zone_id
    JOIN availability a ON a.partner_id = p.partner_id AND a.date = :appointment_date
    LEFT JOIN latest_scores s ON s.partner_id = p.partner_id
    LEFT JOIN experience e ON e.partner_id = p.partner_id
    WHERE p.status = 'active'
      AND p.declared_availability = 1
      AND a.declared_available = 1
      AND a.actual_available = 1
      AND a.available_slots > a.booked_slots
    """
    params = {
        "zone_id": int(zone_id),
        "mission_type": mission_type,
        "appointment_date": appointment_at.date().isoformat(),
    }
    candidates = read_frame(query, params, db_path)
    if candidates.empty:
        return candidates

    spare = (candidates["available_slots"] - candidates["booked_slots"]).clip(lower=0)
    candidates["reliability_component"] = candidates["reliability_score"].clip(0, 100)
    candidates["availability_component"] = 100.0
    candidates["distance_component"] = 100.0 * np.exp(-candidates["distance_km"] / 35.0)
    candidates["workload_component"] = 100.0 * spare / candidates["available_slots"].clip(lower=1)
    candidates["experience_component"] = 100.0 * (1 - np.exp(-candidates["mission_experience"] / 12.0))
    candidates["assignment_score"] = sum(
        ASSIGNMENT_WEIGHTS[name] * candidates[f"{name}_component"]
        for name in ASSIGNMENT_WEIGHTS
    )
    candidates = candidates.sort_values(
        ["assignment_score", "reliability_score", "distance_km"],
        ascending=[False, False, True],
    ).head(limit).reset_index(drop=True)
    candidates.insert(0, "rank", np.arange(1, len(candidates) + 1))
    numeric = [column for column in candidates.columns if column.endswith("_component") or column == "assignment_score"]
    candidates[numeric] = candidates[numeric].round(2)

    if save:
        stored = candidates[[
            "partner_id", "rank", "reliability_component", "availability_component",
            "distance_component", "workload_component", "experience_component", "assignment_score",
        ]].copy()
        stored.insert(0, "appointment_at", appointment_at.replace(microsecond=0).isoformat())
        stored.insert(0, "mission_type", mission_type)
        stored.insert(0, "zone_id", int(zone_id))
        stored.insert(0, "mission_id", mission_id)
        stored["generated_at"] = datetime.now().replace(microsecond=0).isoformat()
        with transaction(db_path) as connection:
            stored.to_sql("assignment_recommendations", connection, if_exists="append", index=False)
    return candidates


def recommendation_reasons(row: pd.Series) -> list[str]:
    reasons = []
    if row["reliability_component"] >= 90:
        reasons.append("Very high reliability")
    elif row["reliability_component"] >= 80:
        reasons.append("Strong reliability")
    if row["distance_km"] <= 15:
        reasons.append("Close to the mission")
    if row["workload_component"] >= 60:
        reasons.append("Good remaining capacity")
    if row["experience_component"] >= 75:
        reasons.append("Extensive experience with this mission type")
    return reasons or ["Best overall balance among eligible partners"]
