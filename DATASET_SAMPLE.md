# TrackShift — Formula 1 Real Telemetry & AI/ML Dataset Sample Reference

> **Platform:** TrackShift Formula 1 Tyre Debt Intelligence Platform  
> **Telemetry Source:** Official FastF1 Historical Ingestion (2024 & 2025 FIA Formula 1 World Championship)  
> **Total Records Audited:** 18,513 telemetry laps, 16,376 debt ledger observations, 15,789 circuit geometry coordinates  
> **Format:** Apache Parquet (Columnar snappy-compressed) + SQLite Relational Schema (`tyredebt.db`)

---

## Table of Contents
1. [Dataset Overview & Summary Statistics](#1-dataset-overview--summary-statistics)
2. [Dataset 1: `laps.parquet` — Telemetry & Behavioral Features](#2-dataset-1-lapsparquet--telemetry--behavioral-features)
3. [Dataset 2: `residual_ledger.parquet` — Contextual Residuals & Cumulative Tyre Debt](#3-dataset-2-residual_ledgerparquet--contextual-residuals--cumulative-tyre-debt)
4. [Dataset 3: `circuit_geometry.parquet` — 24-Circuit GPS Track Coordinates & Speeds](#4-dataset-3-circuit_geometryparquet--24-circuit-gps-track-coordinates--speeds)
5. [Dataset 4: `bootstrap_uncertainty.parquet` — 1,000-Iteration Cluster Bootstrap Intervals](#5-dataset-4-bootstrap_uncertaintyparquet--1000-iteration-cluster-bootstrap-intervals)
6. [Dataset 5: `baseline_predictions.parquet` — Stage 1 Linear M1 Lap Time Loss Baseline](#6-dataset-5-baseline_predictionsparquet--stage-1-linear-m1-lap-time-loss-baseline)
7. [Relational SQLite Schema (`api/tyredebt.db`)](#7-relational-sqlite-schema-apityredebtdb)

---

## 1. Dataset Overview & Summary Statistics

| Dataset Name | File Path | Records | File Size | Primary Key / Indexing | Domain Scope |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **Telemetry Laps** | `data/laps.parquet` | 18,513 | ~680 KB | `stint_id`, `lap_number` | Multi-season laps, driving metrics, fuel loads |
| **Residual Debt Ledger** | `data/residual_ledger.parquet` | 16,376 | ~213 KB | `stint_id`, `lap_number` | Baseline lap loss, residual error, cumulative tyre debt |
| **Circuit Geometry** | `data/circuit_geometry.parquet` | 15,789 | ~798 KB | `circuit_id`, `point_order` | 24 Grand Prix tracks, X/Y GPS coordinates, speeds |
| **Bootstrap Uncertainty** | `data/bootstrap_uncertainty.parquet` | 131,670 | ~715 KB | `stint_id`, `feature`, `delta_pct` | 95% Confidence bounds [CI lower, CI upper, margin] |
| **Baseline Predictions** | `data/baseline_predictions.parquet` | 16,376 | ~64 KB | `stint_id`, `lap_number` | Parsimonious Stage 1 linear model predictions |
| **Relational SQLite DB** | `api/tyredebt.db` | 10 Tables | ~1.05 MB | Foreign Keys (`session_id`, `driver_id`, `circuit_id`) | Full normalized relational database for FastF1 |

---

## 2. Dataset 1: `laps.parquet` — Telemetry & Behavioral Features

Contains lap-by-lap high-frequency extracted metrics from FastF1 car telemetry, throttle/brake telemetry, and fuel estimates across all 2024 and 2025 race weekends.

### Schema & Data Types
- `stint_id` (*string*): Composite identifier format `{year}_{circuit}_{session}_{driver}_{stint_num}` (e.g. `2024_bahrain_R_VER_1`)
- `circuit_id` (*string*): Standardized slug (e.g. `bahrain`, `monza`, `silverstone`, `spa`)
- `session_id` (*string*): Session slug (e.g. `2024_bahrain_R`)
- `driver_id` (*string*): 3-letter driver code (`VER`, `HAM`, `NOR`, `LEC`, `PIA`, `SAI`, etc.)
- `compound` (*string*): Tyre compound name (`SOFT`, `MEDIUM`, `HARD`, `INTERMEDIATE`, `WET`)
- `lap_number` (*int64*): Lap number within race
- `lap_time` (*float64*): Lap time in seconds
- `is_green_flag` (*int64*): Binary flag (1 = Green Flag racing, 0 = SC/VSC/In-lap/Out-lap)
- `fuel_load_est` (*float64*): Estimated fuel on board in kilograms (depleting ~1.75 kg/lap from 110 kg initial)
- `braking_aggression` (*float64*): Mean peak deceleration gradient (bar/s or G/s)
- `throttle_transient_smoothness` (*float64*): Standard deviation of throttle application rate (lower = smoother)
- `lateral_dynamics_proxy` (*float64*): High-speed cornering lateral acceleration load proxy
- `kerb_usage` (*float64*): Integrated high-frequency oscillation magnitude over kerbs
- `lockup_flag_rate` (*float64*): Proportion of braking zones exhibiting front tyre rotational lockup

### Sample Records (Top 5 Rows)
```json
[
  {
    "stint_id":"2024_bahrain_R_VER_1",
    "circuit_id":"bahrain",
    "session_id":"2024_bahrain_R",
    "driver_id":"VER",
    "compound":"SOFT",
    "lap_number":1,
    "lap_time":97.284,
    "is_green_flag":0,
    "fuel_load_est":108.5,
    "braking_aggression":50.2846,
    "throttle_transient_smoothness":2.3897,
    "lateral_dynamics_proxy":0.348967,
    "kerb_usage":143.1769,
    "lockup_flag_rate":0.0
  },
  {
    "stint_id":"2024_bahrain_R_VER_1",
    "circuit_id":"bahrain",
    "session_id":"2024_bahrain_R",
    "driver_id":"VER",
    "compound":"SOFT",
    "lap_number":2,
    "lap_time":96.296,
    "is_green_flag":1,
    "fuel_load_est":107.0,
    "braking_aggression":64.1777,
    "throttle_transient_smoothness":2.5467,
    "lateral_dynamics_proxy":0.173412,
    "kerb_usage":145.0769,
    "lockup_flag_rate":0.0
  },
  {
    "stint_id":"2024_bahrain_R_VER_1",
    "circuit_id":"bahrain",
    "session_id":"2024_bahrain_R",
    "driver_id":"VER",
    "compound":"SOFT",
    "lap_number":3,
    "lap_time":96.753,
    "is_green_flag":1,
    "fuel_load_est":105.5,
    "braking_aggression":53.2575,
    "throttle_transient_smoothness":2.4167,
    "lateral_dynamics_proxy":0.153305,
    "kerb_usage":135.162,
    "lockup_flag_rate":0.0183
  },
  {
    "stint_id":"2024_bahrain_R_VER_1",
    "circuit_id":"bahrain",
    "session_id":"2024_bahrain_R",
    "driver_id":"VER",
    "compound":"SOFT",
    "lap_number":4,
    "lap_time":96.647,
    "is_green_flag":1,
    "fuel_load_est":104.0,
    "braking_aggression":55.0717,
    "throttle_transient_smoothness":2.3984,
    "lateral_dynamics_proxy":0.139344,
    "kerb_usage":148.2698,
    "lockup_flag_rate":0.0
  },
  {
    "stint_id":"2024_bahrain_R_VER_1",
    "circuit_id":"bahrain",
    "session_id":"2024_bahrain_R",
    "driver_id":"VER",
    "compound":"SOFT",
    "lap_number":5,
    "lap_time":97.173,
    "is_green_flag":1,
    "fuel_load_est":102.5,
    "braking_aggression":56.8003,
    "throttle_transient_smoothness":2.4157,
    "lateral_dynamics_proxy":0.139968,
    "kerb_usage":138.1121,
    "lockup_flag_rate":0.0074
  }
]
```

### Formatted Sample Table
| stint_id | circuit_id | driver_id | compound | lap | lap_time (s) | fuel (kg) | braking_aggression | throttle_smoothness | lateral_proxy | kerb_usage | lockup_rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2024_bahrain_R_VER_1` | `bahrain` | **VER** | `SOFT` | 1 | 97.284 | 108.5 | 50.28 | 2.3897 | 0.3490 | 143.18 | 0.0000 |
| `2024_bahrain_R_VER_1` | `bahrain` | **VER** | `SOFT` | 2 | 96.296 | 107.0 | 64.18 | 2.5467 | 0.1734 | 145.08 | 0.0000 |
| `2024_bahrain_R_VER_1` | `bahrain` | **VER** | `SOFT` | 3 | 96.753 | 105.5 | 53.26 | 2.4167 | 0.1533 | 135.16 | 0.0183 |
| `2024_bahrain_R_VER_1` | `bahrain` | **VER** | `SOFT` | 4 | 96.647 | 104.0 | 55.07 | 2.3984 | 0.1393 | 148.27 | 0.0000 |
| `2024_bahrain_R_VER_1` | `bahrain` | **VER** | `SOFT` | 5 | 97.173 | 102.5 | 56.80 | 2.4157 | 0.1400 | 138.11 | 0.0074 |

---

## 3. Dataset 2: `residual_ledger.parquet` — Contextual Residuals & Cumulative Tyre Debt

The fundamental ledger powering TrackShift's Stage 2 Tyre Debt calculations. Decomposes lap time loss into baseline degradation and cumulative unrecoverable thermal/mechanical deficit.

### Schema & Data Types
- `stint_id` (*string*): Target stint identifier
- `lap_number` (*int64*): Lap number within race
- `actual_lap_time_loss` (*float64*): Observed lap time loss relative to fastest stint lap (seconds)
- `predicted_lap_time_loss` (*float64*): Stage 1 baseline expected loss $\hat{y} = 0.1974 + 0.0400 \times \text{tyre\_age}$
- `residual` (*float64*): Contextual residual $\epsilon_i = y_i - \hat{y}_i$
- `cumulative_debt` (*float64*): Integrated positive excess loss $\sum \max(0, \epsilon_i)$ (seconds)
- `model_version` (*string*): Provenance model version string (e.g. `v4_m1_production_2026-09-10`)

### Sample Records (Top 5 Rows)
```json
[
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "lap_number":4,
    "actual_lap_time_loss":0.0,
    "predicted_lap_time_loss":0.3573300528,
    "residual":-0.3573300528,
    "cumulative_debt":0.0,
    "model_version":"v4_m1_production_2026-09-10"
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "lap_number":5,
    "actual_lap_time_loss":0.309,
    "predicted_lap_time_loss":0.3973179115,
    "residual":-0.0883179115,
    "cumulative_debt":0.0,
    "model_version":"v4_m1_production_2026-09-10"
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "lap_number":6,
    "actual_lap_time_loss":0.755,
    "predicted_lap_time_loss":0.4373057702,
    "residual":0.3176942298,
    "cumulative_debt":0.3176942298,
    "model_version":"v4_m1_production_2026-09-10"
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "lap_number":7,
    "actual_lap_time_loss":0.257,
    "predicted_lap_time_loss":0.4772936289,
    "residual":-0.2202936289,
    "cumulative_debt":0.3176942298,
    "model_version":"v4_m1_production_2026-09-10"
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "lap_number":8,
    "actual_lap_time_loss":0.645,
    "predicted_lap_time_loss":0.5172814876,
    "residual":0.1277185124,
    "cumulative_debt":0.4454127423,
    "model_version":"v4_m1_production_2026-09-10"
  }
]
```

### Formatted Sample Table
| stint_id | lap_number | actual_loss (s) | predicted_loss (s) | residual (s) | cumulative_debt (s) | model_version |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `2024_abu_dhabi_R_ALB_1` | 4 | 0.000 | 0.357 | -0.357 | **0.000** | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 5 | 0.309 | 0.397 | -0.088 | **0.000** | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 6 | 0.755 | 0.437 | 0.318 | **0.318** | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 7 | 0.257 | 0.477 | -0.220 | **0.318** | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 8 | 0.645 | 0.517 | 0.128 | **0.445** | `v4_m1_production_2026-09-10` |

---

## 4. Dataset 3: `circuit_geometry.parquet` — 24-Circuit GPS Track Coordinates & Speeds

Normalized 2D/3D track layout telemetry for all 24 official Formula 1 circuits. Used for real-time SVG track rendering, corner identification, driver positioning, and speed heatmaps.

### Schema & Data Types
- `X` (*float64*): Raw GPS easting coordinate in decimeters / meters
- `Y` (*float64*): Raw GPS northing coordinate in decimeters / meters
- `Distance` (*float64*): Distance along track centerline from start/finish line (meters)
- `Speed` (*float64*): Typical reference apex/straight speed (km/h)
- `Throttle` (*float64*): Throttle application percentage (0.0 to 100.0)
- `Brake` (*bool*): Binary brake activation flag (`True` / `False`)
- `circuit_id` (*string*): Standardized circuit slug (e.g. `bahrain`, `monza`, `silverstone`)
- `point_order` (*int64*): Sequential index of coordinate points along track spline
- `x_rot` (*float64*): Rotated and centered SVG X coordinate
- `y_rot` (*float64*): Rotated and centered SVG Y coordinate

### Sample Records (Top 5 Rows)
```json
[
  {
    "X":-379.6079280973,
    "Y":1297.7195176351,
    "Distance":0.0027317087,
    "Speed":283.0750016,
    "Throttle":100.0,
    "Brake":false,
    "circuit_id":"bahrain",
    "point_order":0,
    "x_rot":-1283.6808563333,
    "y_rot":-424.6664392307
  },
  {
    "X":-371.9825771903,
    "Y":1455.8078865125,
    "Distance":12.195,
    "Speed":285.0,
    "Throttle":100.0,
    "Brake":false,
    "circuit_id":"bahrain",
    "point_order":1,
    "x_rot":-1441.9390429566,
    "y_rot":-422.5629379897
  },
  {
    "X":-369.0,
    "Y":1516.0,
    "Distance":18.3822421448,
    "Speed":285.2785718857,
    "Throttle":100.0,
    "Brake":false,
    "circuit_id":"bahrain",
    "point_order":2,
    "x_rot":-1502.1985794777,
    "y_rot":-421.682852171
  },
  {
    "X":-364.0052271832,
    "Y":1610.2358522537,
    "Distance":34.4394444444,
    "Speed":286.0,
    "Throttle":100.0,
    "Brake":false,
    "circuit_id":"bahrain",
    "point_order":3,
    "x_rot":-1596.5513408539,
    "y_rot":-419.9799058499
  },
  {
    "X":-358.86047743,
    "Y":1718.6762957839,
    "Distance":47.195,
    "Speed":287.0,
    "Throttle":100.0,
    "Brake":false,
    "circuit_id":"bahrain",
    "point_order":4,
    "x_rot":-1705.1052745729,
    "y_rot":-418.6228070406
  }
]
```

### Formatted Sample Table
| circuit_id | point_order | Distance (m) | Speed (km/h) | Throttle (%) | Brake | X (GPS) | Y (GPS) | x_rot (SVG) | y_rot (SVG) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `bahrain` | 0 | 0.0 | 283.1 | 100% | `False` | -379.61 | 1297.72 | -1283.68 | -424.67 |
| `bahrain` | 1 | 12.2 | 285.0 | 100% | `False` | -371.98 | 1455.81 | -1441.94 | -422.56 |
| `bahrain` | 2 | 18.4 | 285.3 | 100% | `False` | -369.00 | 1516.00 | -1502.20 | -421.68 |
| `bahrain` | 3 | 34.4 | 286.0 | 100% | `False` | -364.01 | 1610.24 | -1596.55 | -419.98 |
| `bahrain` | 4 | 47.2 | 287.0 | 100% | `False` | -358.86 | 1718.68 | -1705.11 | -418.62 |

---

## 5. Dataset 4: `bootstrap_uncertainty.parquet` — 1,000-Iteration Cluster Bootstrap Intervals

Precomputed statistical uncertainty intervals across counterfactual behavioural adjustments ($\Delta = -50\%$ to $+50\%$) using cluster-level resampling (preserving intra-stint correlation).

### Schema & Data Types
- `stint_id` (*string*): Target stint identifier
- `feature` (*string*): Behavioral feature modified (`braking_aggression`, `throttle_transient_smoothness`, `lateral_dynamics_proxy`, `kerb_usage`, `lockup_flag_rate`)
- `delta_pct` (*float64*): Percentage change in behavioral driver input (e.g. `-20.0%`, `+15.0%`)
- `recovered_p50` (*float64*): Median expected tyre debt recovery (seconds)
- `ci_lower` (*float64*): 2.5th empirical percentile of recovery (seconds)
- `ci_upper` (*float64*): 97.5th empirical percentile of recovery (seconds)
- `ci_margin` (*float64*): Half-width uncertainty interval $(CI_{upper} - CI_{lower}) / 2$
- `is_saturated` (*bool*): True if hypothetical change breaches physical grip limits
- `max_physical_bound` (*float64*): Maximum physically attainable time recovery bound (seconds)

### Sample Records (Top 5 Rows)
```json
[
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "feature":"braking_aggression",
    "delta_pct":-50.0,
    "recovered_p50":-1.53,
    "ci_lower":-3.559,
    "ci_upper":0.993,
    "ci_margin":2.276,
    "is_saturated":false,
    "max_physical_bound":4.2
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "feature":"braking_aggression",
    "delta_pct":-45.0,
    "recovered_p50":-1.389,
    "ci_lower":-3.395,
    "ci_upper":0.897,
    "ci_margin":2.146,
    "is_saturated":false,
    "max_physical_bound":4.2
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "feature":"braking_aggression",
    "delta_pct":-40.0,
    "recovered_p50":-1.244,
    "ci_lower":-3.194,
    "ci_upper":0.8,
    "ci_margin":1.997,
    "is_saturated":false,
    "max_physical_bound":4.2
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "feature":"braking_aggression",
    "delta_pct":-35.0,
    "recovered_p50":-1.097,
    "ci_lower":-2.952,
    "ci_upper":0.702,
    "ci_margin":1.827,
    "is_saturated":false,
    "max_physical_bound":4.2
  },
  {
    "stint_id":"2024_abu_dhabi_R_ALB_1",
    "feature":"braking_aggression",
    "delta_pct":-30.0,
    "recovered_p50":-0.946,
    "ci_lower":-2.663,
    "ci_upper":0.604,
    "ci_margin":1.633,
    "is_saturated":false,
    "max_physical_bound":4.2
  }
]
```

### Formatted Sample Table
| stint_id | feature | delta_pct | recovered_p50 (s) | 95% CI Lower | 95% CI Upper | CI Margin (±s) | Saturated? | Max Physical (s) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `2024_abu_dhabi_R_ALB_1` | `braking_aggression` | -50.0% | **-1.530** | -3.559 | 0.993 | ±2.276 | `False` | 4.2 |
| `2024_abu_dhabi_R_ALB_1` | `braking_aggression` | -45.0% | **-1.389** | -3.395 | 0.897 | ±2.146 | `False` | 4.2 |
| `2024_abu_dhabi_R_ALB_1` | `braking_aggression` | -40.0% | **-1.244** | -3.194 | 0.800 | ±1.997 | `False` | 4.2 |
| `2024_abu_dhabi_R_ALB_1` | `braking_aggression` | -35.0% | **-1.097** | -2.952 | 0.702 | ±1.827 | `False` | 4.2 |
| `2024_abu_dhabi_R_ALB_1` | `braking_aggression` | -30.0% | **-0.946** | -2.663 | 0.604 | ±1.633 | `False` | 4.2 |

---

## 6. Dataset 5: `baseline_predictions.parquet` — Stage 1 Linear M1 Lap Time Loss Baseline

Stores the frozen parsimonious baseline predictions for all laps across target sessions.

### Schema & Data Types
- `stint_id` (*string*): Stint identifier
- `lap_number` (*int64*): Lap number
- `actual_lap_time_loss` (*float64*): Actual lap time loss over stint minimum pace
- `predicted_lap_time_loss` (*float64*): Baseline linear model prediction
- `model_version` (*string*): Model version string

### Formatted Sample Table
| stint_id | lap_number | actual_loss (s) | predicted_loss (s) | model_version |
| :--- | :---: | :---: | :---: | :--- |
| `2024_abu_dhabi_R_ALB_1` | 4 | 0.000 | 0.357 | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 5 | 0.309 | 0.397 | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 6 | 0.755 | 0.437 | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 7 | 0.257 | 0.477 | `v4_m1_production_2026-09-10` |
| `2024_abu_dhabi_R_ALB_1` | 8 | 0.645 | 0.517 | `v4_m1_production_2026-09-10` |

---

## 7. Relational SQLite Schema (`api/tyredebt.db`)

The relational layer integrates telemetry with high-level Grand Prix metadata and ML model registries.

### Table Inventory & Purpose
1. `seasons`: Supported calendar seasons (2024, 2025) and status.
2. `events`: Grand Prix weekends with round numbers, dates, locations, countries.
3. `sessions`: Practice, Qualifying, and Race session entries with date/time.
4. `drivers`: Full driver registry (VER, HAM, NOR, LEC, etc.) with team names and car numbers.
5. `circuits`: Circuit metadata (lengths, lap records, corner counts, DRS zones, coordinates).
6. `circuit_geometry`: Normalized coordinate splines for live 2D/3D map tracking.
7. `stints`: Tyre stint metadata (compound, start/end laps, total laps, tyre age).
8. `laps`: Normalized lap times, weather flags, sector splits.
9. `baseline_models`: Registered Stage 1 baseline models, parameters, training split manifests, and RMSE.
10. `stage3_models`: Trained PyTorch TCN architectures, causal convolutional weights, embedding dimensions, and test metrics.
