CREATE TABLE IF NOT EXISTS tracks (
  track_id        TEXT PRIMARY KEY,     -- e.g. "monza"
  name            TEXT NOT NULL,
  country         TEXT,
  country_code    TEXT,
  location        TEXT,
  rotation        REAL DEFAULT 0,
  map_available   BOOLEAN DEFAULT 1,
  telemetry_available BOOLEAN DEFAULT 0
);

CREATE TABLE IF NOT EXISTS circuit_corners (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  circuit_id      TEXT NOT NULL REFERENCES tracks(track_id),
  corner_number   INTEGER NOT NULL,
  corner_letter   TEXT,
  x               REAL NOT NULL,
  y               REAL NOT NULL,
  angle           REAL,
  distance        REAL
);

CREATE TABLE IF NOT EXISTS drivers (
  driver_id       TEXT PRIMARY KEY,     -- FastF1 driver code, e.g. "VER"
  full_name       TEXT NOT NULL,
  team            TEXT,
  reputation_tag  TEXT CHECK(reputation_tag IN
                    ('aggressive','tyre_management','neutral','unlabeled'))
                    DEFAULT 'unlabeled'
);

CREATE TABLE IF NOT EXISTS races (
  race_id         TEXT PRIMARY KEY,     -- "2024_monza"
  season          INTEGER NOT NULL,
  round           INTEGER NOT NULL,
  track_id        TEXT NOT NULL REFERENCES tracks(track_id),
  event_date      TEXT NOT NULL,        -- ISO date
  event_name      TEXT NOT NULL         -- FastF1 EventName
);

CREATE TABLE IF NOT EXISTS sessions (
  session_id      TEXT PRIMARY KEY,     -- "2024_monza_R"
  race_id         TEXT NOT NULL REFERENCES races(race_id),
  session_type    TEXT NOT NULL CHECK(session_type IN ('FP1','FP2','FP3','Q','R')),
  weather_flag    TEXT CHECK(weather_flag IN ('dry','wet','mixed','unknown')) NOT NULL,
  track_evolution_index REAL            -- precomputed session-level scalar
);

CREATE TABLE IF NOT EXISTS stints (
  stint_id        TEXT PRIMARY KEY,     -- "2024_monza_R_VER_1"
  session_id      TEXT NOT NULL REFERENCES sessions(session_id),
  driver_id       TEXT NOT NULL REFERENCES drivers(driver_id),
  compound        TEXT NOT NULL CHECK(compound IN ('SOFT','MEDIUM','HARD',
                                                     'INTERMEDIATE','WET')),
  start_lap       INTEGER NOT NULL,
  end_lap         INTEGER NOT NULL,
  tyre_age_start  INTEGER NOT NULL DEFAULT 0,
  is_valid        BOOLEAN NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS provenance (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  source          TEXT NOT NULL,        -- "FastF1"
  season          INTEGER NOT NULL,
  event_name      TEXT NOT NULL,
  round_number    INTEGER NOT NULL,
  circuit_id      TEXT NOT NULL,
  session_type    TEXT NOT NULL,
  session_date    TEXT,
  retrieved_at    TEXT NOT NULL,
  notes           TEXT
);

CREATE TABLE IF NOT EXISTS model_registry (
  model_version   TEXT PRIMARY KEY,     -- "v3_stage3_2026-09-01"
  stage           INTEGER NOT NULL CHECK(stage IN (1,3)),  -- Stage 1 baseline, Stage 3 attribution
  trained_at      TEXT NOT NULL,
  held_out_metric REAL,                 -- real measured R²/correlation, NULL until measured
  split_method    TEXT NOT NULL DEFAULT 'chronological_by_race_weekend',
  is_active       BOOLEAN NOT NULL DEFAULT 0  -- exactly one active row per stage
);

CREATE TABLE IF NOT EXISTS model_coefficients (
  model_version   TEXT NOT NULL REFERENCES model_registry(model_version),
  feature_name    TEXT NOT NULL CHECK(feature_name IN
                    ('braking_aggression','throttle_transient_smoothness',
                     'lateral_dynamics_proxy','kerb_usage','lockup_flag_rate')),
  coefficient     REAL NOT NULL,        -- linear coeff, or shape-function ref below
  shape_function_ref TEXT,              -- NULL for linear; points to a GAM shape
  track_scope     TEXT,                 -- NULL = global; else a track_id if fit per-track
  PRIMARY KEY (model_version, feature_name, track_scope)
);
