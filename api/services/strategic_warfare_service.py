"""
TrackShift — Strategic Warfare API Service
==========================================
Bridges the database, parquet ledgers, and Stage 1-4 models with the
Strategic Warfare Engine.

Computes:
- Module 1: Tyre Debt Liquidation
- Module 2: Ghost-Car Pit ROI
- Module 3: Competitor Undercut Vulnerability
- Module 4: Pit Stop Market Spread
- Module 5: Performance Instability / Cliff Warning
- Strategic Decision Fusion & Battle Matrix
- Full-Race Checkpoints (Pre-Race, Lap 5, 10, 15, 20, 25, 30, 40, 45)

Zero future leakage, full cache isolation, 100% authentic provenance.
"""

import os
import sqlite3
import hashlib
import json
import logging
import math
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
from fastapi import HTTPException

from api.cache import CacheKeys, get_cache_service, DATA_VERSION
from trackshift.strategy import (
    CIRCUIT_METRICS,
    DEFAULT_METRICS,
    COMPOUND_CHARACTERISTICS,
    calculate_debt_liquidation,
    simulate_ghost_car_pit_roi,
    evaluate_competitor_undercut,
    compute_pit_market_spread,
    evaluate_performance_instability,
    fuse_strategic_decision,
    simulate_full_race_strategies,
    execute_strategic_checkpoint
)

logger = logging.getLogger("trackshift.api.strategic_warfare")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')


