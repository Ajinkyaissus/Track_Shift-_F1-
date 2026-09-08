"""
Stints Service for TrackShift.
Handles race listings, stint queries, and stint comparisons.
"""

import os
import sqlite3
import pandas as pd
from typing import Any, Dict, List, Optional
from fastapi import HTTPException

from api.cache import CacheKeys, get_cache_service, DATA_VERSION
from api.services.circuits_service import get_driver_profile_image
from api.models import BEHAVIORAL_FEATURES

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')

class StintsService:
    def __init__(self, db_path: str, app_data: Dict[str, Any]):
        self.db_path = db_path
        self.app_data = app_data
        self.cache = get_cache_service()

    def _ensure_data_loaded(self):
        if not self.app_data.get("stint_feature_means") and os.path.exists(LAPS_PARQUET):
            laps_df = pd.read_parquet(LAPS_PARQUET)
            means_df = laps_df.groupby('stint_id')[BEHAVIORAL_FEATURES].mean()
            self.app_data["stint_feature_means"] = means_df.to_dict(orient='index')

        if not self.app_data.get("ledger") and os.path.exists(LEDGER_PARQUET):
            ledger_df = pd.read_parquet(LEDGER_PARQUET)
            for stint_id, group in ledger_df.groupby('stint_id'):
                self.app_data["ledger"][stint_id] = group[['lap_number', 'residual', 'cumulative_debt']].to_dict(orient='records')

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    async def get_races(self) -> List[Dict[str, Any]]:
        cache_key = CacheKeys.races_list(DATA_VERSION)

        async def _compute():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = self._dict_factory
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT race_id, season, round, track_id, event_date, event_name 
                    FROM races 
                    ORDER BY CASE WHEN race_id IN (SELECT DISTINCT ses.race_id FROM sessions ses JOIN stints st ON ses.session_id = st.session_id WHERE st.is_valid = 1) THEN 0 
                                  WHEN status = 'VERIFIED' THEN 1 
                                  ELSE 2 END, season DESC, round DESC
                """)
                races = cursor.fetchall()
            return races

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)

    async def get_stints_by_query(self, race_id: Optional[str] = None) -> List[Dict[str, Any]]:
        self._ensure_data_loaded()
        cache_key = CacheKeys.stints_list(race_id, DATA_VERSION)

        async def _compute():
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = self._dict_factory
                cursor = conn.cursor()
                if race_id:
                    if race_id.startswith("2023_") or "2023" in race_id:
                        raise HTTPException(status_code=404, detail="Season 2023 is unsupported.")
                    clean_id = race_id.replace("_R", "")
                    cursor.execute("SELECT 1 FROM races WHERE race_id = ? OR race_id = ?", (race_id, clean_id))
                    if not cursor.fetchone():
                        cursor.execute("SELECT 1 FROM sessions WHERE session_id = ? OR session_id = ?", (race_id, f"{clean_id}_R"))
                        if not cursor.fetchone():
                            raise HTTPException(status_code=404, detail=f"Race/Session '{race_id}' not found")

                    cursor.execute("""
                        SELECT s.stint_id, s.session_id, s.driver_id, s.compound, s.start_lap, s.end_lap, s.tyre_age_start
                        FROM stints s
                        LEFT JOIN sessions ses ON s.session_id = ses.session_id
                        WHERE (ses.race_id = ? OR ses.race_id = ? OR ses.session_id = ? OR s.session_id = ? OR s.session_id = ?) AND s.is_valid = 1
                        ORDER BY s.start_lap ASC
                    """, (race_id, clean_id, race_id, f"{clean_id}_R", race_id))
                else:
                    cursor.execute("""
                        SELECT s.stint_id, s.session_id, s.driver_id, s.compound, s.start_lap, s.end_lap, s.tyre_age_start
                        FROM stints s
                        WHERE s.is_valid = 1
                        ORDER BY s.start_lap ASC
                    """)
                stints = cursor.fetchall()
                if self.app_data.get("stint_feature_means"):
                    valid_stints = [s for s in stints if s['stint_id'] in self.app_data["stint_feature_means"]]
                    if valid_stints:
                        stints = valid_stints
            return stints

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)

    async def compare_stints(self, stint_a: str, stint_b: str) -> Dict[str, Any]:
        self._ensure_data_loaded()
        if stint_a not in self.app_data.get("stint_feature_means", {}):
            raise HTTPException(status_code=404, detail=f"Stint '{stint_a}' not found in real telemetry dataset")
        if stint_b not in self.app_data.get("stint_feature_means", {}):
            raise HTTPException(status_code=404, detail=f"Stint '{stint_b}' not found in real telemetry dataset")

        stage3_version = self.app_data.get("active_models", {}).get(3, "v4_tcn_stage3_2026-09-07")
        cache_key = CacheKeys.stints_compare(stint_a, stint_b, stage3_version)

        async def _compute():
            feats_a = self.app_data["stint_feature_means"][stint_a]
            feats_b = self.app_data["stint_feature_means"][stint_b]
            
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = self._dict_factory
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT s.*, d.full_name, d.team, r.event_name FROM stints s JOIN drivers d ON s.driver_id = d.driver_id JOIN sessions ses ON s.session_id = ses.session_id JOIN races r ON ses.race_id = r.race_id WHERE s.stint_id IN (?, ?)",
                    (stint_a, stint_b)
                )
                meta_rows = {}
                for row in cursor.fetchall():
                    row['profile_image'] = get_driver_profile_image(row.get('driver_id', ''))
                    meta_rows[row['stint_id']] = row

            ledger_a = self.app_data["ledger"].get(stint_a, [])
            ledger_b = self.app_data["ledger"].get(stint_b, [])
            
            total_debt_a = ledger_a[-1]["cumulative_debt"] if ledger_a else 0.0
            total_debt_b = ledger_b[-1]["cumulative_debt"] if ledger_b else 0.0
            
            feature_comparisons = []
            for feat in BEHAVIORAL_FEATURES:
                val_a = feats_a.get(feat, 0.0)
                val_b = feats_b.get(feat, 0.0)
                feature_comparisons.append({
                    "feature": feat,
                    "stint_a_val": round(val_a, 4),
                    "stint_b_val": round(val_b, 4),
                    "delta_b_minus_a": round(val_b - val_a, 4),
                    "delta_pct": round(((val_b - val_a) / val_a * 100.0) if val_a != 0 else 0.0, 2)
                })

            return {
                "stint_a": meta_rows.get(stint_a, {"stint_id": stint_a}),
                "stint_b": meta_rows.get(stint_b, {"stint_id": stint_b}),
                "total_debt_seconds": {
                    "stint_a": round(total_debt_a, 3),
                    "stint_b": round(total_debt_b, 3),
                    "delta": round(total_debt_b - total_debt_a, 3)
                },
                "feature_comparisons": feature_comparisons
            }

        return await self.cache.single_flight(cache_key, _compute, attach_metadata=False)
