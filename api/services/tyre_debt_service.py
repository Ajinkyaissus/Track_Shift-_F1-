"""
Tyre Debt Service for TrackShift.
Handles residual tyre debt ledgers and hybrid DL/ML behavioral attributions.
"""

import math
from typing import Any, Dict
from fastapi import HTTPException

from api.cache import CacheKeys, get_cache_service, LEDGER_VERSION
from api.models import get_model_registry, BEHAVIORAL_FEATURES

class TyreDebtService:
    def __init__(self, db_path: str, app_data: Dict[str, Any]):
        self.db_path = db_path
        self.app_data = app_data
        self.cache = get_cache_service()
        self.registry = get_model_registry()
        self._ensure_data_loaded()

    def _ensure_data_loaded(self):
        import os
        import pandas as pd
        BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        DATA_DIR = os.path.join(BASE_DIR, 'data')
        LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')
        LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')

        if not self.app_data.get("ledger") and os.path.exists(LEDGER_PARQUET):
            ledger_df = pd.read_parquet(LEDGER_PARQUET)
            self.app_data.setdefault("ledger", {})
            for stint_id, group in ledger_df.groupby('stint_id'):
                self.app_data["ledger"][stint_id] = group[['lap_number', 'residual', 'cumulative_debt']].to_dict(orient='records')

        if not self.app_data.get("stint_feature_means") and os.path.exists(LAPS_PARQUET):
            laps_df = pd.read_parquet(LAPS_PARQUET)
            means_df = laps_df.groupby('stint_id')[BEHAVIORAL_FEATURES].mean()
            self.app_data["stint_feature_means"] = means_df.to_dict(orient='index')

    async def get_ledger(self, stint_id: str) -> Dict[str, Any]:
        self._ensure_data_loaded()
        if stint_id not in self.app_data.get("ledger", {}):
            raise HTTPException(status_code=404, detail=f"Stint ledger '{stint_id}' not found in real dataset")

        cache_key = CacheKeys.stint_ledger(stint_id, LEDGER_VERSION)

        async def _compute():
            series = self.app_data["ledger"][stint_id]
            total_debt = round(series[-1]["cumulative_debt"], 4) if len(series) > 0 else 0.0
            
            return {
                "stint_id": stint_id,
                "model_version": self.app_data.get("active_models", {}).get(1, "v3_stage1_2026-09-07"),
                "total_debt_seconds": total_debt,
                "series": series
            }

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)

    async def get_attribution(self, stint_id: str) -> Dict[str, Any]:
        self._ensure_data_loaded()
        if stint_id not in self.app_data.get("stint_feature_means", {}):
            laps_df = self.app_data.get("laps_df")
            if laps_df is None and os.path.exists(LAPS_PARQUET):
                laps_df = pd.read_parquet(LAPS_PARQUET)
                self.app_data["laps_df"] = laps_df
            
            if laps_df is not None and not laps_df.empty and 'stint_id' in laps_df.columns:
                st_laps = laps_df[laps_df['stint_id'] == stint_id]
                if not st_laps.empty:
                    means = st_laps[BEHAVIORAL_FEATURES].mean().to_dict()
                    self.app_data.setdefault("stint_feature_means", {})[stint_id] = means

        if stint_id not in self.app_data.get("stint_feature_means", {}):
            raise HTTPException(status_code=404, detail=f"Stint features '{stint_id}' not found in real telemetry dataset")
            
        stage3_version = self.app_data.get("active_models", {}).get(3) or self.registry.get_stage_version(3)
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
