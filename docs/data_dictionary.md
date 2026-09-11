# Data dictionary

The executable source of truth is `database/schema.sql`.

| Table | Purpose |
|---|---|
| `zones` | Postal operating areas and map coordinates. |
| `partners` | Partner identity, home location, capacity and lifecycle status. |
| `partner_capabilities` | Mission types a partner may perform. |
| `partner_service_zones` | Geographic eligibility and partner-to-zone distance. |
| `missions` | Independent work requests and delivered outcomes. |
| `mission_offers` | Proposal and response history for every contacted partner. |
| `assignments` | Selected partner, arrival and execution status. |
| `availability` | Declared/actual daily availability and booked slots. |
| `partner_score_snapshots` | Auditable 90-day KPI and reliability history. |
| `coverage_snapshots` | Forecast demand, allocated capacity and ratio. |
| `assignment_recommendations` | Ranked candidates and factor contributions. |
| `alerts` | Idempotent operational conditions and lifecycle state. |
| `quality_assessments` | Model version, probability and risk level by mission. |

