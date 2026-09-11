from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .config import (
    CONFIDENCE_PRIOR_MISSIONS,
    DEFAULT_DB_PATH,
    MIN_MISSIONS_FOR_TIER,
    SCORE_WEIGHTS,
)
from .db import transaction
from .kpis import calculate_partner_kpis


def delivery_score(hours: pd.Series | float) -> pd.Series | float:
    """Map 12 hours or less to 100 and 72 hours or more to 0."""
    return np.clip(100.0 - (np.asarray(hours) - 12.0) * (100.0 / 60.0), 0.0, 100.0)


def tier_for(score: float, mission_count: int) -> str:
    if mission_count < MIN_MISSIONS_FOR_TIER or np.isnan(score):
        return "Insufficient data"
    if score >= 95:
        return "Elite"
    if score >= 90:
        return "Gold"
    if score >= 80:
        return "Silver"
    if score >= 70:
        return "Bronze"
    return "Risk"


def score_partner_frame(kpis: pd.DataFrame) -> pd.DataFrame:
    result = kpis.copy()
    rate_columns = ["acceptance_rate", "punctuality_rate", "compliance_rate", "no_show_rate"]
    priors = {}
    for column in rate_columns:
        prior = result[column].mean(skipna=True)
        priors[column] = float(prior) if pd.notna(prior) else (0.0 if column == "no_show_rate" else 0.75)
    delivery_prior = result["average_delivery_hours"].mean(skipna=True)
    delivery_prior = float(delivery_prior) if pd.notna(delivery_prior) else 36.0

    acceptance = result["acceptance_rate"].fillna(priors["acceptance_rate"]) * 100
    punctuality = result["punctuality_rate"].fillna(priors["punctuality_rate"]) * 100
    compliance = result["compliance_rate"].fillna(priors["compliance_rate"]) * 100
    no_show = (1 - result["no_show_rate"].fillna(priors["no_show_rate"])) * 100
    delivery = delivery_score(result["average_delivery_hours"].fillna(delivery_prior))

    result["acceptance_score"] = acceptance
    result["punctuality_score"] = punctuality
    result["compliance_score"] = compliance
    result["delivery_score"] = delivery
    result["no_show_score"] = no_show
    result["raw_score"] = (
        SCORE_WEIGHTS["acceptance"] * acceptance
        + SCORE_WEIGHTS["punctuality"] * punctuality
        + SCORE_WEIGHTS["compliance"] * compliance
        + SCORE_WEIGHTS["delivery"] * delivery
        + SCORE_WEIGHTS["no_show"] * no_show
    )

    weights = result["mission_count"].clip(lower=1)
    network_prior = float(np.average(result["raw_score"], weights=weights))
    result["confidence"] = result["mission_count"] / (result["mission_count"] + CONFIDENCE_PRIOR_MISSIONS)
    result["reliability_score"] = (
        result["confidence"] * result["raw_score"] + (1 - result["confidence"]) * network_prior
    ).round(2)
    result["raw_score"] = result["raw_score"].round(2)
    result["tier"] = [
        tier_for(float(score), int(count))
        for score, count in zip(result["reliability_score"], result["mission_count"])
    ]
    return result


def calculate_and_store_scores(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    as_of: date | None = None,
    window_days: int = 90,
) -> pd.DataFrame:
    as_of = as_of or date.today()
    scored = score_partner_frame(calculate_partner_kpis(db_path, as_of=as_of, window_days=window_days))
    stored = scored[[
        "partner_id", "acceptance_rate", "punctuality_rate", "compliance_rate",
        "average_delivery_hours", "no_show_rate", "complaint_rate", "mission_count",
        "raw_score", "confidence", "reliability_score", "tier",
    ]].copy()
    stored.insert(1, "snapshot_date", as_of.isoformat())
    stored.insert(2, "window_days", window_days)
    with transaction(db_path) as connection:
        connection.execute(
            "DELETE FROM partner_score_snapshots WHERE snapshot_date = ? AND window_days = ?",
            (as_of.isoformat(), window_days),
        )
        stored.to_sql("partner_score_snapshots", connection, if_exists="append", index=False)
    return scored


def build_score_history(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    as_of: date | None = None,
    snapshots: int = 4,
    spacing_days: int = 30,
    window_days: int = 90,
) -> pd.DataFrame:
    as_of = as_of or date.today()
    results = []
    for offset in reversed(range(snapshots)):
        snapshot_date = as_of - timedelta(days=offset * spacing_days)
        frame = calculate_and_store_scores(db_path, as_of=snapshot_date, window_days=window_days)
        frame["snapshot_date"] = snapshot_date.isoformat()
        results.append(frame)
    return pd.concat(results, ignore_index=True)
