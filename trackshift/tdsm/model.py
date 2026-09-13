"""
trackshift/tdsm/model.py — Primary State-Transition TinyTDSM Architecture & Operational Fallback Model.
Canonical neural model definitions for TrackShift TDSM.

TDSM model: a learned STATE-TRANSITION model:
    S_t        = [D_t, Delta_D_t, Delta2_D_t]
    Delta_S_t  = F_theta(S_t, X_t)
    S_{t+1}    = S_t + Delta_S_t

Multi-horizon debt change predictions:
    D_{t+h} = D_t + Forecast_Delta_h
"""

import os
import sys
import json
import torch
import torch.nn as nn
from typing import Tuple, Optional

from trackshift.tdsm.dataset import (
    COMPOUNDS,
    COMPOUND_MAP,
    one_hot_compound,
    TDSMDataset,
    FeatureScaler
)

STATE_DIM = 3            # D, Delta_D, Delta2_D
CONTEXT_DIM = 2 + 6      # TyreLife, FuelProxy, one-hot compound(6)
INPUT_DIM = STATE_DIM + CONTEXT_DIM
HORIZONS = (1, 3, 5, 10)


class TinyTDSM(nn.Module):
    """
    PRIMARY TDSM: Learned State-Transition Model with Multi-Horizon Debt Change Head.
    
    Inputs (11):
      S_t (3): [D, Delta_D, Delta2_D] (scaled)
      Context (8): [TyreLife, FuelProxy] (scaled) + Compound_OneHot (6)
      
    Outputs:
      next_state: S_{t+1} in scaled space
      delta_state: Delta_S_t
      forecast_delta: Predicted CHANGE in raw debt for +1, +3, +5, +10
    """
    def __init__(self, input_dim: int = INPUT_DIM, state_dim: int = STATE_DIM):
        super().__init__()
        self.state_dim = state_dim
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
        )
        self.transition_head = nn.Linear(16, state_dim)        # Delta_S_t = F_theta(S_t, X_t)
        self.forecast_delta_head = nn.Linear(16, len(HORIZONS))  # multi-horizon debt CHANGE

    def forward(self, x: torch.Tensor):
        """
        x: (batch, INPUT_DIM) = concat([S_t(3), TyreLife, FuelProxy, compound_onehot(6)])
        Returns:
            next_state    : (batch, 3) -> S_{t+1} = S_t + Delta_S_t   (SCALED space)
            delta_state   : (batch, 3) -> Delta_S_t alone
            forecast_delta: (batch, 4) -> predicted CHANGE in raw debt per horizon
        """
        state = x[:, : self.state_dim]
        hidden = self.encoder(x)

        delta_state = self.transition_head(hidden)
        next_state = state + delta_state  # S_{t+1} = S_t + F_theta(S_t, X_t)

        forecast_delta = self.forecast_delta_head(hidden)
        return next_state, delta_state, forecast_delta

    def predict_forecast_debt(self, x: torch.Tensor, raw_d: torch.Tensor) -> torch.Tensor:
        """Absolute debt forecasts = current (unscaled) debt + predicted change."""
        _, _, forecast_delta = self.forward(x)
        if raw_d.dim() == 1:
            raw_d = raw_d.unsqueeze(1)
        return raw_d + forecast_delta


class FallbackTDSM(nn.Module):
    """
    OPERATIONAL FALLBACK MODEL ONLY:
    Original 6-input linear direct regressor.
    MUST NEVER participate in model selection or improve the 2025 TDSM score.
    Used only if Primary TDSM weights fail to load or unrecoverable anomaly occurs.
    """
    def __init__(self, input_dim: int = 6):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU()
        )
        self.forecast_head = nn.Linear(16, 4)

    def forward(self, x: torch.Tensor):
        state_rep = self.net(x)
        forecasts = self.forecast_head(state_rep)
        return forecasts


class MaskedMultiHorizonLoss(nn.Module):
    """
    Masked MSE ignoring any (row, horizon) pair where mask == 0.
    """
    def __init__(self, alpha: float = 1.0):
        super().__init__()
        self.alpha = alpha

    def forward(self, pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        sq_err = (pred - target) ** 2 * mask
        denom = mask.sum().clamp(min=1.0)
        return sq_err.sum() / denom
