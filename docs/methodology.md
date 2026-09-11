# Methodology

## Data grain

- A **mission** is the operational request, independent of the partner who may perform it.
- A **mission offer** records one proposal and its accepted, refused or timeout response.
- An **assignment** records the selected partner and execution outcome.
- **Availability** is recorded per partner and calendar day.
- **Coverage** is evaluated per zone, day and mission type.
- **Partner score snapshots** retain historical values needed for trends and alert rules.

This separation prevents reassignment from erasing the partners who previously refused a mission.

## KPI definitions

| KPI | Definition |
|---|---|
| Acceptance rate | Accepted offers ÷ accepted and refused offers. Timeouts are tracked separately. |
| Punctuality | Completed assignments arriving no later than 15 minutes after the appointment. |
| First-pass compliance | Completed missions marked compliant before any rework. |
| Delivery time | Hours between visit completion and final delivery. |
| No-show rate | No-show assignments ÷ all scheduled assignments. |
| Complaint rate | Complaints ÷ completed missions. |
| Manual rework rate | Rework events ÷ completed missions. |

Partner metrics use a trailing 90-day window. The prototype stores snapshots at 30-day intervals for trends.

## Score normalization

- Rate metrics are multiplied by 100.
- No-show score is `100 × (1 − no-show rate)`.
- Delivery is 100 at 12 hours or less and declines linearly to zero at 72 hours.
- Missing component values use the corresponding network average, then the full score is adjusted toward a weighted network prior.
- Confidence is `n / (n + 20)`, where `n` is completed missions.
- Fewer than ten completed missions results in `Insufficient data`.

Tier thresholds are demonstration assumptions:

| Tier | Score |
|---|---:|
| Elite | 95–100 |
| Gold | 90–94.99 |
| Silver | 80–89.99 |
| Bronze | 70–79.99 |
| Risk | below 70 |

## Coverage forecast

Expected demand is the average historical mission count for the same weekday over the previous eight weeks. A floor of 0.25 preserves visibility for low-frequency segments.

A partner's remaining slots are divided among all service-zone and capability combinations they can serve on that date. This prevents a single slot from appearing simultaneously as full capacity in several areas. A production optimizer could allocate this shared capacity dynamically.

| Status | Coverage ratio |
|---|---:|
| Healthy | at least 1.20 |
| Watch | 0.90–1.19 |
| Critical | below 0.90 |

The critical alert threshold is deliberately tighter at 0.85.

## Smart Assignment

Hard constraints precede ranking:

- active partner;
- declared and actual availability;
- positive remaining capacity;
- mission-type capability;
- service coverage for the target zone.

Distance decays exponentially with a 35 km scale. Experience approaches 100 as relevant completed missions accumulate. Availability is binary after filtering; workload represents the fraction of daily slots still free.

## Quality risk

The binary outcome is positive when a mission produces a no-show, first-pass non-compliance, rework, or complaint. Features are limited to information conceptually available before the outcome:

- distance;
- partner tenure;
- appointment hour and weekday;
- prior mission count and prior bad-outcome rate;
- daily capacity;
- mission type.

Prior performance uses an expanding, shifted calculation so the current outcome is not included in its own features. The final 20% of chronologically ordered observations is held out for evaluation. Because both inputs and labels are synthetic, the metrics demonstrate pipeline validity only.

## Alert lifecycle

Every rule creates a deterministic deduplication key. An active condition updates the same record. When a previously active managed condition is absent on the next run, the alert is resolved automatically. This avoids daily duplicate alerts.

