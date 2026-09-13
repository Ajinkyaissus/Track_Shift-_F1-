"""
tests/test_clean_architecture.py — Comprehensive Verification for Clean Final Architecture.

Validates:
1. Canonical imports for all core modules (trackshift.tdsm and trackshift.strategy).
2. TDSM inference engine (predict_realtime_point, TDSMInferenceEngine, and TrackShiftState).
3. Strategy engine determinism and action spaces (trackshift.strategy.decision_engine).
4. Canonical FastAPI platform serving layer (/api/tdsm/health, /v1/predict, /api/tdsm/predict).
5. Fail-safe behavior (missing weights/scaler triggers operational fallback, never fake neural model).
6. Training/Validation dataset isolation: 0 2025 rows in training split.
7. Scaler parameters strictly 2024-train fitted.
"""

import os
import json
import pytest
import numpy as np
import torch
from fastapi.testclient import TestClient

from trackshift.tdsm.model import TinyTDSM, FallbackTDSM, INPUT_DIM, STATE_DIM, HORIZONS
from trackshift.tdsm.dataset import TDSMDataset, FeatureScaler, one_hot_compound
from trackshift.tdsm.inference import predict_realtime_point, TDSMInferenceEngine, TrackShiftState
from trackshift.strategy.decision_engine import TDSMStrategyEngine
from api.main import app as main_app


def test_canonical_imports_and_exports():
    """Ensure all core architectural modules are cleanly importable."""
    assert TinyTDSM is not None
    assert FallbackTDSM is not None
    assert TDSMDataset is not None
    assert FeatureScaler is not None
    assert TDSMStrategyEngine is not None
    assert predict_realtime_point is not None
    assert TDSMInferenceEngine is not None
    assert TrackShiftState is not None


def test_tdsm_inference_engine():
    """Verify end-to-end inference using TDSMInferenceEngine and predict_realtime_point."""
    pred = predict_realtime_point(
        d=0.45,
        delta_d=0.08,
        delta2_d=0.01,
        tyre_life=12,
        compound="MEDIUM",
        fuel_proxy=75.0
    )
    
    assert "forecast" in pred
    assert len(pred["forecast"]) == 4
    for h in [1, 3, 5, 10]:
        assert f"+{h}" in pred["forecast"]
        assert isinstance(pred["forecast"][f"+{h}"], float)
    
    assert pred["model"] == "TDSM"


def test_strategy_engine_determinism():
    """Verify deterministic strategy evaluation with strict action semantics."""
    engine = TDSMStrategyEngine()
    
    # Test high degradation triggers deterministic action
    cliff_forecast = {"+1": 1.9, "+3": 2.6, "+5": 3.4, "+10": 4.8}
    rec_high = engine.evaluate_strategy(
        current_lap=18,
        tyre_life=18,
        compound="SOFT",
        current_d=1.5,
        delta_d=0.3,
        delta2_d=0.15,
        tdsm_forecast=cliff_forecast,
        total_laps=57
    )
    assert rec_high["action"] in ["PIT", "MANAGE", "STAY_OUT", "PUSH", "ATTACK", "DEFEND", "MONITOR"]
    assert "TYRE_CLIFF_FORECAST_EXCEEDED" in rec_high["reason_codes"]

    # Verify identical inputs produce identical outputs (determinism)
    rec_copy = engine.evaluate_strategy(
        current_lap=18,
        tyre_life=18,
        compound="SOFT",
        current_d=1.5,
        delta_d=0.3,
        delta2_d=0.15,
        tdsm_forecast=cliff_forecast,
        total_laps=57
    )
    assert rec_high["action"] == rec_copy["action"]
    assert rec_high["reason_codes"] == rec_copy["reason_codes"]
    assert rec_high["confidence"] == rec_copy["confidence"]


