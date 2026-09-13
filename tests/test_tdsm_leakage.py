"""
tests/test_tdsm_leakage.py — Strict Proof of Causal Integrity & Zero Data Leakage.
"""

import numpy as np
import pandas as pd
import pytest
import torch

from trackshift.tdsm.preprocessing import TDSMPreprocessor
from trackshift.tdsm.inference import TDSMInferenceEngine, TrackShiftState


def test_prediction_invariance_to_future_rows():
    """
    CRITICAL LEAKAGE TEST:
    A prediction at lap N MUST NOT depend on lap N+1 or later rows.
    
    Procedure:
    1. Generate state and prediction using data through lap N.
    2. Append future rows (lap N+1 onward).
    3. Generate state and prediction at lap N with full dataset.
    4. Predictions must be 100% identical.
    """
    engine = TDSMInferenceEngine()
    preprocessor = TDSMPreprocessor()

    # Create historical stint of 10 laps
    laps_10 = pd.DataFrame({
        "event_name": ["Bahrain Grand Prix"] * 10,
        "season": [2025] * 10,
        "round": [1] * 10,
        "driver": ["VER"] * 10,
        "stint_num": [1] * 10,
        "LapNumber": list(range(1, 11)),
        "compound": ["MEDIUM"] * 10,
        "tyre_age": list(range(1, 11)),
        "fuel_kg": [100.0 - i * 1.8 for i in range(10)],
        "lap_time_s": [93.0 + 0.1 * i + 0.033 * (100.0 - i * 1.8) for i in range(10)]
    })

    # Cutoff at Lap 6
    laps_through_6 = laps_10.iloc[:6].copy()

    feat_6 = preprocessor.extract_canonical_features(laps_through_6)
    row_6_isolated = feat_6.iloc[-1]
    pred_isolated = engine.predict_state(
        d=row_6_isolated['D'],
        delta_d=row_6_isolated['Delta_D'],
        delta2_d=row_6_isolated['Delta2_D'],
        tyre_life=row_6_isolated['TyreLife'],
        compound_idx=row_6_isolated['CompoundIdx'],
        fuel_proxy=row_6_isolated['FuelProxy'],
        data_cutoff_lap=6
    )

    # Now extract features with all 10 laps present
    feat_10 = preprocessor.extract_canonical_features(laps_10)
    row_6_full = feat_10.iloc[5]
    pred_with_future = engine.predict_state(
        d=row_6_full['D'],
        delta_d=row_6_full['Delta_D'],
        delta2_d=row_6_full['Delta2_D'],
        tyre_life=row_6_full['TyreLife'],
        compound_idx=row_6_full['CompoundIdx'],
        fuel_proxy=row_6_full['FuelProxy'],
        data_cutoff_lap=6
    )

    # Features must match identically
    for col in ['D', 'Delta_D', 'Delta2_D', 'TyreLife', 'CompoundIdx', 'FuelProxy']:
        assert abs(row_6_isolated[col] - row_6_full[col]) < 1e-6, f"Feature {col} leaked future data!"

    # Forecasts must match identically
    for h in ["+1", "+3", "+5", "+10"]:
        assert abs(pred_isolated["forecast"][h] - pred_with_future["forecast"][h]) < 1e-6, f"Forecast {h} leaked future data!"


def test_cross_stint_isolation():
    """Verify Delta_D and Delta2_D never cross stint boundaries."""
    preprocessor = TDSMPreprocessor()

    df = pd.DataFrame({
        "event_name": ["Monza"] * 6,
        "season": [2025] * 6,
        "round": [1] * 6,
        "driver": ["HAM"] * 6,
        "stint_num": [1, 1, 1, 2, 2, 2],
        "LapNumber": [1, 2, 3, 4, 5, 6],
        "compound": ["SOFT", "SOFT", "SOFT", "HARD", "HARD", "HARD"],
        "tyre_age": [1, 2, 3, 1, 2, 3],
        "fuel_kg": [100.0, 98.0, 96.0, 94.0, 92.0, 90.0],
        "lap_time_s": [85.0, 85.5, 86.2, 84.0, 84.3, 84.8]
    })

    featured = preprocessor.extract_canonical_features(df)

    # First lap of stint 2 (index 3, Lap 4) must have Delta_D = 0.0 and Delta2_D = 0.0
    stint2_lap1 = featured.iloc[3]
    assert stint2_lap1['Delta_D'] == 0.0, f"Stint boundary leak: Delta_D is {stint2_lap1['Delta_D']} instead of 0.0"
    assert stint2_lap1['Delta2_D'] == 0.0, f"Stint boundary leak: Delta2_D is {stint2_lap1['Delta2_D']} instead of 0.0"


def test_cross_driver_isolation():
    """Verify features never leak across different drivers."""
    preprocessor = TDSMPreprocessor()

    df = pd.DataFrame({
        "event_name": ["Silverstone"] * 4,
        "season": [2025] * 4,
        "round": [1] * 4,
        "driver": ["VER", "VER", "LEC", "LEC"],
        "stint_num": [1, 1, 1, 1],
        "LapNumber": [1, 2, 1, 2],
        "compound": ["HARD"] * 4,
        "tyre_age": [1, 2, 1, 2],
        "fuel_kg": [100.0, 98.0, 100.0, 98.0],
        "lap_time_s": [90.0, 90.4, 89.0, 89.5]
    })

    featured = preprocessor.extract_canonical_features(df)

    # First lap of LEC (index 2) must not compute delta from VER
    lec_lap1 = featured.iloc[2]
    assert lec_lap1['Delta_D'] == 0.0, f"Cross-driver leak: Delta_D is {lec_lap1['Delta_D']} instead of 0.0"
    assert lec_lap1['Delta2_D'] == 0.0, f"Cross-driver leak: Delta2_D is {lec_lap1['Delta2_D']} instead of 0.0"


def test_trackshift_state_streaming_causality():
    """Verify TrackShiftState records accurate cutoff laps and causality during streaming replay."""
    state = TrackShiftState(driver="NOR", stint=1, event="Spa", session="2025_Race")

    laps_data = [
        (1, 105.0, 1.0, "MEDIUM", 100.0),
        (2, 105.4, 2.0, "MEDIUM", 98.2),
        (3, 105.8, 3.0, "MEDIUM", 96.4),
        (4, 106.5, 4.0, "MEDIUM", 94.6),
    ]

    for lap_num, lap_time, age, comp, fuel in laps_data:
        res = state.update_lap(lap_num, lap_time, age, comp, fuel)
        assert res["data_cutoff_lap"] == lap_num
        assert res["driver"] == "NOR"
        assert "+1" in res["forecast"]
        assert "+3" in res["forecast"]
        assert "+5" in res["forecast"]
        assert "+10" in res["forecast"]

    assert len(state.prediction_history) == 4
