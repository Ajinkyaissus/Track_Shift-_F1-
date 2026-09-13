"""
tests/test_tdsm_strategy_and_api.py — Strategy Decision Layer and API Integration Tests.
"""

import pytest
from fastapi.testclient import TestClient

from trackshift.strategy.decision_engine import TDSMStrategyEngine
from api.main import app


def test_strategy_engine_decisions():
    """Verify deterministic strategy engine outputs transparent recommendations without hard-coded laps."""
    engine = TDSMStrategyEngine(default_pit_loss_sec=22.0, cliff_deg_threshold_sec=2.2)

    # Scenario 1: Imminent tyre cliff at Lap 18 of 57
    cliff_forecast = {"+1": 1.9, "+3": 2.6, "+5": 3.4, "+10": 4.8}
    rec_cliff = engine.evaluate_strategy(
        current_lap=18,
        tyre_life=18,
        compound="SOFT",
        current_d=1.5,
        delta_d=0.3,
        delta2_d=0.15,
        tdsm_forecast=cliff_forecast,
        total_laps=57
    )
    assert rec_cliff["action"] == "PIT"
    assert "TYRE_CLIFF_FORECAST_EXCEEDED" in rec_cliff["reason_codes"]
    assert rec_cliff["target_lap"] in [19, 20]
    assert rec_cliff["confidence"] >= 0.85

    # Scenario 2: Fresh tyres / Low degradation at Lap 5 of 57
    stable_forecast = {"+1": 0.2, "+3": 0.35, "+5": 0.5, "+10": 0.9}
    rec_fresh = engine.evaluate_strategy(
        current_lap=5,
        tyre_life=5,
        compound="HARD",
        current_d=0.15,
        delta_d=0.02,
        delta2_d=0.0,
        tdsm_forecast=stable_forecast,
        total_laps=57
    )
    assert rec_fresh["action"] == "PUSH"
    assert "LOW_DEGRADATION_PUSH_WINDOW" in rec_fresh["reason_codes"]

    # Scenario 3: End of race (lap 55 of 57) - never pit with 2 laps remaining
    rec_end = engine.evaluate_strategy(
        current_lap=55,
        tyre_life=25,
        compound="MEDIUM",
        current_d=2.0,
        delta_d=0.1,
        delta2_d=0.0,
        tdsm_forecast={"+1": 2.2, "+3": 2.6, "+5": 3.0, "+10": 4.0},
        total_laps=57
    )
    assert rec_end["action"] == "STAY_OUT"
    assert "END_OF_RACE_STAY_OUT" in rec_end["reason_codes"]


def test_fastapi_tdsm_endpoints():
    """Verify FastAPI /api/tdsm/ endpoints."""
    client = TestClient(app)

    # 1. Health check
    res_health = client.get("/api/tdsm/health")
    assert res_health.status_code == 200
    data_h = res_health.json()
    assert data_h["model"] == "TDSM"
    assert data_h["status"] == "running"
    assert data_h["horizons"] == [1, 3, 5, 10]

    # 2. Metadata check
    res_meta = client.get("/api/tdsm/metadata")
    assert res_meta.status_code == 200
    data_m = res_meta.json()
    assert data_m["input_features"] == ["D", "Delta_D", "Delta2_D", "TyreLife", "CompoundIdx", "FuelProxy"]
    assert data_m["training_year"] == 2024
    assert data_m["validation_year"] == 2025

    # 3. Prediction endpoint
    payload = {
        "D": 0.5,
        "Delta_D": 0.1,
        "Delta2_D": 0.0,
        "TyreLife": 12.0,
        "CompoundIdx": 1,
        "FuelProxy": 85.0,
        "data_cutoff_lap": 24
    }
    res_pred = client.post("/api/tdsm/predict", json=payload)
    assert res_pred.status_code == 200
    data_p = res_pred.json()
    assert data_p["model"] == "TDSM"
    assert data_p["data_cutoff_lap"] == 24
    assert "+1" in data_p["forecast"]
    assert "+3" in data_p["forecast"]
    assert "+5" in data_p["forecast"]
    assert "+10" in data_p["forecast"]


def test_hardened_tdsm_api():
    """Verify FastAPI app with batched LapState prediction."""
    client = TestClient(app)

    # Health check
    h_res = client.get("/api/tdsm/health")
    assert h_res.status_code == 200
    h_data = h_res.json()
    assert h_data["status"] == "running"
    assert h_data["trained_weights_loaded"] is True

    # Batched prediction
    payload = {
        "laps": [
            {
                "D": 0.5,
                "Delta_D": 0.1,
                "Delta2_D": 0.0,
                "TyreLife": 12.0,
                "Compound": "MEDIUM",
                "FuelProxy": 85.0,
                "data_cutoff_lap": 24
            },
            {
                "D": 1.2,
                "Delta_D": 0.25,
                "Delta2_D": 0.05,
                "TyreLife": 18.0,
                "Compound": "HARD",
                "FuelProxy": 72.0,
                "data_cutoff_lap": 30
            }
        ]
    }
    pred_res = client.post("/v1/predict", json=payload)
    assert pred_res.status_code == 200
    res_data = pred_res.json()
    assert len(res_data["results"]) == 2
    assert res_data["results"][0]["model_used"] == "TDSM"
    assert res_data["results"][0]["data_cutoff_lap"] == 24
    assert res_data["results"][1]["data_cutoff_lap"] == 30

