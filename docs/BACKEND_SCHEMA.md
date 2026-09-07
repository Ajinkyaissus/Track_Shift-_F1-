# Backend Schema — Tyre Debt

Ties to: ARCHITECTURE.md §5 (Storage: Parquet + SQLite), §8 (API Layer), RULES.md
#3–5 (coefficient lookup, no per-request retrain, load-once), MASTER_PROMPT.md
gap-fixes #2 (confound covariates), #5 (stint boundary), #6 (baseline functional form).

## 1. Storage split — what goes where and why

- **SQLite** — small, indexed, relational metadata: races, sessions, stints, drivers,
  tracks, model version registry. Anything the API queries by ID/filter at request time.
- **Parquet** — bulk lap-level and residual-level precompute: laps, features, residual
  ledger. Read once into memory or via pandas at process start / batch job, never
  queried row-by-row live (RULES.md #5).
- Nothing in this system is Postgres-justified — dataset is static/historical, no
  concurrent writes, per ARCHITECTURE.md §5.

## 2. SQLite schema (DDL-level)

```sql
CREATE TABLE tracks (
  track_id        TEXT PRIMARY KEY,     -- e.g. "monza"
  name            TEXT NOT NULL,
  country         TEXT
);

CREATE TABLE drivers (
  driver_id       TEXT PRIMARY KEY,     -- FastF1 driver code, e.g. "VER"
  full_name       TEXT NOT NULL,
  team            TEXT,
  reputation_tag  TEXT CHECK(reputation_tag IN
                    ('aggressive','tyre_management','neutral','unlabeled'))
                    DEFAULT 'unlabeled'
  -- reputation_tag is manually curated from public reporting, used ONLY for the
  -- attribution sanity check (PRD.md §8) — never fed into the model as a feature.
  -- Feeding it in would be circular: validating the model against a label the
  -- model itself could learn to game.
);

CREATE TABLE races (
  race_id         TEXT PRIMARY KEY,     -- "2024_monza"
  season          INTEGER NOT NULL,
  round           INTEGER NOT NULL,
  track_id        TEXT NOT NULL REFERENCES tracks(track_id),
  event_date      TEXT NOT NULL         -- ISO date
);

CREATE TABLE sessions (
  session_id      TEXT PRIMARY KEY,     -- "2024_monza_R"
  race_id         TEXT NOT NULL REFERENCES races(race_id),
  session_type    TEXT NOT NULL CHECK(session_type IN ('FP1','FP2','FP3','Q','R')),
  weather_flag    TEXT CHECK(weather_flag IN ('dry','wet','mixed')) NOT NULL,
                                         -- dynamically derived from session.weather_data (Rainfall > 0)
  track_evolution_index REAL            -- computed per-session as the median lap-time delta between the first and last quintile of green-flag laps
                                         -- confound covariate — MASTER_PROMPT gap-fix #2
);

CREATE TABLE stints (
  stint_id        TEXT PRIMARY KEY,     -- "2024_monza_R_VER_1"
  session_id      TEXT NOT NULL REFERENCES sessions(session_id),
  driver_id       TEXT NOT NULL REFERENCES drivers(driver_id),
  compound        TEXT NOT NULL CHECK(compound IN ('SOFT','MEDIUM','HARD',
                                                     'INTERMEDIATE','WET')),
  start_lap       INTEGER NOT NULL,
  end_lap         INTEGER NOT NULL,
  tyre_age_start  INTEGER NOT NULL DEFAULT 0,
  is_valid        BOOLEAN NOT NULL DEFAULT 1
  -- is_valid = 0 for stints excluded by the boundary rule (MASTER_PROMPT gap-fix #5):
  -- SC/VSC/red-flag-affected, or straddling a compound change. Excluded stints stay
  -- in the table (auditable) but never surface in /stints or /races results.
);

CREATE TABLE model_registry (
  model_version   TEXT PRIMARY KEY,     -- "v3_stage3_2026-09-01"
  stage           INTEGER NOT NULL CHECK(stage IN (1,3)),  -- Stage 1 baseline, Stage 3 attribution
  trained_at      TEXT NOT NULL,
  held_out_metric REAL,                 -- real measured R²/correlation, NULL until measured
  split_method    TEXT NOT NULL DEFAULT 'chronological_by_race_weekend',
  is_active       BOOLEAN NOT NULL DEFAULT 0  -- exactly one active row per stage
);

CREATE TABLE model_coefficients (
  model_version   TEXT NOT NULL REFERENCES model_registry(model_version),
  feature_name    TEXT NOT NULL CHECK(feature_name IN
                    ('braking_aggression','throttle_transient_smoothness',
                     'lateral_dynamics_proxy','kerb_usage','lockup_flag_rate')),
  coefficient     REAL NOT NULL,        -- linear coeff, or shape-function ref below
  shape_function_ref TEXT,              -- NULL for linear; points to a GAM shape
                                         -- table if EBM/GAM is used instead of pure linear
  track_scope     TEXT,                 -- NULL = global; else a track_id if fit per-track
  PRIMARY KEY (model_version, feature_name, track_scope)
);
```

## 3. Parquet artifacts (schema, not SQL)

```
laps.parquet
  stint_id, lap_number, lap_time, is_green_flag, fuel_load_est,
  braking_aggression, throttle_transient_smoothness, lateral_dynamics_proxy,
  kerb_usage, lockup_flag_rate

  -- Feature engineering output, one row per lap. Confound covariates
  -- (track_id, session_type, weather_flag) are joined in from SQLite at
  -- feature-build time, not re-derived at query time.

  -- NONE of the behavioral features above are raw FastF1/OpenF1 channels.
  -- The public F1 telemetry feed (both libraries read the same underlying
  -- source) only exposes: Speed, RPM, nGear, Throttle (0-100%), Brake (BOOLEAN,
  -- not pressure), DRS, X/Y/Z position. There is no steering angle channel in
  -- any public source. Derivations, locked:
  --   braking_aggression        = deceleration rate (d(Speed)/dt) during
  --                                Brake=True windows, plus brake-point timing
  --                                relative to a corner reference. NOT a raw
  --                                brake-pressure value -- that field doesn't
  --                                exist publicly.
  --   lateral_dynamics_proxy    = curvature / lateral-g estimate computed from
  --                                the X/Y position trace per corner segment.
  --                                Replaces "steering_angle_variance" -- that
  --                                name implied a raw channel that isn't public.
  --                                Rename anywhere else it still appears
  --                                (PRD.md, RULES.md, DESIGN.md, ARCHITECTURE.md,
  --                                UIUX_BRIEF.md, APP_FLOW.md) before Phase 1.
  --   throttle_transient_smoothness = derived from the raw Throttle (0-100%)
  --                                channel, which IS a real field -- no issue here.
  --   kerb_usage, lockup_flag_rate  = derived from position/speed traces
  --                                relative to track geometry -- also derived,
  --                                not raw fields.
  -- Every one of these must be documented as a derived/estimated feature with
  -- its derivation method stated wherever it's reported (same discipline as
  -- fuel_load_est being called an estimate, not a measured value) -- RULES.md #11.

baseline_predictions.parquet
  stint_id, lap_number, predicted_lap_time_loss, model_version

  -- Stage 1 output. Functional form (locked, MASTER_PROMPT gap-fix #6):
  -- lap_time_loss ~ tyre_age + tyre_age^2 + compound + fuel_load_est
  --                 + track_id + track_evolution_index
  -- Track handled as categorical fixed effect. If this changes, bump model_version,
  -- don't overwrite in place.

residual_ledger.parquet
  stint_id, lap_number, actual_lap_time_loss, predicted_lap_time_loss,
  residual, cumulative_debt

  -- Stage 2 output. residual = actual - predicted. cumulative_debt = running sum.
  -- This is what /stints/{id}/ledger serves directly — no computation on request path.
```

## 4. API contracts

All responses are precomputed lookups except `/counterfactual` (RULES.md #4).
Field names match the Parquet/SQLite columns above exactly — no silent renaming
between storage and API layer.

### `GET /races`
```json
[
  { "race_id": "2024_monza", "season": 2024, "round": 16,
    "track_id": "monza", "event_date": "2024-09-01" }
]
```

### `GET /sessions/{race_id}/stints`
```json
[
  { "stint_id": "2024_monza_R_VER_1", "session_id": "2024_monza_R",
    "driver_id": "VER", "compound": "MEDIUM",
    "start_lap": 1, "end_lap": 22, "tyre_age_start": 0 }
]
```

### `GET /stints/{id}/ledger`
```json
{
  "stint_id": "2024_monza_R_VER_1",
  "model_version": "v3_stage1_2026-09-01",
  "series": [
    { "lap_number": 1, "residual": 0.02, "cumulative_debt": 0.02 },
    { "lap_number": 2, "residual": -0.01, "cumulative_debt": 0.01 }
  ]
}
```

### `GET /stints/{id}/attribution`
```json
{
  "stint_id": "2024_monza_R_VER_1",
  "model_version": "v3_stage3_2026-09-01",
  "attribution": [
    { "feature": "braking_aggression", "pct_contribution": 42.0,
      "coefficient": 0.12, "unit": "seconds debt per 1% braking aggression" }
  ]
}
```
`coefficient` is mandatory in every attribution row — DESIGN.md requires the
coefficient shown alongside every attribution line, not just a percentage.

### `POST /stints/{id}/counterfactual`
Request:
```json
{ "feature": "braking_aggression", "delta_pct": -15 }
```
Response:
```json
{
  "feature": "braking_aggression",
  "delta_pct": -15,
  "recovered_laps": 1.8,
  "model_version": "v3_stage3_2026-09-01",
  "compute_path": "server_lookup",
  "measured_latency_ms": 34
}
```
`compute_path` is mandatory: `"server_lookup"` or `"client_lookup"` — never
ambiguous about where the number came from (MASTER_PROMPT gap-fix #4, DESIGN.md
"state this choice explicitly, don't hide it"). Computation itself is
`coefficient × (delta_pct / 100) × avg_feature_value_over_stint`, converted from
seconds-of-debt to laps via the stint's own baseline degradation-per-lap rate —
no re-inference, no perturb-and-rerun (RULES.md #3/#4).

## 5. Model load-at-startup contract (RULES.md #5)

On API process start:
1. Query `model_registry` for `is_active = 1` rows (one per stage).
2. Load corresponding `model_coefficients` rows into an in-memory dict keyed by
   `(feature_name, track_scope)`.
3. Reject startup if any active model has `held_out_metric IS NULL` in a
   production/demo build — an unmeasured model must not be silently served as if
   validated (ties to RULES.md #14).
4. No coefficient lookup, disk read, or deserialization happens on the request path
   after this point — confirmed by the Phase 5 gate in PHASE.md.
