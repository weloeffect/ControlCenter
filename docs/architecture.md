# Architecture

## Runtime view

```mermaid
flowchart TD
    G[Synthetic generator] --> DB[(SQLite prototype database)]
    DB --> K[KPI and score services]
    DB --> C[Coverage forecast]
    DB --> A[Assignment engine]
    DB --> Q[Quality-risk model]
    K --> DB
    C --> DB
    Q --> DB
    DB --> R[Alert rules]
    R --> DB
    DB --> S[Streamlit control tower]
    N[n8n daily schedule] --> API[FastAPI automation endpoint]
    API --> R
    API --> W[Optional webhook]
```

## Decision sequence

```mermaid
flowchart LR
    M[New mission] --> E{Eligibility}
    E -->|inactive / unavailable / unqualified / full| X[Excluded]
    E -->|eligible| F[Normalized factor scores]
    F --> R[Rank candidates]
    R --> J[Explain recommendation]
    J --> L[Log ranked result]
```

## Boundaries

- `synthetic.py` owns reproducible demonstration-data generation.
- `kpis.py` owns measurement definitions and aggregation.
- `scoring.py` owns reliability normalization, confidence and tiers.
- `coverage.py` owns short-horizon demand and allocated capacity.
- `assignment.py` owns hard eligibility and soft ranking.
- `quality.py` owns model training, temporal holdout validation and assessment.
- `alerts.py` owns rule evaluation, deduplication and resolution.
- Streamlit pages contain presentation logic only.

SQLite provides a portable demo with no infrastructure dependency. PostgreSQL is the recommended next step when multiple deployed services need concurrent, durable access.

