"""
trackshift/tdsm/inference.py — Stateful & Streaming Inference Engine for TDSM.
"""

import os
import time
import json
import torch
import numpy as np
from typing import Dict, Any, List, Optional

from trackshift.tdsm.dataset import COMPOUNDS, COMPOUND_MAP, one_hot_compound
from trackshift.tdsm.model import TinyTDSM, INPUT_DIM, STATE_DIM
from trackshift.domain_constants import FUEL_EFFECT_COEFFICIENT


class TDSMInferenceEngine:
    """
    Production Inference Engine for Frozen TDSM Model.
    Supports both 11-dim State-Transition TDSM and 6-dim Direct Regressor.
    """
    def __init__(self, weights_path: Optional[str] = None, model_version: str = "TDSM-v2.0-StateTransition-2024-FROZEN"):
        self.model_version = model_version
        self.compound_map = COMPOUND_MAP
        self.horizons = [1, 3, 5, 10]
        self.scaler_mean = None
        self.scaler_std = None

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        if weights_path is None:
            candidate = os.path.join(base_dir, "artifacts", "tdsm", "tdsm_model_2024.pth")
            if os.path.exists(candidate):
                weights_path = candidate

        # Load scaler if available
        scaler_path = os.path.join(base_dir, "artifacts", "tdsm", "scaler.json")
        if os.path.exists(scaler_path):
            try:
                with open(scaler_path, "r") as f:
                    sc = json.load(f)
                self.scaler_mean = np.array(sc["mean"], dtype=np.float32)
                self.scaler_std = np.array(sc["std"], dtype=np.float32)
            except Exception:
                pass

        self.model_loaded = False
        in_dim = INPUT_DIM
        if weights_path and os.path.exists(weights_path):
            try:
                state = torch.load(weights_path, map_location=torch.device('cpu'))
                # Inspect input dimension from first layer
                if "encoder.0.weight" in state:
                    in_dim = state["encoder.0.weight"].shape[1]
                elif "net.0.weight" in state:
                    in_dim = state["net.0.weight"].shape[1]
                self.input_dim = in_dim
                self.model = TinyTDSM(input_dim=self.input_dim)
                self.model.load_state_dict(state)
                self.model_loaded = True
            except Exception:
                self.input_dim = INPUT_DIM
                self.model = TinyTDSM(input_dim=self.input_dim)
        else:
            self.input_dim = INPUT_DIM
            self.model = TinyTDSM(input_dim=self.input_dim)

        self.model.eval()

    def predict_state(
        self,
        d: float,
        delta_d: float,
        delta2_d: float,
        tyre_life: float,
        compound_idx: int,
        fuel_proxy: float,
        data_cutoff_lap: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Executes single-lap inference with provenance tracking.
        """
        if self.input_dim == 11:
            # State-Transition input: [scaled continuous (5), one-hot compound (6)]
            cont = np.array([d, delta_d, delta2_d, tyre_life, fuel_proxy], dtype=np.float32)
            if self.scaler_mean is not None and self.scaler_std is not None:
                cont = (cont - self.scaler_mean) / self.scaler_std

            # One-hot compound
            comp_str = COMPOUNDS[compound_idx] if 0 <= compound_idx < len(COMPOUNDS) else "UNKNOWN"
            comp_oh = one_hot_compound(comp_str)

            x = np.concatenate([cont, comp_oh], axis=0).astype(np.float32)
            inp = torch.tensor([x], dtype=torch.float32)
            raw_d = torch.tensor([[d]], dtype=torch.float32)

            with torch.no_grad():
                preds = self.model.predict_forecast_debt(inp, raw_d).squeeze(0).cpu().numpy().tolist()
        else:
            # 6-input model
            feats = [float(d), float(delta_d), float(delta2_d), float(tyre_life), int(compound_idx), float(fuel_proxy)]
            inp = torch.tensor([feats], dtype=torch.float32)
            with torch.no_grad():
                preds = self.model(inp).squeeze(0).cpu().numpy().tolist()

        return {
            "model": "TDSM",
            "model_version": self.model_version,
            "data_cutoff_lap": data_cutoff_lap,
            "prediction_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "forecast": {
                "+1": round(float(preds[0]), 4),
                "+3": round(float(preds[1]), 4),
                "+5": round(float(preds[2]), 4),
                "+10": round(float(preds[3]), 4)
            }
        }


class TrackShiftState:
    """
    Live Telemetry & Historical Replay Stateful Tracker.
    Accumulates telemetry lap-by-lap without forward looking data.
    """
    def __init__(
        self,
        driver: str,
        stint: int = 1,
        event: str = "Unknown",
        session: str = "2025_Race",
        inference_engine: Optional[TDSMInferenceEngine] = None
    ):
        self.driver = driver
        self.stint = stint
        self.event = event
        self.session = session
        self.engine = inference_engine or TDSMInferenceEngine()

        self.current_lap = 0
        self.tyre_life = 0
        self.compound = "UNKNOWN"
        self.compound_idx = 5
        self.fuel_proxy = 100.0

        self.fuel_corrected_history = []
        self.d_history = []
        self.delta_d_history = []
        self.delta2_d_history = []
        self.running_base_pace = None

        self.latest_forecasts = {}
        self.prediction_history = []

    def update_lap(
        self,
        lap_number: int,
        lap_time_s: float,
        tyre_life: float,
        compound: str,
        fuel_kg: float
    ) -> Dict[str, Any]:
        """
        Ingests newly completed lap, calculates features causally, and generates TDSM forecast.
        """
        self.current_lap = lap_number
        self.tyre_life = tyre_life
        self.compound = str(compound).upper()
        self.compound_idx = self.engine.compound_map.get(self.compound, 5)
        self.fuel_proxy = float(fuel_kg)

        # Canonical fuel-corrected lap time
        fc_time = lap_time_s - FUEL_EFFECT_COEFFICIENT * self.fuel_proxy
        self.fuel_corrected_history.append(fc_time)

        # Causal base pace: running minimum of first 3 laps in stint
        if len(self.fuel_corrected_history) <= 3:
            self.running_base_pace = min(self.fuel_corrected_history)
        elif self.running_base_pace is None:
            self.running_base_pace = fc_time

        d = max(0.0, fc_time - self.running_base_pace)
        self.d_history.append(d)

        # First derivative Delta_D
        if len(self.d_history) >= 2:
            delta_d = d - self.d_history[-2]
        else:
            delta_d = 0.0
        self.delta_d_history.append(delta_d)

        # Second derivative Delta2_D
        if len(self.delta_d_history) >= 2:
            delta2_d = delta_d - self.delta_d_history[-2]
        else:
            delta2_d = 0.0
        self.delta2_d_history.append(delta2_d)

        # Generate forecast with explicit data_cutoff_lap
        pred = self.engine.predict_state(
            d=d,
            delta_d=delta_d,
            delta2_d=delta2_d,
            tyre_life=self.tyre_life,
            compound_idx=self.compound_idx,
            fuel_proxy=self.fuel_proxy,
            data_cutoff_lap=self.current_lap
        )
        self.latest_forecasts = pred["forecast"]
        self.prediction_history.append(pred)

        return {
            "driver": self.driver,
            "stint": self.stint,
            "lap": self.current_lap,
            "compound": self.compound,
            "tyre_life": self.tyre_life,
            "D": round(d, 4),
            "Delta_D": round(delta_d, 4),
            "Delta2_D": round(delta2_d, 4),
            "FuelProxy": round(self.fuel_proxy, 2),
            "data_cutoff_lap": self.current_lap,
            "forecast": self.latest_forecasts
        }


def predict_realtime_point(
    d: float,
    delta_d: float,
    delta2_d: float,
    tyre_life: float,
    compound: str,
    fuel_proxy: float,
    weights_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Canonical functional inference wrapper for a single telemetry point.
    """
    engine = TDSMInferenceEngine(weights_path=weights_path)
    c_idx = engine.compound_map.get(str(compound).upper(), 5)
    return engine.predict_state(
        d=d,
        delta_d=delta_d,
        delta2_d=delta2_d,
        tyre_life=tyre_life,
        compound_idx=c_idx,
        fuel_proxy=fuel_proxy
    )

