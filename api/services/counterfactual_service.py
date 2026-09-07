"""
Counterfactual Service for TrackShift.
Executes physically bounded observational sensitivity calculations:
R_bounded = R_max * tanh(R_linear / R_max)
and attaches empirical stint bootstrap confidence intervals.
"""

import time
import math
from typing import Any, Dict, Optional, Tuple
from fastapi import HTTPException
from pydantic import BaseModel

from api.cache import CacheKeys, get_cache_service
from api.models import get_model_registry

class CounterfactualRequest(BaseModel):
    feature: str
    delta_pct: float

class CounterfactualService:
    def __init__(self, app_data: Dict[str, Any]):
        self.app_data = app_data
        self.cache = get_cache_service()
        self.registry = get_model_registry()

    async def compute_counterfactual(self, stint_id: str, feature: str, delta_pct: float) -> Dict[str, Any]:
        start_time = time.perf_counter()
        
        if abs(delta_pct) > 100.0:
            raise HTTPException(
                status_code=400, 
                detail=f"Adjustment delta {delta_pct}% exceeds supported domain range [-100.0%, +100.0%]."
            )
        
        if stint_id not in self.app_data["stint_feature_means"]:
            raise HTTPException(status_code=404, detail="Stint features not found")
            
        stage3_version = self.app_data["active_models"].get(3)
        if not stage3_version:
            raise HTTPException(status_code=500, detail="No active stage 3 model")
            
        avg_feat_val = self.app_data["stint_feature_means"][stint_id].get(feature)
        if avg_feat_val is None or math.isnan(avg_feat_val):
            raise HTTPException(status_code=400, detail="Invalid feature or missing data")

        cache_key = CacheKeys.stint_counterfactual(stint_id, stage3_version, feature, delta_pct)

        async def _compute():
            track_id = self.app_data["stint_track_map"].get(stint_id)
            coef = self.app_data["coefficients"].get((stage3_version, feature, track_id))
            if coef is None:
                coef = self.app_data["coefficients"].get((stage3_version, feature, None))
            if coef is None:
                coef = self.registry.get_coefficient(stage3_version, feature, track_id)
            
            seconds_debt_recovered = - (coef * (delta_pct / 100.0) * avg_feat_val)
            
            deg_per_lap = self.app_data["stint_avg_loss_per_lap"].get(stint_id, 0.1)
            stint_len = self.app_data.get("stint_lengths", {}).get(stint_id, 20)

            # Check precomputed bootstrap uncertainty table
            boot_lookup = self.app_data.get("bootstrap_uncertainty", {}).get((stint_id, feature, round(delta_pct, 1)))
            bootstrap_ci = (boot_lookup["ci_lower"], boot_lookup["ci_upper"]) if boot_lookup else None

            # Enforce physical saturation guardrail with bootstrap CI
            cf_eval = self.registry.behavioral_model.compute_counterfactual_recovery(
                linear_loss_recovery=seconds_debt_recovered,
                stint_length=stint_len,
                deg_per_lap=deg_per_lap,
                bootstrap_ci=bootstrap_ci
            )
            
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            
            return {
                "feature": feature,
                "delta_pct": delta_pct,
                "recovered_laps": cf_eval["recovered_laps"],
                "ci_95": cf_eval["ci_95"],
                "uncertainty_margin": cf_eval["uncertainty_margin"],
                "uncertainty_method": cf_eval.get("uncertainty_method", "stint_cluster_bootstrap"),
                "is_saturated": cf_eval["is_saturated"],
                "model_version": stage3_version,
                "methodology": "model_based_hypothetical_sensitivity",
                "compute_path": "server_lookup",
                "measured_latency_ms": latency_ms
            }

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)
