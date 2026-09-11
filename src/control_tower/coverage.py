from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DEFAULT_DB_PATH, MISSION_TYPES
from .db import read_frame, transaction


def coverage_status(ratio: float) -> str:
    if ratio >= 1.20:
        return "healthy"
    if ratio >= 0.90:
        return "watch"
    return "critical"


def calculate_coverage_forecast(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    as_of: date | None = None,
    horizon_days: int = 7,
    lookback_days: int = 56,
) -> pd.DataFrame:
    """Forecast demand with weekday averages and allocate capacity without double counting.

    Each partner's spare slots are divided across every service-zone/capability
    combination they can serve. It is a conservative planning view, not an optimizer.
    """
    as_of = as_of or date.today()
    history_start = as_of - timedelta(days=lookback_days)
    demand = read_frame(
        """
        SELECT zone_id, mission_type, date(appointment_at) appointment_date, COUNT(*) demand
        FROM missions
        WHERE appointment_at >= :start AND appointment_at < :end
        GROUP BY zone_id, mission_type, date(appointment_at)
        """,
        {"start": history_start.isoformat(), "end": as_of.isoformat()},
        db_path,
    )
    if not demand.empty:
        demand["appointment_date"] = pd.to_datetime(demand["appointment_date"])
        demand["weekday"] = demand["appointment_date"].dt.weekday

    zones = read_frame("SELECT zone_id FROM zones ORDER BY zone_id", (), db_path)
    capacity_source = read_frame(
        """
        SELECT a.partner_id, a.date, a.actual_available, a.available_slots, a.booked_slots,
               psz.zone_id, pc.mission_type,
               COUNT(*) OVER (PARTITION BY a.partner_id) allocation_count
        FROM availability a
        JOIN partners p ON p.partner_id = a.partner_id AND p.status = 'active'
        JOIN partner_service_zones psz ON psz.partner_id = a.partner_id
        JOIN partner_capabilities pc ON pc.partner_id = a.partner_id
        WHERE a.date >= :start AND a.date < :end
        """,
        {
            "start": as_of.isoformat(),
            "end": (as_of + timedelta(days=horizon_days)).isoformat(),
        },
        db_path,
    )
    if not capacity_source.empty:
        # allocation_count includes every date; recalculate per partner/date.
        allocation_counts = capacity_source.groupby(["partner_id", "date"])["zone_id"].transform("count")
        spare = (capacity_source["available_slots"] - capacity_source["booked_slots"]).clip(lower=0)
        capacity_source["allocated_capacity"] = (
            capacity_source["actual_available"] * spare / allocation_counts.clip(lower=1)
        )
        capacity = capacity_source.groupby(["date", "zone_id", "mission_type"], as_index=False)["allocated_capacity"].sum()
    else:
        capacity = pd.DataFrame(columns=["date", "zone_id", "mission_type", "allocated_capacity"])

    rows: list[dict] = []
    generated_at = datetime.now().replace(microsecond=0).isoformat()
    weekday_occurrences = {
        weekday: sum((history_start + timedelta(days=i)).weekday() == weekday for i in range(lookback_days))
        for weekday in range(7)
    }
    for day_offset in range(horizon_days):
        target = as_of + timedelta(days=day_offset)
        for zone_id in zones["zone_id"]:
            for mission_type in MISSION_TYPES:
                if demand.empty:
                    expected = 0.0
                else:
                    selector = (
                        (demand["zone_id"] == zone_id)
                        & (demand["mission_type"] == mission_type)
                        & (demand["weekday"] == target.weekday())
                    )
                    expected = float(demand.loc[selector, "demand"].sum()) / max(weekday_occurrences[target.weekday()], 1)
                # A small buffer prevents a zero forecast from hiding emerging demand.
                expected = max(expected, 0.25)
                selector = (
                    (capacity["date"] == target.isoformat())
                    & (capacity["zone_id"] == zone_id)
                    & (capacity["mission_type"] == mission_type)
                ) if not capacity.empty else np.array([], dtype=bool)
                available = float(capacity.loc[selector, "allocated_capacity"].sum()) if len(selector) else 0.0
                ratio = available / expected
                rows.append({
                    "zone_id": int(zone_id),
                    "target_date": target.isoformat(),
                    "mission_type": mission_type,
                    "available_capacity": round(available, 2),
                    "expected_demand": round(expected, 2),
                    "coverage_ratio": round(ratio, 3),
                    "coverage_status": coverage_status(ratio),
                    "forecast_generated_at": generated_at,
                })
    result = pd.DataFrame(rows)
    with transaction(db_path) as connection:
        connection.execute(
            "DELETE FROM coverage_snapshots WHERE target_date >= ? AND target_date < ?",
            (as_of.isoformat(), (as_of + timedelta(days=horizon_days)).isoformat()),
        )
        result.to_sql("coverage_snapshots", connection, if_exists="append", index=False)
    return result


def coverage_view(db_path: str | Path = DEFAULT_DB_PATH, *, target_date: date | None = None) -> pd.DataFrame:
    target_date = target_date or date.today()
    return read_frame(
        """
        SELECT c.*, z.city, z.postal_code, z.latitude, z.longitude
        FROM coverage_snapshots c
        JOIN zones z ON z.zone_id = c.zone_id
        WHERE c.target_date = :target_date
        ORDER BY c.coverage_ratio, z.city, c.mission_type
        """,
        {"target_date": target_date.isoformat()},
        db_path,
    )

