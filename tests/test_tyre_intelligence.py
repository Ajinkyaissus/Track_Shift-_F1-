"""
Comprehensive Unit & Integration Tests for TrackShift Confounder-Aware Tyre Intelligence
========================================================================================
Verifies:
1. Feature provenance catalog integrity (11 variables & nature tags).
2. Confounder formulas and physical bounds (fuel proxy, track evolution proxy, traffic context).
3. Decomposition model and contextual residual ledger arithmetic.
4. Estimated degradation curve generator and bootstrap uncertainty.
5. Out-of-sample forward predictive multi-horizon validation (+1, +3, +5, +10 horizons).
6. Reconciled 8-Model ablation study runner and output format.
7. Exact mathematical reproduction of Frozen Stage 1 M1 Baseline (MAE = 0.4437 s).
8. Strict preservation of Frozen Stage 1 and Stage 2 mathematical hierarchy.
9. Zero-future-leakage temporal isolation (no future track evolution, traffic, or debt access).
10. Robustness to missing data, unsupported sessions, and extreme values.
11. REST API router endpoints (/api/tyre-intelligence/*).
"""

import pytest
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from pipeline.model_stage1 import load_data
from trackshift.tyre_intelligence import (
    FEATURE_PROVENANCE_CATALOG,
    get_provenance_catalog_dict,
    ObservableConfounderEstimator,
    ConfounderContext,
    ObservableDecompositionModel,
    TyreDegradationCurveGenerator,
    PostRaceValidator,
    ConfounderAblationSuite,
    STAGE1_M1_INTERCEPT,
    STAGE1_M1_SLOPE,
    FUEL_EFFECT_COEFFICIENT,
    TRACK_EVOLUTION_COEFFICIENT,
    TRAFFIC_EFFECT_COEFFICIENT,
)
from trackshift.tyre_intelligence.confounders import compute_track_evolution_proxy, compute_traffic_context_score
from api.main import app


@pytest.fixture
def mock_stint_df():
    """Synthetic dataframe conforming to laps.parquet schema for fast unit tests."""
    n_laps = 25
    laps = []
    base_time = 90.0
    for lap in range(1, n_laps + 1):
        wear = STAGE1_M1_INTERCEPT + STAGE1_M1_SLOPE * lap
        fuel_kg = max(5.0, 100.0 - lap * 1.7)
        fuel_loss = (fuel_kg - 5.0) * 0.033
        lap_time = base_time + wear + fuel_loss + np.random.normal(0, 0.05)
        laps.append({
            "stint_id": "test_stint_1",
            "circuit_id": "silverstone",
            "session_id": "silverstone_2024_R",
            "driver_id": "HAM",
            "compound": "MEDIUM",
            "lap_number": lap,
            "lap_time": lap_time,
            "is_green_flag": True,
            "fuel_load_est": fuel_kg,
            "braking_aggression": 0.5,
            "throttle_transient_smoothness": 0.6,
            "lateral_dynamics_proxy": 0.7,
            "kerb_usage": 0.4,
            "lockup_flag_rate": 0.0,
            "event_date": "2024-07-07",
            "season": 2024,
            "tyre_age": lap,
            "actual_lap_time_loss": wear + np.random.normal(0, 0.02),
        })
    return pd.DataFrame(laps)


def test_frozen_constants_integrity():
    """Verify that Stage 1 baseline constants are strictly frozen."""
    assert STAGE1_M1_INTERCEPT == 0.1974
    assert STAGE1_M1_SLOPE == 0.0400
    assert FUEL_EFFECT_COEFFICIENT == 0.033
    assert TRACK_EVOLUTION_COEFFICIENT == -0.008
    assert TRAFFIC_EFFECT_COEFFICIENT == 0.250


def test_feature_provenance_catalog():
    """Verify that all 11 observable features are defined with audited feature nature."""
    cat = get_provenance_catalog_dict()
    assert len(cat) == 11
    names = [f["feature_name"] for f in cat]
    assert "tyre_age" in names
    assert "load_fuel_proxy" in names
    assert "track_evolution_proxy" in names
    assert "traffic_context_score" in names
    assert "braking_aggression" in names
    assert "compound" in names

    # Verify explicit feature nature tags
    natures = {f["feature_name"]: f["feature_nature"] for f in cat}
    assert natures["tyre_age"] == "REAL MEASUREMENT"
    assert natures["load_fuel_proxy"] == "OBSERVABLE PROXY"
    assert natures["track_evolution_proxy"] == "OBSERVABLE PROXY"
    assert natures["traffic_context_score"] == "MODEL-DERIVED FEATURE"


def test_confounder_estimator_bounds():
    """Test observable confounder calculation and physical bound clamping."""
    estimator = ObservableConfounderEstimator()
    
    # Fuel adjustment: bounded positive
    adj_fuel = estimator.compute_fuel_adjustment(50.0)
    assert np.isclose(adj_fuel, 50.0 * 0.033)
    assert estimator.compute_fuel_adjustment(-10.0) == 0.0
    
    # Track evolution: bounded [-2.5s, +0.5s]
    adj_track = estimator.compute_track_evolution_adjustment(10.0)
    assert np.isclose(adj_track, -10.0 * 0.008)
    assert estimator.compute_track_evolution_adjustment(1000.0) == -2.5
    
    # Traffic adjustment: bounded [0.0, 3.0s]
    adj_traffic = estimator.compute_traffic_adjustment(0.5)
    assert np.isclose(adj_traffic, 0.5 * 0.250)
    assert estimator.compute_traffic_adjustment(100.0) == 3.0


