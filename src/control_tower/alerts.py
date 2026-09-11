from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from .config import DEFAULT_DB_PATH
from .db import read_frame, transaction


MANAGED_ALERT_TYPES = (
    "performance_drop", "partner_risk", "coverage_critical",
    "complaint_spike", "elite_candidate", "quality_review",
)


def detect_alerts(db_path: str | Path = DEFAULT_DB_PATH, *, as_of: date | None = None) -> pd.DataFrame:
    as_of = as_of or date.today()
    previous_date = as_of - timedelta(days=30)
    now = datetime.now().replace(microsecond=0).isoformat()
    rows: list[dict] = []

    scores = read_frame(
        """
        SELECT current.partner_id, p.name, current.reliability_score current_score,
               current.tier, current.mission_count, current.complaint_rate,
               previous.reliability_score previous_score
        FROM partner_score_snapshots current
        JOIN partners p ON p.partner_id = current.partner_id
        LEFT JOIN partner_score_snapshots previous
          ON previous.partner_id = current.partner_id
         AND previous.snapshot_date = :previous_date
         AND previous.window_days = current.window_days
        WHERE current.snapshot_date = :as_of AND current.window_days = 90
        """,
        {"as_of": as_of.isoformat(), "previous_date": previous_date.isoformat()},
        db_path,
    )
    for row in scores.itertuples(index=False):
        if pd.notna(row.previous_score) and row.previous_score - row.current_score > 15:
            rows.append(_alert(
                "performance_drop", "high", now, f"partner:{row.partner_id}:performance_drop",
                partner_id=row.partner_id,
                message=f"{row.name}'s score fell {row.previous_score - row.current_score:.1f} points in 30 days.",
            ))
        if row.tier == "Risk" and row.mission_count >= 10:
            rows.append(_alert(
                "partner_risk", "high", now, f"partner:{row.partner_id}:risk",
                partner_id=row.partner_id,
                message=f"{row.name} is in the Risk tier with a score of {row.current_score:.1f}.",
            ))
        if pd.notna(row.complaint_rate) and row.complaint_rate > 0.05 and row.mission_count >= 20:
            rows.append(_alert(
                "complaint_spike", "high", now, f"partner:{row.partner_id}:complaints",
                partner_id=row.partner_id,
                message=f"{row.name}'s complaint rate is {row.complaint_rate:.1%} over the scoring window.",
            ))

    elite = read_frame(
        """
        SELECT s.partner_id, p.name, MIN(s.reliability_score) min_score, COUNT(*) months
        FROM partner_score_snapshots s
        JOIN partners p ON p.partner_id = s.partner_id
        WHERE s.snapshot_date IN (:d0, :d1, :d2) AND s.window_days = 90
        GROUP BY s.partner_id, p.name
        HAVING COUNT(*) = 3 AND MIN(s.reliability_score) >= 95
        """,
        {
            "d0": as_of.isoformat(),
            "d1": (as_of - timedelta(days=30)).isoformat(),
            "d2": (as_of - timedelta(days=60)).isoformat(),
        },
        db_path,
    )
    for row in elite.itertuples(index=False):
        rows.append(_alert(
            "elite_candidate", "low", now, f"partner:{row.partner_id}:elite",
            partner_id=row.partner_id,
            message=f"{row.name} has maintained an Elite score for three snapshots.",
        ))

    coverage = read_frame(
        """
        SELECT c.zone_id, z.city, c.target_date, c.mission_type, c.coverage_ratio
        FROM coverage_snapshots c JOIN zones z ON z.zone_id = c.zone_id
        WHERE c.target_date >= :as_of AND c.target_date < :end AND c.coverage_ratio < 0.85
        """,
        {"as_of": as_of.isoformat(), "end": (as_of + timedelta(days=7)).isoformat()},
        db_path,
    )
    for row in coverage.itertuples(index=False):
        rows.append(_alert(
            "coverage_critical", "critical", now,
            f"zone:{row.zone_id}:{row.target_date}:{row.mission_type}:coverage",
            zone_id=row.zone_id,
            message=f"{row.city} is critically under-covered for {row.mission_type} on {row.target_date} ({row.coverage_ratio:.2f}).",
        ))

    quality = read_frame(
        """
        SELECT qa.mission_id, qa.risk_probability, a.partner_id, m.zone_id
        FROM quality_assessments qa
        JOIN missions m ON m.mission_id = qa.mission_id
        LEFT JOIN assignments a ON a.mission_id = qa.mission_id
        WHERE qa.risk_probability >= 0.75
          AND date(m.appointment_at) >= :recent
        ORDER BY qa.risk_probability DESC
        LIMIT 50
        """,
        {"recent": (as_of - timedelta(days=14)).isoformat()},
        db_path,
    )
    for row in quality.itertuples(index=False):
        rows.append(_alert(
            "quality_review", "medium", now, f"mission:{row.mission_id}:quality",
            partner_id=row.partner_id, mission_id=row.mission_id, zone_id=row.zone_id,
            message=f"Mission {row.mission_id} has a {row.risk_probability:.0%} predicted quality-risk probability.",
        ))

    current_keys = {row["dedupe_key"] for row in rows}
    placeholders = ",".join("?" for _ in MANAGED_ALERT_TYPES)
    with transaction(db_path) as connection:
        existing = connection.execute(
            f"SELECT alert_id, dedupe_key FROM alerts WHERE status != 'resolved' AND alert_type IN ({placeholders})",
            MANAGED_ALERT_TYPES,
        ).fetchall()
        for alert in rows:
            connection.execute(
                """
                INSERT INTO alerts (
                    partner_id, mission_id, zone_id, alert_type, severity,
                    first_seen_at, last_seen_at, status, message, dedupe_key
                ) VALUES (
                    :partner_id, :mission_id, :zone_id, :alert_type, :severity,
                    :first_seen_at, :last_seen_at, :status, :message, :dedupe_key
                )
                ON CONFLICT(dedupe_key) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    severity = excluded.severity,
                    message = excluded.message,
                    status = 'open',
                    resolved_at = NULL
                """,
                alert,
            )
        for existing_alert in existing:
            if existing_alert["dedupe_key"] not in current_keys:
                connection.execute(
                    "UPDATE alerts SET status = 'resolved', resolved_at = ?, last_seen_at = ? WHERE alert_id = ?",
                    (now, now, existing_alert["alert_id"]),
                )
    return pd.DataFrame(rows)


