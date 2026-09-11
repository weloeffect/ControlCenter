from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from control_tower.config import DEFAULT_DB_PATH  # noqa: E402
from control_tower.pipeline import build_demo  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the complete synthetic control-tower demo")
    parser.add_argument("--partners", type=int, default=350)
    parser.add_argument("--missions", type=int, default=15_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-quality-model", action="store_true")
    args = parser.parse_args()
    result = build_demo(
        DEFAULT_DB_PATH,
        partner_count=args.partners,
        mission_count=args.missions,
        seed=args.seed,
        train_quality=not args.skip_quality_model,
    )
    result["generated"] = asdict(result["generated"])
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

