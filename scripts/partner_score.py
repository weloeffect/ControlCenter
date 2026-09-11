from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.scoring import build_score_history  # noqa: E402


if __name__ == "__main__":
    frame = build_score_history()
    print(frame.sort_values("reliability_score", ascending=False).head(20).to_string(index=False))

