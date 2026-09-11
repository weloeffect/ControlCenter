from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DEFAULT_DB_PATH, MISSION_TYPES
from .db import initialize_database, transaction


ZONES = [
    ("06000", "Nice", 43.7102, 7.2620),
    ("06150", "Cannes", 43.5528, 7.0174),
    ("06600", "Antibes", 43.5804, 7.1251),
    ("06500", "Menton", 43.7745, 7.4975),
    ("13001", "Marseille", 43.2965, 5.3698),
    ("13100", "Aix-en-Provence", 43.5297, 5.4474),
    ("83000", "Toulon", 43.1242, 5.9280),
    ("84000", "Avignon", 43.9493, 4.8055),
    ("34000", "Montpellier", 43.6108, 3.8767),
    ("31000", "Toulouse", 43.6047, 1.4442),
    ("33000", "Bordeaux", 44.8378, -0.5792),
    ("44000", "Nantes", 47.2184, -1.5536),
    ("35000", "Rennes", 48.1173, -1.6778),
    ("69001", "Lyon", 45.7640, 4.8357),
    ("38000", "Grenoble", 45.1885, 5.7245),
    ("75001", "Paris", 48.8566, 2.3522),
    ("59000", "Lille", 50.6292, 3.0573),
    ("67000", "Strasbourg", 48.5734, 7.7521),
    ("76000", "Rouen", 49.4432, 1.0993),
    ("45000", "Orleans", 47.9030, 1.9093),
]


@dataclass(frozen=True)
class GenerationSummary:
    partners: int
    missions: int
    offers: int
    assignments: int
    availability_rows: int


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat(timespec="seconds") if isinstance(value, datetime) else value.isoformat() if value else None


