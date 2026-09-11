from datetime import date, datetime, time, timedelta

from control_tower.assignment import rank_partners
from control_tower.db import transaction


def test_unavailable_partner_is_never_recommended(demo_db):
    appointment = datetime.combine(date.today() + timedelta(days=1), time(14, 0))
    candidates = None
    selected = None
    for zone_id in range(1, 21):
        result = rank_partners(zone_id, "apartment_inspection", appointment, demo_db)
        if not result.empty:
            candidates = result
            selected = int(result.iloc[0].partner_id)
            break
    assert candidates is not None and selected is not None
    with transaction(demo_db) as connection:
        connection.execute(
            "UPDATE availability SET actual_available = 0 WHERE partner_id = ? AND date = ?",
            (selected, appointment.date().isoformat()),
        )
    reranked = rank_partners(zone_id, "apartment_inspection", appointment, demo_db)
    assert selected not in reranked.partner_id.tolist()


def test_assignment_scores_are_ranked(demo_db):
    appointment = datetime.combine(date.today() + timedelta(days=2), time(10, 0))
    result = rank_partners(1, "apartment_inspection", appointment, demo_db)
    if len(result) > 1:
        assert result.assignment_score.is_monotonic_decreasing

