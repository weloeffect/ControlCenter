from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.kpis import calculate_partner_kpis, network_summary  # noqa: E402


if __name__ == "__main__":
    frame = calculate_partner_kpis()
    print(frame.head(10).to_string(index=False))
    print(network_summary(frame))

