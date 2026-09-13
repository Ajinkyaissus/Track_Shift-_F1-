# TrackShift — Scientific Method & Architecture

## Overview

TrackShift is a three-stage tyre degradation and race-intelligence analysis system
for F1 data from the 2024 and 2025 seasons. It explicitly distinguishes between
*observable data* and *inferred physical quantities*, and all production output is
accompanied by a provenance chain.

---

## 3-Stage Architecture

### Stage 1 — M1 Linear Tyre Age Baseline (FROZEN)

**Purpose**: Estimate baseline tyre degradation as a function of tyre age (laps on
the current set), corrected for fuel load.

**Model**: Ordinary Least Squares linear regression.

`
y_hat = STAGE1_M1_INTERCEPT + STAGE1_M1_SLOPE x max(0, tyre_age)
`

**Frozen Constants** (see `trackshift/domain_constants.py`):

| Constant | Value | Unit |
|:---|:---:|:---|
| `STAGE1_M1_INTERCEPT` | **0.1974** | seconds |
| `STAGE1_M1_SLOPE` | **0.0400** | seconds / lap of tyre age |
| `FUEL_EFFECT_COEFFICIENT` | **0.033** | seconds / kg of estimated fuel |

> These constants are **FROZEN PRODUCTION BASELINES**. They must not be retuned
> without a full blocked chronological re-validation on >= 3,372 laps across >= 10 events.
> All production code must import them from `trackshift.domain_constants`.

**Validation split**: Chronological event split — training set on earlier events,
test set on held-out events from the same season. No random-shuffle leakage.

---

### Stage 2 — Tyre Debt Accumulation

**Formula**: debt at lap L = sum of (y_i - y_hat_M1(tyre_age_i)) for i in [1, L]

Tyre debt is **non-negative by construction** — negative residuals are clamped to 0.

**Confounder adjustments** (observable proxies, ablation layer):
- Track evolution: TRACK_EVOLUTION_COEFFICIENT x lap_grip_proxy
- Traffic effect: TRAFFIC_EFFECT_COEFFICIENT x traffic_units

These are labeled as observable proxy corrections, NOT frozen M1 constants.

---

### Stage 3 — TCN Temporal Behavioral Modeling

**Purpose**: Capture temporal patterns in driver behavior via a Temporal Convolutional Network.

Key invariants:
1. Causal boundary enforced — no future lap data leaks into any embedding.
2. Three-state temporal isolation (PRE_RACE, IN_RACE, POST_RACE) prevents future leakage.
3. 16-dimensional behavioral embedding representing driver behavioral pattern.
4. Stage 3 supplements but does not replace the frozen M1 baseline.

---

## Frozen vs Observable vs Research Constants

| Category | Examples | Status |
|:---|:---|:---|
| Frozen Production | STAGE1_M1_INTERCEPT=0.1974, STAGE1_M1_SLOPE=0.0400, FUEL_EFFECT_COEFFICIENT=0.033 | FROZEN |
| Observable Proxy | TRACK_EVOLUTION_COEFFICIENT=-0.008, TRAFFIC_EFFECT_COEFFICIENT=0.250 | Research/ablation |
| Quarantined (dead) | -0.018 (contextual fuel proxy), 0.035 (legacy fuel proxy) | Quarantined to research/archived/ |

---

## Data Foundation

- Seasons: 2024 and 2025 only. No 2022 or 2023 data is ingested.
- Source: FastF1 library with authenticated ergast API.
- Granularity: Lap-by-lap telemetry (lap time, sector times, tyre compound, tyre age).
- Combined dataset: data/combined_2024_2025_laps.parquet

---

## Non-Negotiable Invariants (enforced by test suite)

1. M1 constants must have exactly one source of truth (trackshift/domain_constants.py).
2. Stage 2 tyre debt must be non-negative (clamped at 0).
3. Stage 3 TCN must not use any future lap features (causal boundary).
4. No 2022 or 2023 data must reach the production pipeline.
5. Tyre age must be derived from chronologically sorted laps — no shuffle leakage.
6. Post-race validation must run at +5, +10, and +15 lap horizons.
7. Bootstrap uncertainty intervals must be derived from >= 200 bootstrap samples.
8. All provenance chains must include event, lap range, and compound for every calculation.
