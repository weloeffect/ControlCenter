from __future__ import annotations

from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from .config import DEFAULT_DB_PATH, MODEL_PATH
from .db import read_frame, transaction


NUMERIC_FEATURES = [
    "distance_km", "partner_tenure_days", "appointment_hour", "appointment_weekday",
    "prior_missions", "prior_bad_rate", "max_daily_capacity",
]
CATEGORICAL_FEATURES = ["mission_type"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def quality_training_frame(db_path: str | Path = DEFAULT_DB_PATH) -> pd.DataFrame:
    frame = read_frame(
        """
        SELECT m.mission_id, m.mission_type, m.appointment_at, m.first_pass_compliant,
               m.rework_count, m.customer_complaint, a.partner_id, a.status assignment_status,
               p.registration_date, p.max_daily_capacity, psz.distance_km
        FROM missions m
        JOIN assignments a ON a.mission_id = m.mission_id
        JOIN partners p ON p.partner_id = a.partner_id
        JOIN partner_service_zones psz ON psz.partner_id = a.partner_id AND psz.zone_id = m.zone_id
        WHERE a.status IN ('completed', 'no_show')
        ORDER BY m.appointment_at, m.mission_id
        """,
        (),
        db_path,
    )
    if frame.empty:
        return frame
    frame["appointment_at"] = pd.to_datetime(frame["appointment_at"])
    frame["registration_date"] = pd.to_datetime(frame["registration_date"])
    frame["partner_tenure_days"] = (frame["appointment_at"] - frame["registration_date"]).dt.days.clip(lower=0)
    frame["appointment_hour"] = frame["appointment_at"].dt.hour
    frame["appointment_weekday"] = frame["appointment_at"].dt.weekday
    frame["bad_outcome"] = (
        (frame["assignment_status"] == "no_show")
        | (frame["first_pass_compliant"] == 0)
        | (frame["rework_count"] > 0)
        | (frame["customer_complaint"] == 1)
    ).astype(int)
    grouped = frame.groupby("partner_id", sort=False)
    frame["prior_missions"] = grouped.cumcount()
    prior_bad = grouped["bad_outcome"].cumsum() - frame["bad_outcome"]
    # Beta prior: two problematic outcomes in twenty historical missions.
    frame["prior_bad_rate"] = (prior_bad + 2.0) / (frame["prior_missions"] + 20.0)
    return frame


def train_quality_model(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    model_path: str | Path = MODEL_PATH,
) -> dict[str, float | int | str]:
    frame = quality_training_frame(db_path)
    if len(frame) < 200 or frame["bad_outcome"].nunique() < 2:
        raise ValueError("At least 200 assignments with both outcome classes are required")
    split_index = int(len(frame) * 0.8)
    train, test = frame.iloc[:split_index], frame.iloc[split_index:]
    numeric = Pipeline([
        ("impute", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    categorical = Pipeline([
        ("impute", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore")),
    ])
    model = Pipeline([
        ("preprocess", ColumnTransformer([
            ("numeric", numeric, NUMERIC_FEATURES),
            ("categorical", categorical, CATEGORICAL_FEATURES),
        ])),
        ("classifier", LogisticRegression(max_iter=1_000, class_weight="balanced")),
    ])
    model.fit(train[FEATURES], train["bad_outcome"])
    probabilities = model.predict_proba(test[FEATURES])[:, 1]
    predictions = (probabilities >= 0.5).astype(int)
    metrics: dict[str, float | int | str] = {
        "rows": int(len(frame)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "roc_auc": round(float(roc_auc_score(test["bad_outcome"], probabilities)), 4),
        "brier_score": round(float(brier_score_loss(test["bad_outcome"], probabilities)), 4),
        "accuracy": round(float(accuracy_score(test["bad_outcome"], predictions)), 4),
        "version": datetime.now().strftime("logistic-%Y%m%d%H%M%S"),
        "warning": "Validated only on synthetic data; not evidence of real-world performance.",
    }
    path = Path(model_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": model, "metrics": metrics}, path)
    return metrics


def assess_quality_risk(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    model_path: str | Path = MODEL_PATH,
) -> pd.DataFrame:
    payload = joblib.load(model_path)
    frame = quality_training_frame(db_path)
    probabilities = payload["model"].predict_proba(frame[FEATURES])[:, 1]
    result = pd.DataFrame({
        "mission_id": frame["mission_id"].astype(int),
        "risk_probability": np.round(probabilities, 4),
    })
    result["risk_level"] = pd.cut(
        result["risk_probability"], bins=[-0.01, 0.35, 0.65, 1.0], labels=["low", "medium", "high"]
    ).astype(str)
    result["model_version"] = payload["metrics"]["version"]
    result["assessed_at"] = datetime.now().replace(microsecond=0).isoformat()
    with transaction(db_path) as connection:
        connection.execute("DELETE FROM quality_assessments")
        result.to_sql("quality_assessments", connection, if_exists="append", index=False)
    return result

