# 07. Demand, supply and mismatch engine

Code: `backend/app/analytics/`. Settings: `config/scoring.yaml` (every weight, window and
threshold below comes from there; the numbers shown are the current values, version `v4`).

## 1. Commands and API

```powershell
cd backend; .\.venv\Scripts\Activate.ps1
python -m app.cli.analytics run        # demand -> supply -> mismatch, all 4 districts, all quarters
python -m app.cli.analytics show --district MH-NASHIK --role ev-service-technician
python -m app.cli.analytics validate   # checks the planted synthetic patterns are found
```

`run` stores one `pipeline_run` (marked current) with its demand, supply and mismatch rows and a
copy of `scoring.yaml` (`scoring_config_version`), so every number can be traced to its settings.

| Endpoint | Returns |
|---|---|
| `GET /api/v1/analytics/demand` | Role demand (`?level=skill` or `?skill=` for skills) |
| `GET /api/v1/analytics/demand/{district}` | The same for one district |
| `GET /api/v1/analytics/supply` | Trained people per year (`?group_by=district|institute|course|role|skill`) |
| `GET /api/v1/analytics/mismatch` | Supply / openings per role and district |
| `GET /api/v1/analytics/districts/{district}/mismatch` | District mismatch score + its roles |
| `POST /api/v1/analytics/run` | Recompute (admin) |

Filters: `district`, `sector`, `role`, `skill`, `quarter` (default: the run's latest quarter).
Readers: admin, state/district officers, SSC reviewers, institute admins, employers, each limited
to the districts in their scope. Candidates get 403.

## 2. Demand score (0-100)

    D = 0.35 P + 0.25 S + 0.20 G + 0.20 A

| Part | Meaning | Formula |
|---|---|---|
| P postings | Job-ad volume and growth | 0.6 x pct(log(1 + postings in the last 4 quarters)) + 0.4 x pct(growth, clipped to [-1, 2]); percentiles across the role x district cells of the quarter |
| S survey | Employer survey headcount | headcount with a recency half-life of 2 quarters, min-max scaled |
| G growth events | Announced projects | expected jobs x realisation factor (0.6 default) landing in the next 4 quarters; synthetic / simulated events are marked |
| A absorption | Trainees placed in the role | placed in role / completers |

Only accepted OBSERVED or SYNTHETIC job-ad links count; INFERRED links and review items never do.
A missing part is **not** treated as zero: the remaining weights are renormalised (stored as an
assumption) and confidence is lowered (rules in `scoring.yaml confidence`).

## 3. Supply, openings, mismatch

- **Supply** (people trained a year) = seats filled x completion rate, summed over the courses
  whose primary role it is, for the latest academic year completed by the quarter end. Missing
  completion rate: 0.8, stored as an assumption. Available by district, institute, course, role
  and skill.
- **Estimated openings** = job postings in the last 4 quarters / coverage factor (0.3 for
  formal-heavy roles, 0.1 for informal-heavy ones). The factor is a **modelling assumption, not an
  official statistic**, and every result says so.
- **Ratio** R = supply / openings. UNDER_SUPPLIED below 0.7, BALANCED 0.7-1.5, OVER_SUPPLIED
  above 1.5.
- **District mismatch** = demand-weighted mean of |ln R| over the district's roles (R floored at
  0.05). 0 means balanced.

## 4. Explanations

Every item returned by the API carries:

| Field | Content |
|---|---|
| `observed_inputs` | Counts behind the number (postings, headcount, events, completers, offerings) |
| `estimated_values` | Numbers the engine estimated (score, openings, supply, ratio) |
| `assumptions` | Weights, coverage factor, default rates, thresholds, with their config source |
| `confidence` | HIGH / MEDIUM / LOW |
| `reasons` | Plain-language reasons, generated only from stored evidence |
| `is_synthetic`, `synthetic_share`, `data_label` | How much of the evidence is demo data |

## 5. Results on the synthetic demo world (2026Q3)

`validate` finds all planted patterns (17 of 17 checks pass). Examples:

- **Nashik EV shortage**: EV Service Technician demand 94.5 (HIGH confidence), supply 0 against
  about 247 estimated openings a year, UNDER_SUPPLIED. Reasons: postings 26 -> 48; employers asked
  for 20 (from 14); a simulated EV battery-pack unit adds about 180 jobs in 2026Q4-2027Q3; no
  Nashik course trains for the role.
- **Kolhapur oversupply**: Wireman demand 23.8, supply 119 a year against about 57 openings,
  ratio 2.10, OVER_SUPPLIED; 26% of recent completers absorbed in the role.
- **Motor Rewinding decline**: demand falls in every district; the skill is DECLINING.

District mismatch: Pune 1.96, Nashik 2.35, Nagpur 1.84, Kolhapur 2.58. These are high partly
because many roles have no demo course at all (R = 0).

## 6. Limitations

- All inputs are synthetic; the coverage factors and the realisation factor are assumptions to
  be calibrated with real data.
- Supply counts a course for its primary role only (a completer of an Electrician course may
  also take wireman jobs).
- Percentile-based P depends on which roles and districts are in scope.
- Course health (`scoring.yaml course_health`) is not computed by the engine yet; the frontend
  shows a clearly labelled demo heuristic instead.
