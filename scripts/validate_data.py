from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.validation import validate_database  # noqa: E402


if __name__ == "__main__":
    checks = validate_database()
    print(checks.to_string(index=False))
    raise SystemExit(1 if (checks.status == "fail").any() else 0)

