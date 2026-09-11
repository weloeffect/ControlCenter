from control_tower.alerts import detect_alerts
from control_tower.coverage import coverage_status, coverage_view
from control_tower.db import table_count


def test_coverage_thresholds():
    assert coverage_status(1.2) == "healthy"
    assert coverage_status(0.9) == "watch"
    assert coverage_status(0.899) == "critical"


def test_coverage_is_non_negative(demo_db):
    frame = coverage_view(demo_db)
    assert (frame.available_capacity >= 0).all()
    assert (frame.expected_demand > 0).all()
    assert (frame.coverage_ratio >= 0).all()


def test_alert_runs_are_idempotent(demo_db):
    detect_alerts(demo_db)
    first = table_count("alerts", demo_db)
    detect_alerts(demo_db)
    second = table_count("alerts", demo_db)
    assert first == second

