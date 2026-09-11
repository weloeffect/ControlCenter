# Check and Visit Operations Center

A complete, reproducible prototype for monitoring a distributed partner network, detecting capacity pressure, recommending an eligible partner for a mission, and creating operational alerts.

> **Synthetic data only.** Nothing in this repository represents the real performance, operations, customers, or partners of Check & Visit.

## What is implemented

- 350 synthetic partners, 20 French operating zones, and 15,000 correlated synthetic missions by default
- event-level offer history, so refusals, timeouts, acceptance and reassignment remain auditable
- confidence-adjusted Partner Reliability Score with four historical snapshots
- seven-day demand and capacity coverage forecast
- interactive geographic coverage map
- constraint-first Smart Assignment with explainable factor contributions
- idempotent performance, complaints, coverage, Elite-candidate and quality-risk alerts
- time-split logistic quality-risk prototype with stored validation metrics
- Streamlit application with five operational pages
- FastAPI endpoint and importable n8n daily workflow
- automated integrity, business-rule, scoring, assignment, coverage and alert tests

## Quick start

Python 3.11 or newer is required.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/setup_demo.py
streamlit run app/Home.py
```

The data generator uses a fixed seed, so the same inputs create the same operational history. Use custom volumes when needed:

```powershell
python scripts/setup_demo.py --partners 400 --missions 20000 --seed 42
```

The app can also build the database from its Home page if no demo database exists.

## Pages

1. **Executive Overview** — network KPIs, score trend, partner tiers and priority alerts.
2. **Partner Performance** — filters, score distribution, evidence volume and partner-level detail.
3. **Coverage Map** — capacity-to-demand ratio by area, date and mission type.
4. **Smart Assignment** — eligible candidates, ranking and recommendation explanation.
5. **Alerts** — current and resolved operational conditions.
6. **Quality Risk** — missions prioritized for possible manual review.

## Reliability score

All components are converted to a 0–100 scale:

```text
20% acceptance
+ 20% punctuality
+ 30% first-pass compliance
+ 15% delivery speed
+ 15% no-show avoidance
```

The raw result is adjusted toward the network average according to evidence volume:

```text
confidence = completed missions / (completed missions + 20)
adjusted score = confidence × raw score + (1 − confidence) × network prior
```

Partners with fewer than ten completed missions receive `Insufficient data` rather than a performance tier.

See [methodology](docs/methodology.md) for exact denominators, thresholds and limitations.

## Smart Assignment

The engine first removes candidates who are inactive, unqualified, outside the service area, unavailable, or at capacity. It then ranks the remaining candidates:

```text
35% reliability
+ 25% availability
+ 20% distance
+ 10% remaining workload capacity
+ 10% mission-type experience
```

Every displayed factor is on a 0–100 scale. Saved recommendations retain the ranked candidates and component scores for auditability.

## Alerts and n8n

Start the local automation API:

```powershell
python scripts/serve_automation_api.py
```

Import `workflows/n8n_alerts.json` into n8n. Its daily schedule calls:

```text
POST http://host.docker.internal:8000/alerts/run
```

When n8n runs outside Docker, change the hostname to `127.0.0.1`. The workflow ends with a prepared notification payload; connect that node to Slack, email, Teams, or another approved destination. Alternatively, set `ALERT_WEBHOOK_URL` for the API to send the summary directly.

Alert writes are idempotent. A repeated run refreshes the existing condition, while a condition that disappears is marked resolved.

## Validation and tests

```powershell
python scripts/validate_data.py
pytest
```

The tests verify, among other things, that accepted offers support assignments, dates are coherent, capacity is not overbooked, scores remain bounded, no-shows reduce reliability, unavailable partners are excluded, coverage thresholds are correct, and repeated alert runs do not create duplicates.

## Individual jobs

```powershell
python scripts/generate_data.py
python scripts/calculate_kpis.py
python scripts/partner_score.py
python scripts/train_quality_model.py
python scripts/run_alerts.py
python scripts/assignment_engine.py --zone 1 --mission-type apartment_inspection
```

## Project structure

```text
app/                    Streamlit app and pages
database/               SQLite schema and reference KPI queries
data/                   Generated database (ignored by Git)
docs/                   Architecture and methodology
models/                 Generated quality model (ignored by Git)
scripts/                Runnable data, analytics and automation jobs
src/control_tower/      Tested domain logic
tests/                  Automated tests
workflows/              Importable n8n workflow
```

## Deployment note

SQLite is deliberately used for a self-contained local prototype. A persistent multi-service deployment should replace it with PostgreSQL and use migrations. Streamlit and the automation API must then share the same database. The code keeps database access isolated so that migration can be performed without rewriting scoring or decision logic.

## Known limitations

- All observations and model labels are synthetic.
- Score weights and tier thresholds are demonstration assumptions requiring business validation.
- Forecasting uses recent weekday averages rather than a production forecasting model.
- Capacity is conservatively divided across the zones and mission types each partner can serve; it is not a global optimization.
- Quality-model validation describes synthetic holdout performance only.
- Real constraints such as contracts, working-hour windows, equipment, accessibility, travel time, partner preferences and customer SLAs are not represented.
- Recommendations support operations teams; they do not replace human judgment.
