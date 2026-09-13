"""
TrackShift — Contextual Feature Provenance Catalog (Audited)
============================================================
Documents the exact source, raw telemetry field, transformation, time availability,
and scientific classification for every contextual variable.

Variable Classification:
- REAL MEASUREMENT: Direct FIA timing or 100Hz telemetry
- OBSERVABLE PROXY: Physically bounded mathematical estimation
- MODEL-DERIVED FEATURE: Multi-head neural network output

Scientific hardening (2026-09):
- fuel proxy coefficient corrected to 0.033 s/kg (canonical production FUEL_EFFECT_COEFFICIENT).
  Previous incorrect entry stated -0.018 s/kg (research/dead-path coefficient).
- tyre_age raw_fields updated to include FastF1 TyreLife field.
"""

from dataclasses import dataclass
from typing import Dict, List, Any


@dataclass
class FeatureProvenance:
    feature_name: str
    category: str
    feature_nature: str  # 'REAL MEASUREMENT' | 'OBSERVABLE PROXY' | 'MODEL-DERIVED FEATURE'
    source: str
    raw_fields: List[str]
    transformation: str
    derivation: str
    unit: str
    time_availability: str
    scientific_status: str
    nomenclature: str


FEATURE_PROVENANCE_CATALOG: List[Dict[str, Any]] = [
    {
        "feature_name": "tyre_age",
        "category": "Tyre & Session Context",
        "feature_nature": "REAL MEASUREMENT",
        "source": "FastF1 / Official FIA timing (TyreLife field)",
        "raw_fields": ["TyreLife", "LapNumber", "stint_start_lap"],
        "transformation": "tyre_age_start + (lap_number - start_lap); primary source: FastF1 TyreLife",
        "derivation": "tyre_age_start + (lap_number - start_lap); gap-preserving (missing laps maintain physical age)",
        "unit": "laps",
        "time_availability": "Available online at current lap N",
        "scientific_status": "PRODUCTION (Stage 1 Core)",
        "nomenclature": "Observable Tyre Age (laps)",
        "provenance_source": "dataset_field (TyreLife via FastF1) or reconstructed_from_stint_history"
    },
    {
        "feature_name": "compound",
        "category": "Tyre & Session Context",
        "feature_nature": "REAL MEASUREMENT",
        "source": "Pirelli / FastF1 compound allocation",
        "raw_fields": ["Compound"],
        "transformation": "Categorical string mapped to one-hot or baseline offset",
        "derivation": "Categorical string mapped to one-hot or baseline offset",
        "unit": "categorical (SOFT/MEDIUM/HARD/INTER/WET)",
        "time_availability": "Available pre-stint / online",
        "scientific_status": "PRODUCTION (Stage 1 & Stint Attribution)",
        "nomenclature": "Tyre Compound Specification"
    },
    {
        "feature_name": "load_fuel_proxy",
        "category": "Fuel & Load Proxy",
        "feature_nature": "OBSERVABLE PROXY",
        "source": "FastF1 session model / stint progression",
        "raw_fields": ["fuel_load_est", "lap_number", "total_session_laps"],
        "transformation": "Estimated initial session load (~110kg) decaying by ~1.7kg/lap (0.033 s/kg)",
        "derivation": "fuel_est_kg * 0.033 s/kg (canonical FUEL_EFFECT_COEFFICIENT)",
        "unit": "kg / seconds offset (Observable Proxy)",
        "time_availability": "Available online at current lap N",
        "scientific_status": "RESEARCH / CONTEXTUAL PROXY",
        "nomenclature": "Observable Load / Fuel Proxy (Never True Fuel Weight)",
        "coefficient": 0.033,
        "coefficient_unit": "s/kg",
        "coefficient_source": "trackshift.domain_constants.FUEL_EFFECT_COEFFICIENT",
        "coefficient_note": "Canonical production value. Research code may use -0.018 (quarantined in tyre_intelligence/research/)."
    },
    {
        "feature_name": "track_evolution_proxy",
        "category": "Track Evolution",
        "feature_nature": "OBSERVABLE PROXY",
        "source": "Field-wide clean lap time progression up to lap N",
        "raw_fields": ["lap_time", "is_green_flag"],
        "transformation": "Rolling median field green-flag lap time relative to session baseline",
        "derivation": "track_evolution_index * 0.35",
        "unit": "seconds gain / lap (Observable Proxy)",
        "time_availability": "Strictly past-only: information_timestamp <= N",
        "scientific_status": "RESEARCH / CONTEXTUAL PROXY",
        "nomenclature": "Observable Track-Evolution Proxy (Never Physical Grip)"
    },
    {
        "feature_name": "traffic_context_score",
        "category": "Traffic Context",
        "feature_nature": "MODEL-DERIVED FEATURE",
        "source": "Session flags, lockup events, and relative delta telemetry",
        "raw_fields": ["is_green_flag", "lockup_flag_rate", "lap_time"],
        "transformation": "Composite penalty index: 1.0 - is_green_flag + (0.5 * lockup_flag_rate)",
        "derivation": "(1.0 - is_green + 0.5 * lockup) * 0.45",
        "unit": "score [0, 1] (Model-Derived Feature)",
        "time_availability": "Available online at current lap N",
        "scientific_status": "RESEARCH / CONTEXTUAL PROXY",
        "nomenclature": "Observable Traffic Context Score (Never Physical Distance)"
    },
    {
        "feature_name": "braking_aggression",
        "category": "Driving Behaviour",
        "feature_nature": "REAL MEASUREMENT",
        "source": "FastF1 100Hz brake telemetry & longitudinal decel",
        "raw_fields": ["Brake", "Speed", "Distance"],
        "transformation": "Mean peak deceleration rate across heavy braking events (m/s²)",
        "derivation": "mean peak decel / reference baseline",
        "unit": "m/s² / normalized",
        "time_availability": "Available online at current lap N",
        "scientific_status": "PRODUCTION (Stage 3 TCN Head)",
        "nomenclature": "Braking Aggression Index"
    },
    {
        "feature_name": "throttle_transient_smoothness",
        "category": "Driving Behaviour",
        "feature_nature": "REAL MEASUREMENT",
        "source": "FastF1 100Hz throttle telemetry",
        "raw_fields": ["Throttle", "Time"],
        "transformation": "Inverse standard deviation of throttle slew rate on corner exit (s)",
        "derivation": "inv_std(dThrottle/dt)",
        "unit": "seconds / normalized",
        "time_availability": "Available online at current lap N",
        "scientific_status": "PRODUCTION (Stage 3 TCN Head)",
        "nomenclature": "Throttle Transient Smoothness (s)"
    },
    {
        "feature_name": "lateral_dynamics_proxy",
        "category": "Driving Behaviour",
        "feature_nature": "REAL MEASUREMENT",
        "source": "FastF1 GPS curvature & apex speed",
        "raw_fields": ["X", "Y", "Speed"],
        "transformation": "Apex speed divided by corner curvature proxy",
        "derivation": "v_apex / kappa",
        "unit": "m²/s / normalized",
        "time_availability": "Available online at current lap N",
        "scientific_status": "PRODUCTION (Stage 3 TCN Head)",
        "nomenclature": "Lateral Dynamics Proxy"
    },
    {
        "feature_name": "kerb_usage",
        "category": "Driving Behaviour",
        "feature_nature": "REAL MEASUREMENT",
        "source": "GPS track corridor boundary excursion",
        "raw_fields": ["x_rot", "y_rot", "circuit_boundaries"],
        "transformation": "Cumulative lateral track limit deviation per lap (mm)",
        "derivation": "sum(max(0, lateral_disp - track_width))",
        "unit": "mm",
        "time_availability": "Available online at current lap N",
        "scientific_status": "PRODUCTION (Stage 3 TCN Head)",
        "nomenclature": "Kerb Usage Index (mm)"
    },
    {
        "feature_name": "stage3_anomaly_score",
        "category": "Driving Behaviour",
        "feature_nature": "MODEL-DERIVED FEATURE",
        "source": "TCN Anomaly Detection Output Head",
        "raw_fields": ["16-dim latent temporal embedding"],
        "transformation": "Sigmoid-activated reconstruction deviation score [0, 1]",
        "derivation": "sigmoid(W_a * h_t + b_a)",
        "unit": "score [0, 1]",
        "time_availability": "Available online at current lap N",
        "scientific_status": "PRODUCTION (Stage 3 TCN Head)",
        "nomenclature": "Behavioral Anomaly Score"
    },
    {
        "feature_name": "stage3_behavioral_drift",
        "category": "Driving Behaviour",
        "feature_nature": "MODEL-DERIVED FEATURE",
        "source": "TCN Drift Detection Output Head",
        "raw_fields": ["Temporal latent sequence deltas"],
        "transformation": "Cosine distance between rolling embedding window and stint baseline [0, 1]",
        "derivation": "1 - cos_sim(h_t, h_baseline)",
        "unit": "drift distance [0, 1]",
        "time_availability": "Available online at current lap N",
        "scientific_status": "PRODUCTION (Stage 3 TCN Head)",
        "nomenclature": "Behavioral Drift Metric"
    }
]

CONTEXT_FEATURE_CATALOG = FEATURE_PROVENANCE_CATALOG


def get_provenance_catalog_dict() -> List[Dict[str, Any]]:
    return FEATURE_PROVENANCE_CATALOG
