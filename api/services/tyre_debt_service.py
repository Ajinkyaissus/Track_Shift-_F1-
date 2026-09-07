"""
Tyre Debt Service for TrackShift.
Handles residual tyre debt ledgers and hybrid DL/ML behavioral attributions.
"""

import math
from typing import Any, Dict, List, Optional
from fastapi import HTTPException

from api.cache import CacheKeys, get_cache_service, LEDGER_VERSION
from api.models import get_model_registry, BEHAVIORAL_FEATURES

class TyreDebtService:
    def __init__(self, db_path: str, app_data: Dict[str, Any]):
        self.db_path = db_path
        self.app_data = app_data
        self.cache = get_cache_service()
        self.registry = get_model_registry()

    async def get_ledger(self, stint_id: str) -> Dict[str, Any]:
        if stint_id not in self.app_data["ledger"]:
            raise HTTPException(status_code=404, detail=f"Stint ledger '{stint_id}' not found")

        cache_key = CacheKeys.stint_ledger(stint_id, LEDGER_VERSION)

        async def _compute():
            series = self.app_data["ledger"][stint_id]
            total_debt = round(series[-1]["cumulative_debt"], 4) if len(series) > 0 else 0.0
            
            return {
                "stint_id": stint_id,
                "model_version": self.app_data["active_models"].get(1, "v3_stage1_2026-09-07"),
                "total_debt_seconds": total_debt,
                "series": series
            }

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)

    async def get_attribution(self, stint_id: str) -> Dict[str, Any]:
        if stint_id not in self.app_data["stint_feature_means"]:
            raise HTTPException(status_code=404, detail="Stint features not found")
            
        stage3_version = self.app_data["active_models"].get(3)
        if not stage3_version:
            raise HTTPException(status_code=500, detail="No active stage 3 model")

        cache_key = CacheKeys.stint_attribution(stint_id, stage3_version)

        async def _compute():
            means = self.app_data["stint_feature_means"][stint_id]
            track_id = self.app_data["stint_track_map"].get(stint_id)
            
            # Behavioral embedding
            emb = self.registry.get_or_generate_embedding(stint_id)
            
            attribution = []
            total_abs_contrib = 0.0
            contribs = {}
            
            for feature, avg_val in means.items():
                if math.isnan(avg_val):
                    avg_val = 0.0
                    
                coef = self.app_data["coefficients"].get((stage3_version, feature, track_id))
                if coef is None:
                    coef = self.app_data["coefficients"].get((stage3_version, feature, None))
                if coef is None:
                    coef = self.registry.get_coefficient(stage3_version, feature, track_id)
                    
                contrib = coef * avg_val
                contribs[feature] = contrib
                total_abs_contrib += abs(contrib)
                
            if total_abs_contrib == 0:
                total_abs_contrib = 1.0
                
            for feature, avg_val in means.items():
                if math.isnan(avg_val):
                    avg_val = 0.0
                    
                contrib = contribs[feature]
                pct = (abs(contrib) / total_abs_contrib) * 100.0
                
                coef = self.app_data["coefficients"].get((stage3_version, feature, track_id))
                if coef is None:
                    coef = self.app_data["coefficients"].get((stage3_version, feature, None))
                if coef is None:
                    coef = self.registry.get_coefficient(stage3_version, feature, track_id)
                    
                attribution.append({
                    "feature": feature,
                    "feature_name": feature.replace("_", " ").title(),
                    "contribution": round(contrib, 4),
                    "share_pct": round(pct, 2),
                    "pct_contribution": round(pct, 2),
                    "coefficient": round(coef, 6),
                    "mean_value": round(avg_val, 4),
                    "unit": f"seconds debt per 1 unit {feature}"
                })
                
            deg_per_lap = self.app_data["stint_avg_loss_per_lap"].get(stint_id, 0.1)
                
            return {
                "stint_id": stint_id,
                "model_version": stage3_version,
                "algorithm": "hybrid_tcn_ridge_attribution" if "tcn" in stage3_version else "ridge_linear_attribution",
                "behavioral_embedding_dim": len(emb),
                "deg_per_lap": round(deg_per_lap, 4),
                "attribution": attribution
            }

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)