def _alert(
    alert_type: str,
    severity: str,
    timestamp: str,
    dedupe_key: str,
    *,
    partner_id: int | None = None,
    mission_id: int | None = None,
    zone_id: int | None = None,
    message: str,
) -> dict:
    return {
        "partner_id": partner_id,
        "mission_id": mission_id,
        "zone_id": zone_id,
        "alert_type": alert_type,
        "severity": severity,
        "first_seen_at": timestamp,
        "last_seen_at": timestamp,
        "status": "open",
        "message": message,
        "dedupe_key": dedupe_key,
    }


def alert_view(db_path: str | Path = DEFAULT_DB_PATH, *, include_resolved: bool = False) -> pd.DataFrame:
    status_filter = "" if include_resolved else "WHERE a.status != 'resolved'"
    return read_frame(
        f"""
        SELECT a.alert_id, a.severity, a.alert_type, a.status, a.message,
               a.first_seen_at, a.last_seen_at, a.partner_id, p.name partner,
               a.zone_id, z.city, a.mission_id
        FROM alerts a
        LEFT JOIN partners p ON p.partner_id = a.partner_id
        LEFT JOIN zones z ON z.zone_id = a.zone_id
        {status_filter}
        ORDER BY CASE a.severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                 a.last_seen_at DESC
        """,
        (),
        db_path,
    )

