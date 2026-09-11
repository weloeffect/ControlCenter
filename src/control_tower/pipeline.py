from __future__ import annotations

from datetime import date
from pathlib import Path

from .alerts import detect_alerts
from .config import DEFAULT_DB_PATH, MODEL_PATH
from .coverage import calculate_coverage_forecast
from .quality import assess_quality_risk, train_quality_model
from .scoring import build_score_history
from .synthetic import GenerationSummary, generate_synthetic_data


def build_demo(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    partner_count: int = 350,
    mission_count: int = 15_000,
    seed: int = 42,
    as_of: date | None = None,
    train_quality: bool = True,
) -> dict:
    as_of = as_of or date.today()
    generated: GenerationSummary = generate_synthetic_data(
        db_path,
        partner_count=partner_count,
        mission_count=mission_count,
        seed=seed,
        as_of=as_of,
    )
    history = build_score_history(db_path, as_of=as_of)
    coverage = calculate_coverage_forecast(db_path, as_of=as_of)
    quality_metrics = None
    if train_quality:
        quality_metrics = train_quality_model(db_path, model_path=MODEL_PATH)
        assess_quality_risk(db_path, model_path=MODEL_PATH)
    alerts = detect_alerts(db_path, as_of=as_of)
    return {
        "generated": generated,
        "score_rows": len(history),
        "coverage_rows": len(coverage),
        "alert_rows": len(alerts),
        "quality_metrics": quality_metrics,
    }