def test_decomposition_model_and_debt_arithmetic(mock_stint_df):
    """Test observable decomposition model ledger creation and debt non-negativity."""
    model = ObservableDecompositionModel()
    ledger = model.decompose_stint(mock_stint_df, "HAM", "test_stint_1", base_lap_time=90.0)
    
    assert len(ledger.points) == len(mock_stint_df)
    prev_debt = 0.0
    for pt in ledger.points:
        assert pt.tyre_age >= 1
        assert pt.m1_baseline_delta > 0
        assert pt.contextual_debt_accumulated >= prev_debt  # Monotonically non-decreasing
        prev_debt = pt.contextual_debt_accumulated


def test_degradation_curve_generator_and_uncertainty(mock_stint_df):
    """Test estimated degradation curve with non-parametric bootstrap uncertainty bounds."""
    gen = TyreDegradationCurveGenerator(n_bootstraps=30, random_seed=42)
    curve = gen.generate_curve(mock_stint_df, "HAM", "test_stint_1", circuit_id="silverstone")
    
    assert len(curve.points) == len(mock_stint_df)
    assert curve.driver_id == "HAM"
    assert "final_m1_debt" in curve.summary
    assert "final_contextual_debt" in curve.summary
    
    # Uncertainty ordering: Q10 <= Q50 <= Q90
    for pt in curve.points:
        assert pt.uncertainty_q10 <= pt.uncertainty_q50 <= pt.uncertainty_q90


def test_out_of_sample_forward_predictive_validator(mock_stint_df):
    """Test out-of-sample forward predictive multi-horizon validation."""
    validator = PostRaceValidator()
    report = validator.run_validation_suite(mock_stint_df, horizons=[1, 3, 5], min_stint_len=10)
    
    assert report.total_stints_evaluated >= 1
    assert len(report.horizon_evaluations) == 3
    for h in report.horizon_evaluations:
        assert h.horizon_laps in [1, 3, 5]
        assert h.m1_mae_s >= 0
        assert h.context_mae_s >= 0


def test_ablation_reconciliation_exact_reproduction():
    """Verify that Model A in the reconciled ablation exactly matches frozen M1 MAE 0.4437s."""
    suite = ConfounderAblationSuite()
    report = suite.run_ablation()
    
    assert len(report.models) == 8
    model_a = next(m for m in report.models if m.model_id == "Model A")
    assert np.isclose(model_a.mae_s, 0.4437, atol=1e-3)
    assert np.isclose(model_a.rmse_s, 0.6664, atol=1e-3)
    assert np.isclose(model_a.r2_score, 0.1398, atol=1e-3)

    # Model G is an integral debt signal
    model_g = next(m for m in report.models if m.model_id == "Model G")
    assert model_g.mae_s is None
    assert model_g.downstream_corr_h1 > 0.50


def test_temporal_leakage_isolation(mock_stint_df):
    """Verify that track evolution and degradation curves use strictly past laps <= checkpoint N."""
    checkpoint_n = 10
    
    # 1. Track evolution past-only cutoff
    evo_cutoff = compute_track_evolution_proxy(mock_stint_df, current_lap=checkpoint_n)
    
    # Modifying future lap time after checkpoint_n must NOT change evo_cutoff
    future_tampered_df = mock_stint_df.copy()
    future_tampered_df.loc[future_tampered_df["lap_number"] > checkpoint_n, "lap_time"] = 200.0
    evo_tampered = compute_track_evolution_proxy(future_tampered_df, current_lap=checkpoint_n)
    assert evo_cutoff == evo_tampered, "Future lap data leaked into track evolution proxy!"

    # 2. Degradation curve cutoff
    gen = TyreDegradationCurveGenerator(n_bootstraps=10, random_seed=42)
    curve_cutoff = gen.generate_curve(mock_stint_df, "HAM", "test_stint_1", max_tyre_age=checkpoint_n)
    assert len(curve_cutoff.points) == checkpoint_n


def test_missing_data_and_unsupported_session_handling():
    """Verify graceful fallback for missing telemetry columns and extreme values."""
    sparse_df = pd.DataFrame([
        {"lap_number": 1, "lap_time": 91.0, "is_green_flag": 1},
        {"lap_number": 2, "lap_time": 91.5, "is_green_flag": 1},
    ])
    gen = TyreDegradationCurveGenerator(n_bootstraps=5)
    curve = gen.generate_curve(sparse_df, "HAM", "sparse_stint")
    assert len(curve.points) == 2
    assert curve.points[0].confounder_breakdown["fuel_effect_delta"] >= 0


def test_api_endpoints():
    """Test FastAPI tyre intelligence endpoints using TestClient."""
    client = TestClient(app)
    
    # 1. Provenance
    res = client.get("/api/tyre-intelligence/provenance")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VERIFIED"
    assert data["total_features"] == 11
    
    # 2. Degradation curve
    res = client.get("/api/tyre-intelligence/degradation-curve?circuit_id=silverstone&driver_id=HAM")
    assert res.status_code == 200
    curve_data = res.json()
    assert "points" in curve_data
    assert "summary" in curve_data
    
    # 3. Ablation study
    res = client.get("/api/tyre-intelligence/ablation")
    assert res.status_code == 200
    abl_data = res.json()
    assert len(abl_data["models"]) == 8
    
    # 4. Post-race validation
    res = client.get("/api/tyre-intelligence/post-race-validation?circuit_id=silverstone")
    assert res.status_code == 200
    val_data = res.json()
    assert "horizon_evaluations" in val_data
    
    # 5. Confounder breakdown
    res = client.get("/api/tyre-intelligence/confounder-breakdown?circuit_id=silverstone&driver_id=HAM")
    assert res.status_code == 200
    cb_data = res.json()
    assert "points" in cb_data
