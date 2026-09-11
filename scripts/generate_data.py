from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.synthetic import generate_synthetic_data  # noqa: E402


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--partners", type=int, default=350)
    parser.add_argument("--missions", type=int, default=15_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    print(asdict(generate_synthetic_data(partner_count=args.partners, mission_count=args.missions, seed=args.seed)))

