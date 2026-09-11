from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.assignment import rank_partners  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--zone", type=int, default=1)
    parser.add_argument("--mission-type", default="apartment_inspection")
    args = parser.parse_args()
    appointment = datetime.combine(date.today() + timedelta(days=1), time(14, 0))
    print(rank_partners(args.zone, args.mission_type, appointment, save=True).to_string(index=False))

