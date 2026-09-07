"""
Driver Signatures & Signature Transfer Service for TrackShift.
Handles cross-driver behavioral transfer projections and driver profile signatures
with physically bounded limits and empirical bootstrap uncertainty intervals.
"""

import sqlite3
import math
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
from pydantic import BaseModel

from api.cache import CacheKeys, get_cache_service
from api.models import get_model_registry

class SignatureTransferRequest(BaseModel):
    target_driver_id: Optional[str] = None
    target_driver: Optional[str] = None

class SignaturesService:
    def __init__(self, db_path: str, app_data: Dict[str, Any]):
        self.db_path = db_path
        self.app_data = app_data
        self.cache = get_cache_service()
        self.registry = get_model_registry()

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    async def get_signatures(self) -> List[Dict[str, Any]]:
        if 1 not in self.app_data["active_models"] or 3 not in self.app_data["active_models"]:
            raise HTTPException(status_code=503, detail="Signature features unavailable: models not fully trained")

        stage3_version = self.app_data["active_models"].get(3, "v5_tcn_stage3_2026-09-07")
        cache_key = CacheKeys.signatures_list(stage3_version)

        async def _compute():
            sigs = []
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = self._dict_factory
                cursor = conn.cursor()
                cursor.execute("SELECT driver_id, full_name, team, reputation_tag FROM drivers")
                driver_meta = {d['driver_id']: d for d in cursor.fetchall()}

            for driver_id, feats in self.app_data.get('driver_signatures', {}).items():
                meta = driver_meta.get(driver_id, {"full_name": driver_id, "team": "F1 Team", "reputation_tag": "neutral"})
                sigs.append({
                    "driver_id": driver_id,
                    "full_name": meta["full_name"],
                    "team": meta["team"],
                    "reputation_tag": meta["reputation_tag"],
                    "features": {k: round(v, 4) for k, v in feats.items()}
                })
            return sigs

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)

    async def compute_signature_transfer(self, stint_id: str, target_driver: str) -> Dict[str, Any]:
        if not target_driver:
            raise HTTPException(status_code=400, detail="Missing target_driver or target_driver_id in request")
            
        if 1 not in self.app_data["active_models"] or 3 not in self.app_data["active_models"]:
            raise HTTPException(status_code=503, detail="Signature transfer unavailable: models not fully trained")
            
        if stint_id not in self.app_data['stint_feature_means']:
            raise HTTPException(status_code=404, detail='Stint features not found')
            
        stage3_version = self.app_data['active_models'].get(3)
        if not stage3_version:
            raise HTTPException(status_code=500, detail='No active stage 3 model')
            
        if target_driver not in self.app_data['driver_signatures']:
            raise HTTPException(status_code=400, detail=f"Target driver signature '{target_driver}' not found")

        cache_key = CacheKeys.stint_signature_transfer(stint_id, stage3_version, target_driver)

        async def _compute():
            actual_means = self.app_data['stint_feature_means'][stint_id]
            target_signature = self.app_data['driver_signatures'][target_driver]
            
            deg_per_lap = self.app_data['stint_avg_loss_per_lap'].get(stint_id, 0.1)
            if deg_per_lap == 0.0:
                deg_per_lap = 0.1
                
            net_seconds_recovered = 0.0
            feature_deltas = []
            track_id = self.app_data["stint_track_map"].get(stint_id)
            
            for feature, actual_val in actual_means.items():
                if math.isnan(actual_val):
                    actual_val = 0.0
                    
                target_val = target_signature.get(feature, actual_val)
                if math.isnan(target_val):
                    target_val = 0.0
                    
                delta_val = target_val - actual_val
                
                coef = self.app_data['coefficients'].get((stage3_version, feature, track_id))
                if coef is None:
                    coef = self.app_data['coefficients'].get((stage3_version, feature, None))
                if coef is None:
                    coef = self.registry.get_coefficient(stage3_version, feature, track_id)
                    
                seconds_debt_recovered = - (coef * delta_val)
                net_seconds_recovered += seconds_debt_recovered
                
                feature_deltas.append({
                    'feature': feature,
                    'current_val': round(actual_val, 4),
                    'target_val': round(target_val, 4),
                    'delta_val': round(delta_val, 4),
                    'seconds_debt_recovered': round(seconds_debt_recovered, 4)
                })
                
            stint_len = self.app_data.get("stint_lengths", {}).get(stint_id, 20)
            cf_eval = self.registry.behavioral_model.compute_counterfactual_recovery(
                linear_loss_recovery=net_seconds_recovered,
                stint_length=stint_len,
                deg_per_lap=deg_per_lap
            )
            
            parts = stint_id.split('_')
            source_driver = parts[-2] if len(parts) >= 3 else "UNKNOWN"

            return {
                'stint_id': stint_id,
                'source_driver': source_driver,
                'source_driver_id': source_driver,
                'target_driver': target_driver,
                'target_driver_id': target_driver,
                'recovered_laps': cf_eval["recovered_laps"],
                'net_recovered_laps': cf_eval["recovered_laps"],
                'ci_95': cf_eval["ci_95"],
                'uncertainty_margin': cf_eval["uncertainty_margin"],
                'uncertainty_method': cf_eval.get("uncertainty_method", "stint_cluster_bootstrap"),
                'is_saturated': cf_eval["is_saturated"],
                'model_version': stage3_version,
                'feature_deltas': feature_deltas
            }

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)
