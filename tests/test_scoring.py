import pandas as pd

from control_tower.kpis import calculate_partner_kpis
from control_tower.scoring import score_partner_frame, tier_for


def test_rates_and_scores_stay_in_bounds(demo_db):
    scored = score_partner_frame(calculate_partner_kpis(demo_db))
    assert scored["reliability_score"].between(0, 100).all()
    for column in ["acceptance_rate", "punctuality_rate", "compliance_rate", "no_show_rate"]:
        assert scored[column].dropna().between(0, 1).all()


def test_no_show_rate_is_penalized():
    base = {
        "partner_id": [1, 2], "name": ["A", "B"], "city": ["X", "X"], "postal_code": ["00000", "00000"],
        "status": ["active", "active"], "valid_offers": [40, 40], "accepted_offers": [36, 36],
        "timed_out_offers": [0, 0], "acceptance_rate": [.9, .9], "scheduled_count": [30, 30],
        "mission_count": [30, 30], "no_show_count": [0, 9], "no_show_rate": [0.0, .3],
        "punctuality_rate": [.9, .9], "compliance_rate": [.9, .9],
        "average_delivery_hours": [20.0, 20.0], "complaint_rate": [.01, .01], "rework_count": [1, 1],
    }
    scored = score_partner_frame(pd.DataFrame(base))
    assert scored.loc[0, "reliability_score"] > scored.loc[1, "reliability_score"]


def test_small_samples_are_not_tiered():
    assert tier_for(99.0, 2) == "Insufficient data"

