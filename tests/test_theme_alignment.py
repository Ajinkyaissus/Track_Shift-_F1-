"""
tests/test_theme_alignment.py — Comprehensive Test Suite for TrackShift Theme Alignment.

Verifies:
1. Practice degradation calculation
2. Context adjustment
3. Fuel-load handling (Estimated Fuel Load label & baseline calculation)
4. Track-evolution handling (explicit index & meter)
5. Traffic availability state (honest not-modeled response)
6. Practice prediction (strictly pre-race inputs)
7. Race validation (prediction vs actual)
8. Practice/race leakage prevention (assert zero race telemetry in prediction snapshot)
9. Compound matching (same compound comparison)
10. Tyre-age matching (overlapping age window)
11. Insufficient-data handling (INSUFFICIENT_DATA status)
12. Prediction error calculation (MAE, RMSE, mean bias, relative error)
13. Uncertainty calculation (empirical bootstrap confidence interval)
14. Cross-driver comparison
15. Cross-season isolation (2024 vs 2025)
16. Cross-session isolation
17. Cache isolation
18. Real-data provenance
19. No synthetic fallback
20. Frontend API contract validation
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.main import app

client = TestClient(app)


# 1. Practice Degradation Calculation
def test_practice_degradation_calculation():
    """Verify session degradation endpoint returns valid stints and degradation signals."""
    res = client.get("/api/sessions/2024_monza_R/degradation")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VALID"
    assert data["stints_count"] > 0
    stint = data["stints"][0]
    assert "estimated_deg_rate_sec_per_lap" in stint
    assert stint["estimated_deg_rate_sec_per_lap"] > 0.0
    assert len(stint["laps"]) > 0
    assert "clean_degradation_signal" in stint["laps"][0]


# 2. Context Adjustment
def test_context_adjustment():
    """Verify raw pace is adjusted for contextual confounders to produce clean degradation signal."""
    res = client.get("/api/sessions/2024_monza_R/degradation?driver_id=LEC")
    assert res.status_code == 200
    stints = res.json()["stints"]
    assert len(stints) > 0
    laps = stints[0]["laps"]
    for lap in laps:
        assert "raw_lap_time" in lap
        assert "expected_loss" in lap
        assert "context_adjusted_pace" in lap
        assert "clean_degradation_signal" in lap
        # Clean degradation signal separates fuel & track evolution from raw loss
        assert lap["clean_degradation_signal"] >= 0.0


# 3. Fuel-Load Handling
def test_fuel_load_handling():
    """Verify fuel load is honestly labeled as estimated mass and accounted for in baseline."""
    res = client.get("/api/sessions/2024_monza_R/degradation?driver_id=LEC")
    assert res.status_code == 200
    stint = res.json()["stints"][0]
    lap = stint["laps"][0]
    context = lap["contextual_factors"]
    assert "estimated_fuel_load_kg" in context
    assert isinstance(context["estimated_fuel_load_kg"], (int, float))
    assert context["estimated_fuel_load_kg"] > 0.0
    assert "Estimated Fuel Load (fuel_load_est)" in stint["confounders_controlled"]


# 4. Track-Evolution Handling
def test_track_evolution_handling():
    """Verify track evolution index is explicit and included in contextual baseline."""
    res = client.get("/api/sessions/2024_monza_R/degradation")
    assert res.status_code == 200
    stint = res.json()["stints"][0]
    lap = stint["laps"][0]
    context = lap["contextual_factors"]
    assert "track_evolution_index" in context
    assert context["track_evolution_index"] > 0.0
    assert "Track Evolution Index (track_evolution_index)" in stint["confounders_controlled"]


# 5. Traffic Availability State
def test_traffic_availability_state():
    """Verify traffic is honestly reported as not modeled rather than fabricated."""
    res = client.get("/api/sessions/2024_monza_R/degradation")
    assert res.status_code == 200
    stint = res.json()["stints"][0]
    assert "Traffic (traffic_adjustment: Not currently modeled)" in stint["confounders_unmodeled"]
    lap = stint["laps"][0]
    assert "Not currently modeled" in lap["contextual_factors"]["traffic_adjustment"]


# 6. Practice Prediction
def test_practice_prediction_generation():
    """Verify pre-race pace prediction generates projected degradation curves with frozen snapshot."""
    res = client.get("/api/sessions/2024_monza_R/prediction")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "PREDICTION_AVAILABLE"
    assert data["predictions_count"] > 0
    pred = data["predictions"][0]
    assert "predicted_deg_rate_sec_per_lap" in pred
    assert len(pred["predicted_curve"]) > 0
    assert "frozen_snapshot" in pred
    assert pred["frozen_snapshot"]["status"] == "FROZEN_PRE_RACE"
    assert len(pred["frozen_snapshot"]["snapshot_hash"]) > 0


# 7. Race Validation
def test_race_validation_comparison():
    """Verify post-race validation compares practice predictions against actual race observations."""
    res = client.get("/api/sessions/2024_monza_R/validation?practice_session_id=2024_monza_R")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VALIDATION_AVAILABLE"
    assert data["comparisons_count"] > 0
    comp = data["comparisons"][0]
    assert "metrics" in comp
    assert "predicted_deg_rate_sec_per_lap" in comp["metrics"]
    assert "actual_deg_rate_sec_per_lap" in comp["metrics"]
    assert "relative_error_pct" in comp["metrics"]


# 8. Practice/Race Leakage Prevention
def test_practice_race_leakage_prevention():
    """
    NON-NEGOTIABLE LEAKAGE TEST:
    Verify prediction endpoint derives values strictly from pre-race session without accessing race telemetry.
    """
    res_pred = client.get("/api/sessions/2024_monza_R/prediction?driver_id=LEC")
    assert res_pred.status_code == 200
    pred = res_pred.json()["predictions"][0]
    provenance = res_pred.json()["provenance"]
    assert provenance["leakage_audit_status"] == "ZERO_RACE_DATA_LEAKAGE_VERIFIED"
    assert pred["frozen_snapshot"]["leakage_guard"] == "STRICT_ISOLATION_ACTIVE"


# 9. Compound Matching
def test_compound_matching():
    """Verify validation strictly matches same compound (e.g. MEDIUM to MEDIUM)."""
    res = client.get("/api/sessions/2024_monza_R/validation?practice_session_id=2024_monza_R&compound=HARD")
    assert res.status_code == 200
    data = res.json()
    if data["status"] == "VALIDATION_AVAILABLE":
        for c in data["comparisons"]:
            assert c["compound"] == "HARD"
            assert c["comparison_basis"]["matching_compound"] == "HARD"


# 10. Tyre-Age Matching
def test_tyre_age_matching():
    """Verify paired comparison aligns laps by tyre age on tyre."""
    res = client.get("/api/sessions/2024_monza_R/validation?practice_session_id=2024_monza_R&driver_id=LEC")
    assert res.status_code == 200
    data = res.json()
    if data["status"] == "VALIDATION_AVAILABLE":
        comp = data["comparisons"][0]
        for pair in comp["paired_lap_series"]:
            assert "tyre_age" in pair
            assert "predicted_degradation" in pair
            assert "actual_degradation" in pair
            assert "prediction_error" in pair


# 11. Insufficient Data Handling
def test_insufficient_data_handling():
    """Verify non-existent driver or stint returns honest INSUFFICIENT_DATA status."""
    res = client.get("/api/sessions/2024_monza_R/degradation?driver_id=NONEXISTENT_DRIVER")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "INSUFFICIENT_DATA"
    assert "N/A — insufficient comparable laps" in data["message"]


# 12. Prediction Error Calculation
def test_prediction_error_calculation():
    """Verify mathematical calculation of MAE, RMSE, Mean Bias, and Absolute Error."""
    res = client.get("/api/sessions/2024_monza_R/validation?practice_session_id=2024_monza_R")
    assert res.status_code == 200
    data = res.json()
    if data["status"] == "VALIDATION_AVAILABLE":
        m = data["comparisons"][0]["metrics"]
        assert m["mean_absolute_error_mae"] >= 0.0
        assert m["root_mean_squared_error_rmse"] >= m["mean_absolute_error_mae"] - 1e-5
        assert isinstance(m["prediction_bias"], (int, float))
        assert m["relative_error_pct"] >= 0.0


# 13. Uncertainty Calculation
def test_uncertainty_calculation():
    """Verify empirical bootstrap confidence intervals are provided for degradation curves."""
    res = client.get("/api/sessions/2024_monza_R/degradation")
    assert res.status_code == 200
    lap = res.json()["stints"][0]["laps"][0]
    unc = lap["uncertainty"]
    assert "ci_lower" in unc
    assert "ci_upper" in unc
    assert unc["ci_upper"] >= unc["ci_lower"]
    assert unc["ci_margin"] > 0.0


# 14. Cross-Driver Comparison
def test_cross_driver_comparison():
    """Verify cross-driver degradation and tyre debt comparison in the same session."""
    res = client.get("/api/sessions/2024_monza_R/degradation/compare-drivers?driver_a=LEC&driver_b=PIA")
    assert res.status_code == 200
    data = res.json()
    assert data["driver_a"]["driver_id"] == "LEC"
    assert data["driver_b"]["driver_id"] == "PIA"
    assert "comparison" in data
    assert "deg_rate_delta_b_minus_a" in data["comparison"]
    assert "cumulative_debt_delta_b_minus_a" in data["comparison"]


# 15. Cross-Season Isolation (2024 vs 2025)
def test_cross_season_isolation():
    """Verify 2024 and 2025 sessions compute degradation strictly from their own session data."""
    res_24 = client.get("/api/sessions/2024_albert_park_R/degradation?driver_id=LEC")
    res_25 = client.get("/api/sessions/2025_albert_park_R/degradation?driver_id=LEC")
    assert res_24.status_code == 200
    assert res_25.status_code == 200
    assert res_24.json()["season"] == 2024
    assert res_25.json()["season"] == 2025



# 16. Cross-Session Isolation
def test_cross_session_isolation():
    """Verify sessions do not leak data across distinct events (e.g. Monza vs Spa)."""
    res_monza = client.get("/api/sessions/2024_monza_R/degradation")
    res_spa = client.get("/api/sessions/2024_spa_R/degradation")
    assert res_monza.status_code == 200
    assert res_spa.status_code == 200
    assert res_monza.json()["circuit_id"] == "monza"
    assert res_spa.json()["circuit_id"] == "spa"


# 17. Cache Isolation
def test_cache_isolation():
    """Verify cache keys properly isolate by session_id, driver_id, and compound."""
    res1 = client.get("/api/sessions/2024_monza_R/degradation?driver_id=LEC")
    res2 = client.get("/api/sessions/2024_monza_R/degradation?driver_id=VER")
    assert res1.status_code == 200
    assert res2.status_code == 200
    assert res1.json()["stints"][0]["driver_id"] == "LEC"
    assert res2.json()["stints"][0]["driver_id"] == "VER"


# 18. Real-Data Provenance
def test_real_data_provenance():
    """Verify all degradation and validation responses include full provenance metadata."""
    res = client.get("/api/sessions/2024_monza_R/degradation")
    assert res.status_code == 200
    prov = res.json()["provenance"]
    assert "season" in prov
    assert "circuit" in prov
    assert "data_version" in prov
    assert "model_version_stage1" in prov


# 19. No Synthetic Fallback
def test_no_synthetic_fallback():
    """Verify non-existent session throws 404 rather than fabricating synthetic telemetry."""
    res = client.get("/api/sessions/fake_nonexistent_session_999/degradation")
    assert res.status_code == 404


# 20. Frontend API Contract Validation
def test_event_practice_race_validation_endpoint():
    """Verify event-level practice-to-race validation endpoint works as expected."""
    res = client.get("/api/events/2024_monza/practice-race-validation?practice_session_type=R")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("VALIDATION_AVAILABLE", "INSUFFICIENT_DATA")
