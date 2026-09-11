from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.alerts import alert_view, detect_alerts  # noqa: E402


if __name__ == "__main__":
    detected = detect_alerts()
    print(f"Active rule conditions: {len(detected)}")
    print(alert_view().head(50).to_string(index=False))