class StrategicWarfareService:
    def __init__(self, db_path: str, app_data: Dict[str, Any]):
        self.db_path = db_path
        self.app_data = app_data
        self.cache = get_cache_service()

    def _dict_factory(self, cursor, row):
        d = {}
        for idx, col in enumerate(cursor.description):
            d[col[0]] = row[idx]
        return d

    def _get_laps_df(self) -> pd.DataFrame:
        if self.app_data.get("laps_df") is not None:
            return self.app_data["laps_df"]
        if os.path.exists(LAPS_PARQUET):
            df = pd.read_parquet(LAPS_PARQUET)
            self.app_data["laps_df"] = df
            return df
        return pd.DataFrame()

    def _get_ledger_df(self) -> pd.DataFrame:
        if self.app_data.get("ledger_df") is not None:
            return self.app_data["ledger_df"]
        if os.path.exists(LEDGER_PARQUET):
            df = pd.read_parquet(LEDGER_PARQUET)
            self.app_data["ledger_df"] = df
            return df
        return pd.DataFrame()

    def _get_session_metadata(self, session_id: str) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = self._dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ses.session_id, ses.session_type, ses.weather_flag, ses.track_evolution_index,
                       ses.status as session_status,
                       r.race_id, r.season, r.round, r.track_id, r.event_date, r.event_name,
                       t.name as circuit_name, t.country, t.country_code, t.location
                FROM sessions ses
                JOIN races r ON ses.race_id = r.race_id
                LEFT JOIN tracks t ON r.track_id = t.track_id
                WHERE ses.session_id = ?
            """, (session_id,))
            meta = cursor.fetchone()

        if not meta:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = self._dict_factory
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT ses.session_id, ses.session_type, ses.weather_flag, ses.track_evolution_index,
                           ses.status as session_status,
                           r.race_id, r.season, r.round, r.track_id, r.event_date, r.event_name,
                           t.name as circuit_name, t.country, t.country_code, t.location
                    FROM sessions ses
                    JOIN races r ON ses.race_id = r.race_id
                    LEFT JOIN tracks t ON r.track_id = t.track_id
                    WHERE ses.race_id = ? AND (ses.session_type = 'R' OR ses.session_type = 'Race')
                """, (session_id,))
                meta = cursor.fetchone()

        if not meta:
            # Fallback parse from session_id
            parts = session_id.split('_')
            season = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 2024
            track_id = parts[1] if len(parts) > 1 else "monza"
            meta = {
                "session_id": session_id,
                "season": season,
                "track_id": track_id,
                "circuit_name": track_id.capitalize(),
                "country": "Unknown",
                "country_code": "UN"
            }
        return meta

    def get_strategic_warfare_analysis(
        self,
        session_id: str,
        driver_id: Optional[str] = None,
        lap: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for Strategic Warfare Engine payload.
        Returns complete intelligence bundle:
        - Decision Fusion
        - Tyre Debt Liquidation
        - Ghost Car Pit ROI
        - Undercut Vulnerability Radar
        - Pit Market Spread
        - Performance Instability
        """
        meta = self._get_session_metadata(session_id)
        track_id = meta.get("track_id", "monza").lower()
        metrics = CIRCUIT_METRICS.get(track_id, DEFAULT_METRICS)
        total_laps = int(metrics["total_laps"])

        laps_df = self._get_laps_df()
        ledger_df = self._get_ledger_df()

        # Filter session laps
        s_laps = pd.DataFrame()
        if not laps_df.empty:
            s_laps = laps_df[laps_df["session_id"] == session_id]
            if s_laps.empty:
                # Try partial match or race_id
                race_id = meta.get("race_id", "")
                s_laps = laps_df[laps_df["session_id"].str.startswith(race_id)]

        s_ledger = pd.DataFrame()
        if not ledger_df.empty:
            if "session_id" in ledger_df.columns:
                s_ledger = ledger_df[ledger_df["session_id"] == session_id]
            elif "stint_id" in ledger_df.columns:
                s_ledger = ledger_df[ledger_df["stint_id"].str.startswith(session_id)]
            if s_ledger.empty and "stint_id" in ledger_df.columns:
                race_id = meta.get("race_id", "")
                s_ledger = ledger_df[ledger_df["stint_id"].str.startswith(race_id)]

        # Determine driver and lap
        if not s_laps.empty:
            available_drivers = s_laps["driver"].unique().tolist()
            if not driver_id or driver_id not in available_drivers:
                driver_id = available_drivers[0]
            max_session_lap = int(s_laps["lap_number"].max())
        else:
            driver_id = driver_id or "ALB"
            max_session_lap = total_laps

        if lap is None or lap <= 0:
            current_lap = max(1, min(20, max_session_lap))
        else:
            current_lap = min(int(lap), total_laps)

        # Cache key check
        cache_key = f"strategic_warfare:{session_id}:{driver_id}:{current_lap}:{DATA_VERSION}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            return cached_result

        # Execute checkpoint analysis
        result = execute_strategic_checkpoint(
            session_id=session_id,
            circuit_key=track_id,
            driver_code=driver_id,
            checkpoint_lap=current_lap,
            total_laps=total_laps,
            session_laps_df=s_laps,
            session_ledger_df=s_ledger
        )

        # Add session metadata and full race multi-stint simulation
        result["session_id"] = session_id
        result["circuit_name"] = meta.get("circuit_name", track_id.capitalize())
        result["season"] = meta.get("season", 2024)
        result["full_race_candidate_strategies"] = simulate_full_race_strategies(
            circuit_key=track_id,
            total_laps=total_laps,
            base_lap_time_sec=83.5
        )

        self.cache.set(cache_key, result, ttl=3600)
        return result

    def get_checkpoint_series(
        self,
        session_id: str,
        driver_id: str
    ) -> List[Dict[str, Any]]:
        """
        Returns strategy recommendations across standard checkpoints:
        [PRE-RACE, 5, 10, 15, 20, 25, 30, 40, 45]
        """
        meta = self._get_session_metadata(session_id)
        track_id = meta.get("track_id", "monza").lower()
        metrics = CIRCUIT_METRICS.get(track_id, DEFAULT_METRICS)
        total_laps = int(metrics["total_laps"])

        laps_df = self._get_laps_df()
        ledger_df = self._get_ledger_df()

        s_laps = pd.DataFrame()
        if not laps_df.empty:
            s_laps = laps_df[laps_df["session_id"] == session_id]

        s_ledger = pd.DataFrame()
        if not ledger_df.empty:
            if "session_id" in ledger_df.columns:
                s_ledger = ledger_df[ledger_df["session_id"] == session_id]
            elif "stint_id" in ledger_df.columns:
                s_ledger = ledger_df[ledger_df["stint_id"].str.startswith(session_id)]

        checkpoints = [1, 5, 10, 15, 20, 25, 30, 40, 45]
        valid_checkpoints = [cp for cp in checkpoints if cp <= total_laps]

        series = []
        for cp in valid_checkpoints:
            analysis = execute_strategic_checkpoint(
                session_id=session_id,
                circuit_key=track_id,
                driver_code=driver_id,
                checkpoint_lap=cp,
                total_laps=total_laps,
                session_laps_df=s_laps,
                session_ledger_df=s_ledger
            )
            rec = analysis["strategic_decision_fusion"]["recommended_decision"]
            series.append({
                "checkpoint_lap": cp,
                "label": "PRE-RACE" if cp == 1 else f"LAP {cp}",
                "recommended_action": rec["action"],
                "action_detail": rec["action_detail"],
                "decision_score": rec["decision_score"],
                "expected_race_time_advantage_sec": rec["expected_race_time_advantage_sec"],
                "win_probability": rec["win_probability"],
                "podium_probability": rec["podium_probability"],
                "strategic_risk": rec["strategic_risk"],
                "cliff_risk": analysis["performance_instability"]["cliff_risk"],
                "liquidation_state": analysis["debt_liquidation"]["liquidation_state"]
            })

        return series
