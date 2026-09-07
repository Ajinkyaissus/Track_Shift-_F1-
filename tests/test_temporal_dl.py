"""
Tests for Temporal Deep Learning (TCN / LSTM) Behavioral Embedding model,
deterministic inference, embedding dimensions, attribution, and physical saturation guardrails.
"""

import numpy as np
import pytest
import torch

from api.models import (
    BEHAVIORAL_FEATURES,
    DEFAULT_EMBEDDING_DIM,
    TemporalBehavioralTCN,
    TemporalBehavioralLSTM,
    BehavioralModelWrapper
)


def test_tcn_architecture_shape():
    batch_size = 4
    num_features = len(BEHAVIORAL_FEATURES)
    seq_len = 30

    x = torch.randn(batch_size, num_features, seq_len)
    model = TemporalBehavioralTCN(in_features=num_features, embedding_dim=DEFAULT_EMBEDDING_DIM)
    model.eval()

    with torch.no_grad():
        out = model(x)

    assert out.shape == (batch_size, DEFAULT_EMBEDDING_DIM)
    assert not torch.isnan(out).any()


def test_lstm_architecture_shape():
    batch_size = 2
    num_features = len(BEHAVIORAL_FEATURES)
    seq_len = 25

    x = torch.randn(batch_size, num_features, seq_len)
    model = TemporalBehavioralLSTM(in_features=num_features, embedding_dim=DEFAULT_EMBEDDING_DIM)
    model.eval()

    with torch.no_grad():
        out = model(x)

    assert out.shape == (batch_size, DEFAULT_EMBEDDING_DIM)
    assert not torch.isnan(out).any()


def test_behavioral_embedding_determinism():
    wrapper = BehavioralModelWrapper(architecture="tcn")
    rng = np.random.RandomState(42)
    seq = rng.randn(len(BEHAVIORAL_FEATURES), 20)

    emb1 = wrapper.generate_embedding(seq)
    emb2 = wrapper.generate_embedding(seq)

    assert emb1.shape == (DEFAULT_EMBEDDING_DIM,)
    assert emb2.shape == (DEFAULT_EMBEDDING_DIM,)
    np.testing.assert_allclose(emb1, emb2, rtol=1e-5, atol=1e-5)


def test_physical_saturation_guardrail():
    wrapper = BehavioralModelWrapper()

    # Case 1: Moderate recovery (should be near-linear)
    mod_res = wrapper.compute_counterfactual_recovery(
        linear_loss_recovery=0.20,
        stint_length=20,
        deg_per_lap=0.10
    )
    assert 1.5 <= mod_res["recovered_laps"] <= 2.1
    assert mod_res["is_saturated"] is False

    # Case 2: Extreme positive recovery (e.g. 50 seconds theoretical) -> MUST saturate at max_physical_bound
    max_bound = min(0.35 * 20, 7.5)  # 7.0 laps
    extreme_pos = wrapper.compute_counterfactual_recovery(
        linear_loss_recovery=50.0,
        stint_length=20,
        deg_per_lap=0.10
    )
    assert extreme_pos["recovered_laps"] <= max_bound
    assert extreme_pos["recovered_laps"] > 6.5
    assert extreme_pos["is_saturated"] is True

    # Case 3: Extreme negative recovery (-50 seconds) -> MUST saturate at -max_physical_bound
    extreme_neg = wrapper.compute_counterfactual_recovery(
        linear_loss_recovery=-50.0,
        stint_length=20,
        deg_per_lap=0.10
    )
    assert extreme_neg["recovered_laps"] >= -max_bound
    assert extreme_neg["recovered_laps"] < -6.5
    assert extreme_neg["is_saturated"] is True
