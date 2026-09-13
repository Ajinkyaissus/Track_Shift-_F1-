"""
TrackShift — Confounder-Aware Tyre Intelligence Service
=======================================================
Bridges database, parquet telemetry ledgers, and tyre intelligence engines:
- Feature provenance catalog for observable variables
- Context-adjusted degradation curves with bootstrap uncertainty
- 8-Model Confounder Ablation Suite
- Post-race empirical validation suite against actual pace
"""

import os
from typing import Any, Dict, List, Optional
import pandas as pd
from fastapi import HTTPException

from trackshift.tyre_intelligence import (
    FEATURE_PROVENANCE_CATALOG,
    get_provenance_catalog_dict,
    ObservableConfounderEstimator,
    ObservableDecompositionModel,
    TyreDegradationCurveGenerator,
    PostRaceValidator,
    ConfounderAblationSuite,
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
LAPS_PARQUET = os.path.join(DATA_DIR, "laps.parquet")


class TyreIntelligenceService:
    def __init__(self, db_path: str, app_data: Optional[Dict[str, Any]] = None):
        self.db_path = db_path
        self.app_data = app_data or {}
        self.confounder_estimator = ObservableConfounderEstimator()
        self.decomposition_model = ObservableDecompositionModel(self.confounder_estimator)
        self.curve_generator = TyreDegradationCurveGenerator(
            self.confounder_estimator,
            self.decomposition_model,
        )
        self.post_race_validator = PostRaceValidator(self.curve_generator)
        self.ablation_suite = ConfounderAblationSuite(self.confounder_estimator)

    def _get_laps_df(self) -> pd.DataFrame:
        if self.app_data.get("laps_df") is not None:
            return self.app_data["laps_df"]
        if os.path.exists(LAPS_PARQUET):
            df = pd.read_parquet(LAPS_PARQUET)
            self.app_data["laps_df"] = df
            return df
        raise HTTPException(status_code=500, detail="Telemetry parquet ledger not found.")

    def get_provenance_catalog(self) -> Dict[str, Any]:
        """Returns the full 11-variable feature provenance catalog."""
        return {
            "status": "VERIFIED",
            "catalog": get_provenance_catalog_dict(),
            "total_features": len(FEATURE_PROVENANCE_CATALOG),
            "classification": "Observable Feature Catalog (No Hidden Synthetics)",
        }

    def get_estimated_degradation_curve(
        self,
        circuit_id: str = "silverstone",
        driver_id: str = "HAM",
        session_id: Optional[str] = None,
        stint_id: Optional[str] = None,
        max_tyre_age: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Generates the context-aware tyre performance degradation curve for a given stint/driver.
        Uses in-memory precomputed curves or indexed laps dataframe.
        """
        cache_key = (circuit_id, driver_id, session_id, stint_id, max_tyre_age)
        precomputed = self.app_data.get("precomputed_curves", {})
        if cache_key in precomputed:
            return precomputed[cache_key]

        # Check circuit-driver precomputed index
        cd_key = (circuit_id, driver_id, max_tyre_age)
        if not session_id and not stint_id and cd_key in precomputed:
            return precomputed[cd_key]

        df = self._get_laps_df()
        if df.empty:
            raise HTTPException(status_code=404, detail="No telemetry dataset loaded.")

        # Filter using indexed subsets if available
        mask = (df["circuit_id"] == circuit_id) & (df["driver_id"] == driver_id)
        if session_id:
            mask = mask & (df["session_id"] == session_id)
        if stint_id and "stint_id" in df.columns:
            mask = mask & (df["stint_id"] == stint_id)

        subset = df[mask].copy()
        if len(subset) == 0:
            subset = df[(df["circuit_id"] == circuit_id)].copy()
            if len(subset) > 0:
                driver_id = str(subset["driver_id"].iloc[0])
                subset = subset[subset["driver_id"] == driver_id].copy()

        if len(subset) == 0:
            raise HTTPException(
                status_code=404,
                detail=f"No telemetry found for circuit='{circuit_id}', driver='{driver_id}'",
            )

        compound = str(subset["compound"].iloc[0]) if "compound" in subset.columns else "MEDIUM"
        sess = str(subset["session_id"].iloc[0]) if "session_id" in subset.columns else "R"
        st_id = str(subset["stint_id"].iloc[0]) if "stint_id" in subset.columns else "stint_1"

        curve = self.curve_generator.generate_curve(
            stint_df=subset,
            driver_id=driver_id,
            stint_id=st_id,
            circuit_id=circuit_id,
            session_id=sess,
            compound=compound,
            max_tyre_age=max_tyre_age,
        )

        res_dict = curve.to_dict()
        if "precomputed_curves" not in self.app_data:
            self.app_data["precomputed_curves"] = {}
        self.app_data["precomputed_curves"][cache_key] = res_dict
        return res_dict

    def get_ablation_study(self, dataset_name: str = "2024_2025_Telemetry") -> Dict[str, Any]:
        """
        Returns the 8-model ablation study (cached or computed).
        """
        if self.app_data.get("precomputed_ablation") is not None:
            return self.app_data["precomputed_ablation"]

        df = self._get_laps_df()
        report = self.ablation_suite.run_ablation(df, dataset_name=dataset_name)
        rep_dict = report.to_dict()
        self.app_data["precomputed_ablation"] = rep_dict
        return rep_dict

    def get_post_race_validation(
        self,
        circuit_id: Optional[str] = None,
        horizons: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates predicted degradation vs actual race-day pace across horizons.
        """
        if not circuit_id and (horizons is None or horizons == [5, 10, 15]) and self.app_data.get("precomputed_post_race_validation") is not None:
            return self.app_data["precomputed_post_race_validation"]

        # Check reports file directly if available
        val_file = os.path.join(BASE_DIR, "reports", "post_race_validation_plus15.json")
        if not circuit_id and os.path.exists(val_file):
            import json
            with open(val_file, "r") as f:
                data = json.load(f)
                self.app_data["precomputed_post_race_validation"] = data
                return data

        df = self._get_laps_df()
        if circuit_id:
            df = df[df["circuit_id"] == circuit_id].copy()

        h_list = horizons or [5, 10, 15]
        report = self.post_race_validator.run_validation_suite(
            df,
            horizons=h_list,
            dataset_name=f"Telemetry_{circuit_id or 'All_Circuits'}",
        )
        return report.to_dict()

    def get_confounder_breakdown(
        self,
        circuit_id: str = "silverstone",
        driver_id: str = "HAM",
    ) -> Dict[str, Any]:
        """
        Provides detailed lap-by-lap observable confounder decomposition.
        """
        curve_data = self.get_estimated_degradation_curve(circuit_id=circuit_id, driver_id=driver_id)
        return {
            "circuit_id": circuit_id,
            "driver_id": driver_id,
            "points": curve_data["points"],
            "summary": curve_data["summary"],
            "provenance_metadata": curve_data["provenance_metadata"],
        }
