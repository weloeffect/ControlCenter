from control_tower.db import read_frame, table_count
from control_tower.validation import validate_database


def test_expected_data_volume(demo_db):
    assert table_count("partners", demo_db) == 80
    assert table_count("missions", demo_db) == 2_000
    assert table_count("mission_offers", demo_db) >= table_count("assignments", demo_db)


def test_synthetic_data_passes_integrity_checks(demo_db):
    checks = validate_database(demo_db)
    assert checks["failures"].sum() == 0, checks.to_dict(orient="records")


def test_one_assignment_per_mission(demo_db):
    duplicated = read_frame(
        "SELECT mission_id FROM assignments GROUP BY mission_id HAVING COUNT(*) > 1", (), demo_db
    )
    assert duplicated.empty

