PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS zones (
    zone_id INTEGER PRIMARY KEY,
    postal_code TEXT NOT NULL UNIQUE,
    city TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS partners (
    partner_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    home_zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    registration_date TEXT NOT NULL,
    declared_availability INTEGER NOT NULL CHECK (declared_availability IN (0, 1)),
    max_daily_capacity INTEGER NOT NULL CHECK (max_daily_capacity > 0),
    status TEXT NOT NULL CHECK (status IN ('active', 'inactive', 'suspended'))
);

CREATE TABLE IF NOT EXISTS partner_capabilities (
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    mission_type TEXT NOT NULL,
    PRIMARY KEY (partner_id, mission_type)
);

CREATE TABLE IF NOT EXISTS partner_service_zones (
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    distance_km REAL NOT NULL CHECK (distance_km >= 0),
    PRIMARY KEY (partner_id, zone_id)
);

CREATE TABLE IF NOT EXISTS missions (
    mission_id INTEGER PRIMARY KEY,
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    mission_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    appointment_at TEXT NOT NULL,
    completed_at TEXT,
    delivered_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('open', 'assigned', 'completed', 'cancelled', 'unfilled')),
    first_pass_compliant INTEGER,
    rework_count INTEGER NOT NULL DEFAULT 0 CHECK (rework_count >= 0),
    customer_complaint INTEGER NOT NULL DEFAULT 0 CHECK (customer_complaint IN (0, 1)),
    source TEXT NOT NULL DEFAULT 'synthetic'
);

CREATE TABLE IF NOT EXISTS mission_offers (
    offer_id INTEGER PRIMARY KEY,
    mission_id INTEGER NOT NULL REFERENCES missions(mission_id),
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    proposed_at TEXT NOT NULL,
    responded_at TEXT,
    response_status TEXT NOT NULL CHECK (response_status IN ('accepted', 'refused', 'timeout')),
    refusal_reason TEXT,
    UNIQUE (mission_id, partner_id)
);

CREATE TABLE IF NOT EXISTS assignments (
    assignment_id INTEGER PRIMARY KEY,
    mission_id INTEGER NOT NULL UNIQUE REFERENCES missions(mission_id),
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    assigned_at TEXT NOT NULL,
    arrival_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no_show')),
    assignment_source TEXT NOT NULL CHECK (assignment_source IN ('manual', 'recommended', 'synthetic'))
);

CREATE TABLE IF NOT EXISTS availability (
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    date TEXT NOT NULL,
    declared_available INTEGER NOT NULL CHECK (declared_available IN (0, 1)),
    actual_available INTEGER NOT NULL CHECK (actual_available IN (0, 1)),
    available_slots INTEGER NOT NULL CHECK (available_slots >= 0),
    booked_slots INTEGER NOT NULL DEFAULT 0 CHECK (booked_slots >= 0),
    updated_at TEXT NOT NULL,
    PRIMARY KEY (partner_id, date)
);

CREATE TABLE IF NOT EXISTS partner_score_snapshots (
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    snapshot_date TEXT NOT NULL,
    window_days INTEGER NOT NULL,
    acceptance_rate REAL,
    punctuality_rate REAL,
    compliance_rate REAL,
    average_delivery_hours REAL,
    no_show_rate REAL,
    complaint_rate REAL,
    mission_count INTEGER NOT NULL,
    raw_score REAL,
    confidence REAL NOT NULL,
    reliability_score REAL,
    tier TEXT NOT NULL,
    PRIMARY KEY (partner_id, snapshot_date, window_days)
);

CREATE TABLE IF NOT EXISTS coverage_snapshots (
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    target_date TEXT NOT NULL,
    mission_type TEXT NOT NULL,
    available_capacity REAL NOT NULL,
    expected_demand REAL NOT NULL,
    coverage_ratio REAL NOT NULL,
    coverage_status TEXT NOT NULL CHECK (coverage_status IN ('healthy', 'watch', 'critical')),
    forecast_generated_at TEXT NOT NULL,
    PRIMARY KEY (zone_id, target_date, mission_type)
);

CREATE TABLE IF NOT EXISTS assignment_recommendations (
    recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    mission_id INTEGER REFERENCES missions(mission_id),
    zone_id INTEGER NOT NULL REFERENCES zones(zone_id),
    mission_type TEXT NOT NULL,
    appointment_at TEXT NOT NULL,
    partner_id INTEGER NOT NULL REFERENCES partners(partner_id),
    rank INTEGER NOT NULL,
    reliability_component REAL NOT NULL,
    availability_component REAL NOT NULL,
    distance_component REAL NOT NULL,
    workload_component REAL NOT NULL,
    experience_component REAL NOT NULL,
    assignment_score REAL NOT NULL,
    generated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alerts (
    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    partner_id INTEGER REFERENCES partners(partner_id),
    mission_id INTEGER REFERENCES missions(mission_id),
    zone_id INTEGER REFERENCES zones(zone_id),
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    resolved_at TEXT,
    status TEXT NOT NULL CHECK (status IN ('open', 'acknowledged', 'resolved')),
    message TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS quality_assessments (
    mission_id INTEGER PRIMARY KEY REFERENCES missions(mission_id),
    risk_probability REAL NOT NULL,
    risk_level TEXT NOT NULL CHECK (risk_level IN ('low', 'medium', 'high')),
    model_version TEXT NOT NULL,
    assessed_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_missions_appointment ON missions(appointment_at);
CREATE INDEX IF NOT EXISTS idx_missions_zone_type ON missions(zone_id, mission_type);
CREATE INDEX IF NOT EXISTS idx_offers_partner ON mission_offers(partner_id, proposed_at);
CREATE INDEX IF NOT EXISTS idx_assignments_partner ON assignments(partner_id, assigned_at);
CREATE INDEX IF NOT EXISTS idx_availability_date ON availability(date);
CREATE INDEX IF NOT EXISTS idx_scores_date ON partner_score_snapshots(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, severity);

