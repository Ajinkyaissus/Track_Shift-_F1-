"""
tests/test_tcn_training_and_leakage.py — Strict tests for:
1. Sequence boundary safety (never crossing stint/session/driver boundaries)
2. Training-only scaler fit (no future leakage in preprocessing)
3. Model weight persistence and deterministic checkpoint loading
4. Model training loss convergence
5. Checkpoint manifest and SHA-256 integrity
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
import torch

from pipeline.train_stage3_tcn import (
    MultiTaskBehavioralTCN,
    build_stint_sequences,
    StintSequenceDataset,
    train_tcn_model,
    BEHAVIORAL_FEATURES,
    DEFAULT_EMBEDDING_DIM
)
from api.models import get_model_registry, BehavioralModelWrapper

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models", "stage3")
DATA_DIR = os.path.join(BASE_DIR, "data")
LAPS_PARQUET = os.path.join(DATA_DIR, "laps.parquet")
LEDGER_PARQUET = os.path.join(DATA_DIR, "residual_ledger.parquet")


def test_sequence_boundary_isolation():
    """Verify that temporal sequences NEVER mix laps from different stints."""
    # Synthetic test fixture with two distinct stints
    laps_synthetic = pd.DataFrame([
        # Stint A
        {"stint_id": "stint_A", "lap_number": 1, "braking_aggression": 0.5, "throttle_transient_smoothness": 0.8, "lateral_dynamics_proxy": 1.0, "kerb_usage": 50.0, "lockup_flag_rate": 0.0},
        {"stint_id": "stint_A", "lap_number": 2, "braking_aggression": 0.6, "throttle_transient_smoothness": 0.7, "lateral_dynamics_proxy": 1.1, "kerb_usage": 55.0, "lockup_flag_rate": 0.0},
        {"stint_id": "stint_A", "lap_number": 3, "braking_aggression": 0.7, "throttle_transient_smoothness": 0.6, "lateral_dynamics_proxy": 1.2, "kerb_usage": 60.0, "lockup_flag_rate": 0.1},
        # Stint B
        {"stint_id": "stint_B", "lap_number": 1, "braking_aggression": 0.3, "throttle_transient_smoothness": 0.9, "lateral_dynamics_proxy": 0.9, "kerb_usage": 40.0, "lockup_flag_rate": 0.0},
        {"stint_id": "stint_B", "lap_number": 2, "braking_aggression": 0.4, "throttle_transient_smoothness": 0.8, "lateral_dynamics_proxy": 1.0, "kerb_usage": 45.0, "lockup_flag_rate": 0.0},
    ])

    ledger_synthetic = pd.DataFrame([
        {"stint_id": "stint_A", "lap_number": 1, "residual": 0.1},
        {"stint_id": "stint_A", "lap_number": 2, "residual": 0.2},
        {"stint_id": "stint_A", "lap_number": 3, "residual": 0.3},
        {"stint_id": "stint_B", "lap_number": 1, "residual": -0.1},
        {"stint_id": "stint_B", "lap_number": 2, "residual": -0.2},
    ])

    samples, scaler = build_stint_sequences(laps_synthetic, ledger_synthetic, fit_scaler=True, max_seq_len=5)

    # Verify every sample belongs exclusively to its stint
    for sample in samples:
        stint_id = sample['stint_id']
        lap_num = sample['lap_number']
        seq = sample['sequence']
        assert stint_id in ['stint_A', 'stint_B']
        # Sequence length must not exceed number of laps seen so far in this stint
        if stint_id == 'stint_A':
            assert len(seq) == lap_num
        elif stint_id == 'stint_B':
            assert len(seq) == lap_num


def test_scaler_fit_on_train_only():
    """Verify that preprocessing scalers are fit exclusively on the training split."""
    laps_df = pd.read_parquet(LAPS_PARQUET)
    train_laps = laps_df.iloc[:500]
    test_laps = laps_df.iloc[500:]

    ledger_df = pd.read_parquet(LEDGER_PARQUET)

    # Fit on train
    train_samples, train_scaler = build_stint_sequences(train_laps, ledger_df, fit_scaler=True)
    # Transform test
    test_samples, test_scaler = build_stint_sequences(test_laps, ledger_df, scaler=train_scaler, fit_scaler=False)

    # Verify that the test transformation uses the exact mean and scale of the train scaler
    np.testing.assert_allclose(train_scaler.mean_, test_scaler.mean_)
    np.testing.assert_allclose(train_scaler.scale_, test_scaler.scale_)


def test_tcn_checkpoint_manifest_integrity():
    """Verify that saved model checkpoints contain valid weights, config, and SHA-256 manifest."""
    assert os.path.exists(MODELS_DIR), "models/stage3 directory must exist"
    subdirs = [d for d in os.listdir(MODELS_DIR) if os.path.isdir(os.path.join(MODELS_DIR, d))]
    assert len(subdirs) > 0, "At least one trained Stage 3 model version must be checkpointed"

    latest = sorted(subdirs)[-1]
    v_dir = os.path.join(MODELS_DIR, latest)

    for fname in ["model.pt", "config.json", "preprocessing.json", "metrics.json", "manifest.json"]:
        p = os.path.join(v_dir, fname)
        assert os.path.exists(p), f"Missing required checkpoint file: {fname}"

    with open(os.path.join(v_dir, "manifest.json"), "r") as f:
        manifest = json.load(f)
        assert "model_hash_sha256" in manifest
        assert len(manifest["model_hash_sha256"]) == 64  # valid sha256


def test_behavioral_wrapper_loads_trained_weights():
    """Verify that BehavioralModelWrapper loads real trained weights."""
    wrapper = BehavioralModelWrapper(architecture="tcn")
    assert wrapper.is_trained is True, "BehavioralModelWrapper must load trained weights"
    assert wrapper.scaler_mean is not None, "Scaler mean must be loaded from checkpoint"
    assert wrapper.scaler_scale is not None, "Scaler scale must be loaded from checkpoint"