def generate_synthetic_data(
    db_path: str | Path = DEFAULT_DB_PATH,
    *,
    partner_count: int = 350,
    mission_count: int = 15_000,
    history_days: int = 180,
    seed: int = 42,
    as_of: date | None = None,
) -> GenerationSummary:
    """Create correlated, deterministic synthetic operations data.

    Partner-level latent traits drive offers and mission outcomes, which makes the
    score, coverage, alert and quality-risk screens tell a coherent story.
    """
    if partner_count < 20 or mission_count < 200:
        raise ValueError("Use at least 20 partners and 200 missions for a meaningful dataset")

    as_of = as_of or date.today()
    rng = np.random.default_rng(seed)
    path = initialize_database(db_path, reset=True)

    zone_rows = [
        {"zone_id": i + 1, "postal_code": pc, "city": city, "latitude": lat, "longitude": lon}
        for i, (pc, city, lat, lon) in enumerate(ZONES)
    ]
    zones = pd.DataFrame(zone_rows)

    # A mild geographic imbalance intentionally creates a few coverage hot spots.
    zone_weights = np.array([1.4, 0.8, 0.7, 0.35, 1.5, 0.9, 0.7, 0.45, 0.9, 1.0,
                             0.95, 0.7, 0.45, 1.25, 0.55, 2.6, 1.0, 0.75, 0.5, 0.4])
    zone_weights /= zone_weights.sum()

    home_zone_ids = rng.choice(zones.zone_id.to_numpy(), size=partner_count, p=zone_weights)
    latent_quality = np.clip(rng.beta(8, 2, partner_count), 0.35, 0.995)
    latent_acceptance = np.clip(rng.beta(6, 2.3, partner_count), 0.25, 0.99)
    capacities = rng.integers(2, 7, partner_count)
    status = rng.choice(["active", "inactive", "suspended"], partner_count, p=[0.96, 0.025, 0.015])
    registration_offsets = rng.integers(90, 1800, partner_count)

    partners: list[dict] = []
    capabilities: list[dict] = []
    service_zones: list[dict] = []
    eligible: dict[tuple[int, str], list[int]] = {}
    partner_traits: dict[int, dict] = {}

    for index in range(partner_count):
        partner_id = index + 1
        home = zones.loc[zones.zone_id == home_zone_ids[index]].iloc[0]
        lat = float(home.latitude + rng.normal(0, 0.045))
        lon = float(home.longitude + rng.normal(0, 0.055))
        partners.append({
            "partner_id": partner_id,
            "name": f"Partner {partner_id:03d}",
            "home_zone_id": int(home.zone_id),
            "latitude": lat,
            "longitude": lon,
            "registration_date": _iso(as_of - timedelta(days=int(registration_offsets[index]))),
            "declared_availability": int(rng.random() > 0.04),
            "max_daily_capacity": int(capacities[index]),
            "status": str(status[index]),
        })
        type_count = int(rng.choice([1, 2, 3], p=[0.18, 0.47, 0.35]))
        types = list(rng.choice(MISSION_TYPES, size=type_count, replace=False))
        for mission_type in types:
            capabilities.append({"partner_id": partner_id, "mission_type": mission_type})

        distances = []
        for zone in zone_rows:
            distance = haversine_km(lat, lon, zone["latitude"], zone["longitude"])
            distances.append((distance, zone["zone_id"]))
        # Every partner covers the nearest zone, and up to three nearby zones.
        for distance, zone_id in sorted(distances)[:3]:
            if distance <= 95 or zone_id == int(home.zone_id):
                service_zones.append({
                    "partner_id": partner_id,
                    "zone_id": zone_id,
                    "distance_km": round(distance, 2),
                })
                for mission_type in types:
                    eligible.setdefault((zone_id, mission_type), []).append(partner_id)
        partner_traits[partner_id] = {
            "quality": float(latent_quality[index]),
            "acceptance": float(latent_acceptance[index]),
            "capacity": int(capacities[index]),
            "status": str(status[index]),
            "experience_bias": float(rng.normal(0, 0.035)),
        }

    start_date = as_of - timedelta(days=history_days)
    availability_end = as_of + timedelta(days=14)
    availability_state: dict[tuple[int, date], dict] = {}
    for partner in partners:
        pid = partner["partner_id"]
        trait = partner_traits[pid]
        current = start_date
        while current <= availability_end:
            weekday_factor = 0.72 if current.weekday() >= 5 else 1.0
            # Partners are freelance/part-time in this scenario; only a fraction of
            # the full network declares any individual day. This creates meaningful
            # local capacity pressure while preserving broad network coverage.
            declared = int(rng.random() < 0.14 * weekday_factor and trait["status"] == "active")
            actual = int(declared and rng.random() < 0.96)
            slots = trait["capacity"] if actual else 0
            availability_state[(pid, current)] = {
                "partner_id": pid,
                "date": current.isoformat(),
                "declared_available": declared,
                "actual_available": actual,
                "available_slots": slots,
                "booked_slots": 0,
                "updated_at": _iso(datetime.combine(current, time(6, 0))),
            }
            current += timedelta(days=1)

    missions: list[dict] = []
    offers: list[dict] = []
    assignments: list[dict] = []
    offer_id = 1
    assignment_id = 1

    mission_zone_weights = zone_weights.copy()
    # Paris, Marseille and Nice have deliberately higher demand than partner supply.
    for hot_zone in (1, 5, 16):
        mission_zone_weights[hot_zone - 1] *= 1.35
    mission_zone_weights /= mission_zone_weights.sum()

    for mission_id in range(1, mission_count + 1):
        days_ago = int(rng.integers(1, history_days + 1))
        appointment_date = as_of - timedelta(days=days_ago)
        # Move most Sunday missions into Monday to make seasonality realistic.
        if appointment_date.weekday() == 6 and rng.random() < 0.75:
            appointment_date += timedelta(days=1)
        hour = int(rng.choice([8, 9, 10, 11, 13, 14, 15, 16], p=[.08, .14, .15, .12, .12, .15, .14, .10]))
        minute = int(rng.choice([0, 30]))
        appointment_at = datetime.combine(appointment_date, time(hour, minute))
        created_at = appointment_at - timedelta(hours=float(rng.uniform(18, 120)))
        zone_id = int(rng.choice(zones.zone_id.to_numpy(), p=mission_zone_weights))
        mission_type = str(rng.choice(MISSION_TYPES, p=[0.52, 0.28, 0.20]))

        candidates = eligible.get((zone_id, mission_type), []).copy()
        rng.shuffle(candidates)
        candidates.sort(
            key=lambda pid: partner_traits[pid]["quality"] + partner_traits[pid]["acceptance"] + rng.normal(0, .18),
            reverse=True,
        )
        selected_partner: int | None = None
        accepted_at: datetime | None = None
        for pid in candidates[: min(20, len(candidates))]:
            av = availability_state[(pid, appointment_date)]
            if not av["actual_available"] or av["booked_slots"] >= av["available_slots"]:
                continue
            trait = partner_traits[pid]
            proposed_at = created_at + timedelta(minutes=int(rng.integers(5, 180)))
            response_delay = timedelta(minutes=int(rng.integers(3, 150)))
            distance = next(
                item["distance_km"] for item in service_zones
                if item["partner_id"] == pid and item["zone_id"] == zone_id
            )
            accept_probability = np.clip(
                trait["acceptance"] - 0.0025 * distance - 0.08 * (av["booked_slots"] / max(av["available_slots"], 1)),
                0.12,
                0.98,
            )
            draw = rng.random()
            if draw < accept_probability:
                response = "accepted"
                refusal_reason = None
                selected_partner = pid
                accepted_at = proposed_at + response_delay
            elif draw > 0.96:
                response = "timeout"
                refusal_reason = "no_response"
            else:
                response = "refused"
                refusal_reason = str(rng.choice(["capacity", "distance", "schedule", "mission_type_preference"]))
            offers.append({
                "offer_id": offer_id,
                "mission_id": mission_id,
                "partner_id": pid,
                "proposed_at": _iso(proposed_at),
                "responded_at": None if response == "timeout" else _iso(proposed_at + response_delay),
                "response_status": response,
                "refusal_reason": refusal_reason,
            })
            offer_id += 1
            if selected_partner is not None:
                break

        completed_at = delivered_at = None
        first_pass_compliant = None
        rework_count = 0
        complaint = 0
        mission_status = "unfilled"

        if selected_partner is not None and accepted_at is not None:
            trait = partner_traits[selected_partner]
            av = availability_state[(selected_partner, appointment_date)]
            av["booked_slots"] += 1
            no_show_probability = np.clip(0.19 - 0.18 * trait["quality"], 0.004, 0.12)
            no_show = bool(rng.random() < no_show_probability)
            if no_show:
                assignment_status = "no_show"
                arrival_at = None
                mission_status = "unfilled"
            else:
                late_mean = 38 * (1 - trait["quality"]) - 6
                lateness_minutes = float(np.clip(rng.normal(late_mean, 17), -35, 100))
                arrival_at = appointment_at + timedelta(minutes=lateness_minutes)
                duration_minutes = float(np.clip(rng.normal(72 if mission_type != "house_inspection" else 105, 22), 30, 190))
                completed_at_dt = max(arrival_at, appointment_at) + timedelta(minutes=duration_minutes)
                delivery_hours = float(np.clip(rng.lognormal(mean=2.45 + 1.1 * (1 - trait["quality"]), sigma=.55), 2, 110))
                delivered_at_dt = completed_at_dt + timedelta(hours=delivery_hours)
                compliance_probability = np.clip(trait["quality"] + trait["experience_bias"] - (0.035 if mission_type == "house_inspection" else 0), .35, .995)
                first_pass_compliant = int(rng.random() < compliance_probability)
                if not first_pass_compliant:
                    rework_count = int(rng.choice([1, 2, 3], p=[.78, .18, .04]))
                    delivered_at_dt += timedelta(hours=8 * rework_count)
                complaint_probability = np.clip(.006 + .11 * (1 - trait["quality"]) + .08 * (not first_pass_compliant), .003, .18)
                complaint = int(rng.random() < complaint_probability)
                completed_at, delivered_at = _iso(completed_at_dt), _iso(delivered_at_dt)
                assignment_status = "completed"
                mission_status = "completed"
            assignments.append({
                "assignment_id": assignment_id,
                "mission_id": mission_id,
                "partner_id": selected_partner,
                "assigned_at": _iso(accepted_at),
                "arrival_at": _iso(arrival_at) if not no_show else None,
                "status": assignment_status,
                "assignment_source": "synthetic",
            })
            assignment_id += 1

        missions.append({
            "mission_id": mission_id,
            "zone_id": zone_id,
            "mission_type": mission_type,
            "created_at": _iso(created_at),
            "appointment_at": _iso(appointment_at),
            "completed_at": completed_at,
            "delivered_at": delivered_at,
            "status": mission_status,
            "first_pass_compliant": first_pass_compliant,
            "rework_count": rework_count,
            "customer_complaint": complaint,
            "source": "synthetic",
        })

    availability = list(availability_state.values())
    frames = [
        ("zones", zones),
        ("partners", pd.DataFrame(partners)),
        ("partner_capabilities", pd.DataFrame(capabilities)),
        ("partner_service_zones", pd.DataFrame(service_zones)),
        ("missions", pd.DataFrame(missions)),
        ("mission_offers", pd.DataFrame(offers)),
        ("assignments", pd.DataFrame(assignments)),
        ("availability", pd.DataFrame(availability)),
    ]
    with transaction(path) as connection:
        for table, frame in frames:
            frame.to_sql(table, connection, if_exists="append", index=False, chunksize=2_000)

    return GenerationSummary(
        partners=len(partners),
        missions=len(missions),
        offers=len(offers),
        assignments=len(assignments),
        availability_rows=len(availability),
    )
