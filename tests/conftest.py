from __future__ import annotations

from datetime import date

import pytest

from control_tower.coverage import calculate_coverage_forecast
from control_tower.scoring import build_score_history
from control_tower.synthetic import generate_synthetic_data


@pytest.fixture(scope="session")
def demo_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("control_tower") / "test.db"
    generate_synthetic_data(path, partner_count=80, mission_count=2_000, history_days=120, seed=7)
    build_score_history(path, as_of=date.today())
    calculate_coverage_forecast(path, as_of=date.today())
    return path

