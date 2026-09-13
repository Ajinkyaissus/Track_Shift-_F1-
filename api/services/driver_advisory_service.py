"""
TrackShift — Driver Advisory API Service
========================================
Bridges telemetry data, tyre performance debt, and strategic warfare checkpoints
with the Driver Advisory Engine to provide real-time race-engineer recommendations.
"""

import os
import sqlite3
from typing import Any, Dict, Optional
import pandas as pd

from trackshift.strategy.driver_advisory import generate_driver_advisory
from trackshift.strategy.config import CIRCUIT_METRICS, DEFAULT_METRICS
from trackshift.strategy.simulator import execute_strategic_checkpoint


class DriverAdvisoryService:
    def __init__(self, db_path: str, app_data: Dict[str, Any]):
        self.db_path = db_path
        self.app_data = app_data

    def _get_laps_df(self) -> pd.DataFrame:
        if self.app_data.get("laps_df") is not None:
            return self.app_data["laps_df"]
        return pd.DataFrame()

    def _get_ledger_df(self) -> pd.DataFrame:
        if self.app_data.get("ledger_df") is not None:
            return self.app_data["ledger_df"]
        return pd.DataFrame()

    def get_driver_advisory(
        self,
        session_id: str,
        driver_id: Optional[str] = None,
        lap: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates machine-readable operational radio advisory for a given driver and lap.
        Uses in-memory indexed telemetry and strategic checkpoint analysis.
        """
        # Parse circuit key
        parts = session_id.split('_')
        track_id = parts[1].lower() if len(parts) > 1 else "silverstone"
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

        # Determine driver and lap
        if not s_laps.empty:
            available_drivers = s_laps["driver_id"].unique().tolist() if "driver_id" in s_laps.columns else (s_laps["driver"].unique().tolist() if "driver" in s_laps.columns else ["HAM"])
            if not driver_id or driver_id not in available_drivers:
                driver_id = available_drivers[0]
            max_session_lap = int(s_laps["lap_number"].max())
        else:
            driver_id = driver_id or "HAM"
            max_session_lap = total_laps

        current_lap = int(lap) if (lap is not None and lap > 0) else max(1, min(20, max_session_lap))

        # Checkpoint strategic execution
        checkpoint_res = execute_strategic_checkpoint(
            session_id=session_id,
            circuit_key=track_id,
            driver_code=driver_id,
            checkpoint_lap=current_lap,
            total_laps=total_laps,
            session_laps_df=s_laps,
            session_ledger_df=s_ledger
        )

        debt_liq = checkpoint_res.get("debt_liquidation", {})
        perf_inst = checkpoint_res.get("performance_instability", {})
        undercut = checkpoint_res.get("undercut_vulnerability", {})

        tyre_age = int(debt_liq.get("tyre_age", current_lap))
        cum_debt = float(debt_liq.get("cumulative_debt_sec", 0.0))
        deg_rate = float(debt_liq.get("current_burn_rate_sec_per_lap", 0.05))
        liq_state = str(debt_liq.get("liquidation_state", "NOMINAL"))
        cliff_prob = float(perf_inst.get("instability_score", 0.1))
        threat = str(undercut.get("threat_level", "LOW"))

        # Calculate pit windows
        earliest_forced = max(1, current_lap if cliff_prob > 0.6 else int(current_lap + 2))
        optimal_target = max(earliest_forced, min(total_laps, int(current_lap + max(1, round((3.0 - cum_debt) / max(0.05, deg_rate))))))
        latest_safe = min(total_laps, optimal_target + 4)

        sample_cnt = len(s_laps[s_laps["driver_id"] == driver_id]) if ("driver_id" in s_laps.columns and not s_laps.empty) else 25

        advisory_obj = generate_driver_advisory(
            current_lap=current_lap,
            tyre_age=tyre_age,
            cumulative_debt=cum_debt,
            debt_trend=deg_rate,
            degradation_state=liq_state,
            cliff_risk=cliff_prob,
            earliest_forced_pit=earliest_forced,
            optimal_pit=optimal_target,
            latest_safe_pit=latest_safe,
            competitor_threat=threat,
            sample_count=sample_cnt,
            model_status="STAGE2_PRODUCTION"
        )

        return advisory_obj.to_dict()
