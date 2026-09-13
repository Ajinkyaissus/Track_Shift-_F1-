"""
api/routers/tdsm.py — Official Production TDSM FastAPI Router with Hardened Serving & Batched Prediction.
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Union
import numpy as np
import torch
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from trackshift.tdsm.dataset import COMPOUNDS, COMPOUND_MAP, one_hot_compound
from trackshift.tdsm.model import TinyTDSM, FallbackTDSM, INPUT_DIM

logger = logging.getLogger("trackshift.api.tdsm")
router = APIRouter(prefix="/api/tdsm", tags=["TDSM"])
v1_router = APIRouter(tags=["TDSM V1"])

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WEIGHTS_PATH = os.path.join(BASE_DIR, "artifacts", "tdsm", "tdsm_model_2024.pth")
SCALER_PATH = os.path.join(BASE_DIR, "artifacts", "tdsm", "scaler.json")
FALLBACK_WEIGHTS_PATH = os.path.join(BASE_DIR, "artifacts", "tdsm", "fallback_model_2024.pth")
MAX_BATCH_SIZE = 64

_model_state = {
    "model": None,
    "fallback_model": None,
    "scaler_mean": None,
    "scaler_std": None,
    "trained_weights_loaded": False,
    "fallback_weights_loaded": False,
    "model_version": "TDSM-v2.0-StateTransition-2024-FROZEN"
}


def load_tdsm_serving():
    model = TinyTDSM(input_dim=INPUT_DIM)
    if os.path.exists(WEIGHTS_PATH):
        try:
            model.load_state_dict(torch.load(WEIGHTS_PATH, map_location="cpu"))
            model.eval()
            _model_state["trained_weights_loaded"] = True
            logger.info("Loaded trained Primary TDSM from %s", WEIGHTS_PATH)
        except Exception as e:
            logger.warning("Could not load TDSM weights: %s", e)
            _model_state["trained_weights_loaded"] = False
    _model_state["model"] = model

    fb_model = FallbackTDSM(input_dim=6)
    if os.path.exists(FALLBACK_WEIGHTS_PATH):
        try:
            fb_model.load_state_dict(torch.load(FALLBACK_WEIGHTS_PATH, map_location="cpu"))
            fb_model.eval()
            _model_state["fallback_weights_loaded"] = True
        except Exception:
            _model_state["fallback_weights_loaded"] = False
    _model_state["fallback_model"] = fb_model

    if os.path.exists(SCALER_PATH):
        try:
            with open(SCALER_PATH) as f:
                sc = json.load(f)
            _model_state["scaler_mean"] = np.array(sc["mean"], dtype=np.float32)
            _model_state["scaler_std"] = np.array(sc["std"], dtype=np.float32)
        except Exception as e:
            logger.warning("Failed loading scaler: %s", e)


# Eager load
load_tdsm_serving()


class LapState(BaseModel):
    D: float = Field(..., description="Current tyre degradation in seconds")
    Delta_D: float = Field(..., description="First derivative of degradation")
    Delta2_D: float = Field(..., description="Second derivative of degradation")
    TyreLife: float = Field(..., ge=0, description="Tyre life in laps")
    Compound: Optional[str] = Field("MEDIUM", description="Tyre compound: SOFT, MEDIUM, HARD, INTERMEDIATE, WET, UNKNOWN")
    CompoundIdx: Optional[int] = Field(None, description="Integer encoded compound (0..5)")
    FuelProxy: float = Field(..., description="Estimated fuel on board in kg")
    data_cutoff_lap: Optional[int] = Field(None, description="Current lap cutoff for causal provenance")


class BatchedPredictRequest(BaseModel):
    laps: List[LapState] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE)


class ForecastItem(BaseModel):
    Forecast_plus_1: float
    Forecast_plus_3: float
    Forecast_plus_5: float
    Forecast_plus_10: float
    model_used: str = "TDSM"
    fallback_reason: Optional[str] = None
    data_cutoff_lap: Optional[int] = None


class BatchedPredictResponse(BaseModel):
    results: List[ForecastItem]


class SinglePredictResponse(BaseModel):
    model: str
    model_version: str
    model_used: str = "TDSM"
    fallback_reason: Optional[str] = None
    data_cutoff_lap: Optional[int] = None
    forecast: Dict[str, float]


def _predict_laps(laps: List[LapState]) -> List[ForecastItem]:
    model = _model_state["model"]
    fallback_model = _model_state["fallback_model"]

    if not _model_state["trained_weights_loaded"] or _model_state["scaler_mean"] is None:
        if fallback_model is None or not _model_state["fallback_weights_loaded"]:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="TDSM model/scaler not loaded and fallback unavailable."
            )
        model_used = "FALLBACK"
        fallback_reason = "Primary TDSM weights or scaler unavailable; fail-safe engaged."
    else:
        model_used = "TDSM"
        fallback_reason = None

    if model_used == "TDSM":
        continuous_batch, compound_batch, raw_d, cutoff_laps = [], [], [], []
        for lap in laps:
            comp_str = lap.Compound if lap.Compound else COMPOUNDS[lap.CompoundIdx if lap.CompoundIdx is not None else 5]
            comp_oh = one_hot_compound(comp_str)
            continuous = np.array([lap.D, lap.Delta_D, lap.Delta2_D, lap.TyreLife, lap.FuelProxy], dtype=np.float32)
            continuous_batch.append(continuous)
            compound_batch.append(comp_oh)
            raw_d.append(lap.D)
            cutoff_laps.append(lap.data_cutoff_lap)

        continuous_batch = np.stack(continuous_batch)
        compound_batch = np.stack(compound_batch)
        raw_d = np.array(raw_d, dtype=np.float32)

        # Strictly standardized via frozen training scaler
        scaled = (continuous_batch - _model_state["scaler_mean"]) / _model_state["scaler_std"]

        x = np.concatenate([scaled, compound_batch], axis=1).astype(np.float32)
        x_t = torch.tensor(x, dtype=torch.float32)
        raw_d_t = torch.tensor(raw_d, dtype=torch.float32)

        try:
            with torch.no_grad():
                forecast = model.predict_forecast_debt(x_t, raw_d_t).cpu().numpy()
        except Exception as inf_err:
            logger.error("Primary TDSM inference error: %s. Engaging operational fallback.", inf_err)
            model_used = "FALLBACK"
            fallback_reason = str(inf_err)

    if model_used == "FALLBACK":
        fb_x = []
        cutoff_laps = []
        for lap in laps:
            c_idx = lap.CompoundIdx if lap.CompoundIdx is not None else COMPOUND_MAP.get(str(lap.Compound).upper(), 5)
            fb_x.append([lap.D, lap.Delta_D, lap.Delta2_D, lap.TyreLife, c_idx, lap.FuelProxy])
            cutoff_laps.append(lap.data_cutoff_lap)
        with torch.no_grad():
            forecast = fallback_model(torch.tensor(fb_x, dtype=torch.float32)).cpu().numpy()

    results = []
    for i, row in enumerate(forecast):
        results.append(
            ForecastItem(
                Forecast_plus_1=round(float(row[0]), 4),
                Forecast_plus_3=round(float(row[1]), 4),
                Forecast_plus_5=round(float(row[2]), 4),
                Forecast_plus_10=round(float(row[3]), 4),
                model_used=model_used,
                fallback_reason=fallback_reason,
                data_cutoff_lap=cutoff_laps[i]
            )
        )
    return results


@router.post("/predict")
def predict_tdsm(payload: Union[BatchedPredictRequest, LapState]):
    try:
        # Check if single lap or batched
        if isinstance(payload, BatchedPredictRequest):
            items = _predict_laps(payload.laps)
            return BatchedPredictResponse(results=items)
        else:
            items = _predict_laps([payload])
            item = items[0]
            return SinglePredictResponse(
                model="TDSM",
                model_version=_model_state["model_version"],
                model_used=item.model_used,
                fallback_reason=item.fallback_reason,
                data_cutoff_lap=item.data_cutoff_lap,
                forecast={
                    "+1": item.Forecast_plus_1,
                    "+3": item.Forecast_plus_3,
                    "+5": item.Forecast_plus_5,
                    "+10": item.Forecast_plus_10
                }
            )
    except Exception as e:
        logger.exception("Prediction endpoint failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error during prediction - see server logs."
        )


@router.get("/health", status_code=status.HTTP_200_OK)
def tdsm_health():
    return {
        "status": "running",
        "model": "TDSM",
        "model_version": _model_state["model_version"],
        "trained_weights_loaded": _model_state["trained_weights_loaded"],
        "scaler_loaded": _model_state["scaler_mean"] is not None,
        "fallback_available": _model_state["fallback_weights_loaded"],
        "horizons": [1, 3, 5, 10],
        "input_dim": INPUT_DIM,
        "max_batch_size": MAX_BATCH_SIZE
    }


@router.get("/metadata", status_code=status.HTTP_200_OK)
def tdsm_metadata():
    return {
        "model": "TDSM",
        "model_version": _model_state["model_version"],
        "input_features": [
            "D", "Delta_D", "Delta2_D", "TyreLife", "CompoundIdx", "FuelProxy"
        ],
        "state_dimension": 3,
        "context_dimension": 8,
        "input_dimension": INPUT_DIM,
        "encoded_features": [
            "D", "Delta_D", "Delta2_D", "TyreLife", "FuelProxy",
            "Compound_SOFT", "Compound_MEDIUM", "Compound_HARD",
            "Compound_INTERMEDIATE", "Compound_WET", "Compound_UNKNOWN"
        ],
        "horizons": [1, 3, 5, 10],
        "training_year": 2024,
        "validation_year": 2025,
        "fallback_model": "FallbackTDSM (6-input direct regressor, operational fallback only)"
    }


# Direct root/v1 compatibility routes
v1_router.add_api_route("/v1/predict", predict_tdsm, methods=["POST"])

