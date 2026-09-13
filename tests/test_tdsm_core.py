"""
tests/test_tdsm_core.py — Unit Tests for Primary State-Transition TinyTDSM & Operational Fallback.
"""

import os
import torch
import numpy as np
import pandas as pd
import pytest

from trackshift.tdsm.model import TinyTDSM, FallbackTDSM, MaskedMultiHorizonLoss, INPUT_DIM, STATE_DIM
from trackshift.tdsm.dataset import TDSMDataset, FeatureScaler, one_hot_compound


def test_primary_tdsm_architecture_shapes():
    """Verify Primary State-Transition TinyTDSM network structure and forward pass shapes."""
    model = TinyTDSM(input_dim=INPUT_DIM, state_dim=STATE_DIM)
    model.eval()

    # Batch of 8 samples, 11 features
    x = torch.randn(8, INPUT_DIM)
    raw_d = torch.randn(8)

    with torch.no_grad():
        next_state, delta_state, forecast_delta = model(x)
        forecast_debt = model.predict_forecast_debt(x, raw_d)

    assert next_state.shape == (8, 3), f"Expected next_state shape (8, 3), got {next_state.shape}"
    assert delta_state.shape == (8, 3), f"Expected delta_state shape (8, 3), got {delta_state.shape}"
    assert forecast_delta.shape == (8, 4), f"Expected forecast_delta shape (8, 4), got {forecast_delta.shape}"
    assert forecast_debt.shape == (8, 4), f"Expected forecast_debt shape (8, 4), got {forecast_debt.shape}"

    # Verify residual addition: forecast_debt = raw_d + forecast_delta
    expected = raw_d.unsqueeze(1) + forecast_delta
    assert torch.allclose(forecast_debt, expected, atol=1e-6)


def test_fallback_tdsm_architecture_shapes():
    """Verify Operational Fallback TDSM model (6 inputs -> 4 outputs)."""
    fb = FallbackTDSM(input_dim=6)
    fb.eval()
    x = torch.randn(4, 6)
    with torch.no_grad():
        out = fb(x)
    assert out.shape == (4, 4)


def test_tdsm_dataset_no_fabricated_targets():
    """Verify missing future horizons are masked as 0, never repeated."""
    # Stint with 4 laps
    df = pd.DataFrame({
        "driver": ["VER"] * 4,
        "stint_num": [1] * 4,
        "LapNumber": [1, 2, 3, 4],
        "compound": ["MEDIUM"] * 4,
        "D": [0.1, 0.3, 0.6, 1.2],
        "Delta_D": [0.1, 0.2, 0.3, 0.6],
        "Delta2_D": [0.0, 0.1, 0.1, 0.3],
        "TyreLife": [1, 2, 3, 4],
        "FuelProxy": [100.0, 98.2, 96.4, 94.6]
    })

    dataset = TDSMDataset(df, horizons=(1, 3, 5, 10))
    assert len(dataset) == 4

    # Lap 0 (Lap 1):
    # +1 -> lap 1 (D=0.3), +3 -> lap 3 (D=1.2), +5 -> masked, +10 -> masked
    x0, y0, m0, d0 = dataset[0]
    assert m0[0].item() == 1.0
    assert abs(y0[0].item() - 0.3) < 1e-4
    assert m0[1].item() == 1.0
    assert abs(y0[1].item() - 1.2) < 1e-4
    assert m0[2].item() == 0.0
    assert m0[3].item() == 0.0

    # Lap 3 (final lap): all future horizons must be masked
    x3, y3, m3, d3 = dataset[3]
    assert torch.all(m3 == 0.0)


def test_masked_loss_ignores_masked_targets():
    """Verify masked loss ignores missing horizons and produces valid finite gradients."""
    criterion = MaskedMultiHorizonLoss()
    preds = torch.tensor([[1.0, 2.0, 3.0, 4.0]], requires_grad=True)
    targets = torch.tensor([[1.2, 999.0, 999.0, 999.0]])
    mask = torch.tensor([[1.0, 0.0, 0.0, 0.0]])

    loss = criterion(preds, targets, mask)
    # Loss should strictly be (1.0 - 1.2)^2 = 0.04
    assert abs(loss.item() - 0.04) < 1e-5

    loss.backward()
    assert preds.grad is not None
    assert abs(preds.grad[0, 0].item() - (-0.4)) < 1e-4
    assert preds.grad[0, 1].item() == 0.0
    assert preds.grad[0, 2].item() == 0.0
    assert preds.grad[0, 3].item() == 0.0


def test_model_save_and_load(tmp_path):
    """Verify model state dictionary round-trip fidelity."""
    model = TinyTDSM(input_dim=INPUT_DIM)
    x = torch.randn(2, INPUT_DIM)
    raw_d = torch.tensor([0.5, 1.2])
    pred_orig = model.predict_forecast_debt(x, raw_d)

    save_file = str(tmp_path / "test_tdsm.pth")
    torch.save(model.state_dict(), save_file)

    loaded_model = TinyTDSM(input_dim=INPUT_DIM)
    loaded_model.load_state_dict(torch.load(save_file))
    loaded_model.eval()
    pred_loaded = loaded_model.predict_forecast_debt(x, raw_d)

    assert torch.allclose(pred_orig, pred_loaded, atol=1e-6)
