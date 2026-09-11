from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from .config import DEFAULT_DB_PATH, PUNCTUALITY_GRACE_MINUTES
from .db import read_frame


def calculate_partner_kpis(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    as_of: date | None = None,
    window_days: int = 90,
) -> pd.DataFrame:
    """Calculate partner KPIs with explicit event-level denominators."""
    as_of = as_of or date.today()
    start = as_of - timedelta(days=window_days - 1)
    end_exclusive = as_of + timedelta(days=1)
    query = f"""
    WITH offer_kpis AS (
        SELECT partner_id,
               SUM(CASE WHEN response_status IN ('accepted', 'refused') THEN 1 ELSE 0 END) valid_offers,
               SUM(CASE WHEN response_status = 'accepted' THEN 1 ELSE 0 END) accepted_offers,
               SUM(CASE WHEN response_status = 'timeout' THEN 1 ELSE 0 END) timed_out_offers
        FROM mission_offers
        WHERE proposed_at >= :start AND proposed_at < :end
        GROUP BY partner_id
    ), mission_kpis AS (
        SELECT a.partner_id,
               COUNT(*) scheduled_count,
               SUM(CASE WHEN a.status = 'completed' THEN 1 ELSE 0 END) mission_count,
               SUM(CASE WHEN a.status = 'no_show' THEN 1 ELSE 0 END) no_show_count,
               AVG(CASE WHEN a.status = 'completed'
                        THEN CASE WHEN datetime(a.arrival_at) <= datetime(m.appointment_at, '+{PUNCTUALITY_GRACE_MINUTES} minutes')
                                  THEN 1.0 ELSE 0.0 END END) punctuality_rate,
               AVG(CASE WHEN a.status = 'completed' THEN 1.0 * m.first_pass_compliant END) compliance_rate,
               AVG(CASE WHEN a.status = 'completed' AND m.delivered_at IS NOT NULL AND m.completed_at IS NOT NULL
                        THEN (julianday(m.delivered_at) - julianday(m.completed_at)) * 24.0 END) average_delivery_hours,
               AVG(CASE WHEN a.status = 'completed' THEN 1.0 * m.customer_complaint END) complaint_rate,
               SUM(CASE WHEN a.status = 'completed' THEN m.rework_count ELSE 0 END) rework_count
        FROM assignments a
        JOIN missions m ON m.mission_id = a.mission_id
        WHERE m.appointment_at >= :start AND m.appointment_at < :end
        GROUP BY a.partner_id
    )
    SELECT p.partner_id, p.name, z.city, z.postal_code, p.status,
           COALESCE(o.valid_offers, 0) valid_offers,
           COALESCE(o.accepted_offers, 0) accepted_offers,
           COALESCE(o.timed_out_offers, 0) timed_out_offers,
           CASE WHEN o.valid_offers > 0 THEN 1.0 * o.accepted_offers / o.valid_offers END acceptance_rate,
           COALESCE(m.scheduled_count, 0) scheduled_count,
           COALESCE(m.mission_count, 0) mission_count,
           COALESCE(m.no_show_count, 0) no_show_count,
           CASE WHEN m.scheduled_count > 0 THEN 1.0 * m.no_show_count / m.scheduled_count END no_show_rate,
           m.punctuality_rate, m.compliance_rate, m.average_delivery_hours,
           m.complaint_rate, COALESCE(m.rework_count, 0) rework_count
    FROM partners p
    JOIN zones z ON z.zone_id = p.home_zone_id
    LEFT JOIN offer_kpis o ON o.partner_id = p.partner_id
    LEFT JOIN mission_kpis m ON m.partner_id = p.partner_id
    ORDER BY p.partner_id
    """
    frame = read_frame(
        query,
        {"start": start.isoformat(), "end": end_exclusive.isoformat()},
        db_path,
    )
    return frame


def network_summary(kpis: pd.DataFrame) -> dict[str, float | int]:
    completed = max(int(kpis["mission_count"].sum()), 1)
    scheduled = max(int(kpis["scheduled_count"].sum()), 1)
    offers = max(int(kpis["valid_offers"].sum()), 1)

    def weighted(column: str, weight: str) -> float:
        valid = kpis[column].notna() & (kpis[weight] > 0)
        if not valid.any():
            return 0.0
        return float((kpis.loc[valid, column] * kpis.loc[valid, weight]).sum() / kpis.loc[valid, weight].sum())

    return {
        "active_partners": int((kpis["status"] == "active").sum()),
        "completed_missions": int(kpis["mission_count"].sum()),
        "acceptance_rate": float(kpis["accepted_offers"].sum() / offers),
        "punctuality_rate": weighted("punctuality_rate", "mission_count"),
        "compliance_rate": weighted("compliance_rate", "mission_count"),
        "no_show_rate": float(kpis["no_show_count"].sum() / scheduled),
        "complaint_rate": weighted("complaint_rate", "mission_count"),
        "average_delivery_hours": weighted("average_delivery_hours", "mission_count"),
        "manual_rework_rate": float(kpis["rework_count"].sum() / completed),
    }