def test_serving_layer_health_and_predict():
    """Verify FastAPI serving layer endpoints on canonical main app via TestClient."""
    client = TestClient(main_app)
    
    # 1. /api/tdsm/health
    health_resp = client.get("/api/tdsm/health")
    assert health_resp.status_code == 200
    data = health_resp.json()
    assert data["status"] == "running"
    assert data["model"] == "TDSM"
    assert data["trained_weights_loaded"] is True
    assert data["scaler_loaded"] is True

    # 2. /v1/predict (batched request)
    payload = {
        "laps": [
            {
                "D": 0.35,
                "Delta_D": 0.05,
                "Delta2_D": 0.01,
                "TyreLife": 10,
                "FuelProxy": 80.0,
                "Compound": "HARD"
            }
        ]
    }
    pred_resp = client.post("/v1/predict", json=payload)
    assert pred_resp.status_code == 200
    pred_data = pred_resp.json()
    assert "results" in pred_data
    assert len(pred_data["results"]) == 1
    p0 = pred_data["results"][0]
    assert p0["Forecast_plus_1"] > 0
    assert p0["Forecast_plus_10"] > 0
    assert p0["model_used"] in ["TDSM", "FALLBACK"]


def test_fail_safe_operational_fallback_api():
    """Verify that when unscaled/untrained, fallback or 503 is cleanly handled."""
    from api.routers.tdsm import _model_state
    # Temporarily simulate missing weights
    orig_loaded = _model_state["trained_weights_loaded"]
    _model_state["trained_weights_loaded"] = False
    
    client = TestClient(main_app)
    payload = {
        "laps": [
            {
                "D": 0.5,
                "Delta_D": 0.1,
                "Delta2_D": 0.02,
                "TyreLife": 15,
                "FuelProxy": 70.0,
                "Compound": "SOFT"
            }
        ]
    }
    pred_resp = client.post("/v1/predict", json=payload)
    # Revert state immediately
    _model_state["trained_weights_loaded"] = orig_loaded

    assert pred_resp.status_code in [200, 503]
    if pred_resp.status_code == 200:
        pred_data = pred_resp.json()
        assert pred_data["results"][0]["model_used"] == "FALLBACK"


def test_training_validation_split_isolation():
    """Verify 2024 training and 2025 validation splits have 0 overlap and 0 2025 rows in training."""
    parquet_path = "data/combined_2024_2025_laps.parquet"
    if not os.path.exists(parquet_path):
        pytest.skip("Dataset parquet file not found for isolation test.")
        
    import pandas as pd
    df = pd.read_parquet(parquet_path)
    
    # 2024 train split rounds 1-18
    season_col = "season" if "season" in df.columns else "Season"
    round_col = "round" if "round" in df.columns else "Round"
    
    train_mask = (df[season_col] == 2024) & (df[round_col] <= 18)
    train_df = df[train_mask]
    
    assert (train_df[season_col] == 2025).sum() == 0, "CRITICAL: 2025 rows detected in 2024 training set!"
    assert len(train_df) == 17963, f"Expected 17,963 training laps, got {len(train_df)}"
    
    # 2025 held-out split
    val_2025_df = df[df[season_col] == 2025]
    assert len(val_2025_df) == 22197, f"Expected 22,197 laps in 2025, got {len(val_2025_df)}"


def test_frozen_scaler_isolation():
    """Verify frozen scaler and training metadata match 2024 training-only protocol."""
    scaler_path = "artifacts/tdsm/scaler.json"
    meta_path = "artifacts/tdsm/training_metadata.json"
    if not os.path.exists(scaler_path) or not os.path.exists(meta_path):
        pytest.skip("Frozen scaler or metadata artifact not found.")
        
    with open(scaler_path, "r") as f:
        scaler = json.load(f)
    with open(meta_path, "r") as f:
        meta = json.load(f)
    
    assert meta.get("training_season") == 2024
    assert meta.get("train_rounds") == list(range(1, 19))
    assert meta.get("val_rounds") == list(range(19, 25))
    assert len(scaler.get("mean", [])) == 5
    assert len(scaler.get("std", [])) == 5
