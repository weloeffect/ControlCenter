from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "control_tower.db"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"
MODEL_PATH = PROJECT_ROOT / "models" / "quality_risk.joblib"

MISSION_TYPES = ("apartment_inspection", "house_inspection", "inventory_check")
MISSION_LABELS = {
    "apartment_inspection": "Apartment inspection",
    "house_inspection": "House inspection",
    "inventory_check": "Inventory check",
}

SCORE_WEIGHTS = {
    "acceptance": 0.20,
    "punctuality": 0.20,
    "compliance": 0.30,
    "delivery": 0.15,
    "no_show": 0.15,
}

ASSIGNMENT_WEIGHTS = {
    "reliability": 0.35,
    "availability": 0.25,
    "distance": 0.20,
    "workload": 0.10,
    "experience": 0.10,
}

MIN_MISSIONS_FOR_TIER = 10
CONFIDENCE_PRIOR_MISSIONS = 20
PUNCTUALITY_GRACE_MINUTES = 15
