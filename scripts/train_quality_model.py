from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.quality import assess_quality_risk, train_quality_model  # noqa: E402


if __name__ == "__main__":
    metrics = train_quality_model()
    assessments = assess_quality_risk()
    print(json.dumps(metrics, indent=2))
    print(f"Assessments stored: {len(assessments)}")

