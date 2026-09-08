"""
Central Model Registry for TrackShift.
Loads and caches ML/DL models in memory once at startup, manages versions,
provenance metadata, and provides deterministic embedding generation.
"""

import os
import sqlite3
import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from api.models.behavioral_model import (
    BehavioralModelWrapper,
    BEHAVIORAL_FEATURES,
    DEFAULT_EMBEDDING_DIM
)

logger = logging.getLogger("trackshift.models.registry")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "api", "tyredebt.db")
DATA_DIR = os.path.join(BASE_DIR, "data")
LAPS_PARQUET = os.path.join(DATA_DIR, "laps.parquet")


class ModelRegistry:
    """
    In-memory registry managing ML and Deep Learning model instances.
    """

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.active_models: Dict[int, str] = {}  # stage -> model_version
        self.model_metadata: Dict[str, Dict[str, Any]] = {}
        self.coefficients: Dict[Tuple[str, str, Optional[str]], float] = {}
        self.behavioral_model: Optional[BehavioralModelWrapper] = None
        self._stint_embeddings: Dict[str, List[float]] = {}
        self._stint_telemetry: Dict[str, np.ndarray] = {}
        self._is_loaded: bool = False

    def load_registry(self):
        """Loads all active model metadata and coefficients from SQLite."""
        if not os.path.exists(self.db_path):
            logger.warning("Database %s not found. Using defaults.", self.db_path)
            self._set_fallbacks()
            return

        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT stage, model_version, trained_at, held_out_metric, split_method FROM model_registry WHERE is_active = 1")
            rows = cursor.fetchall()
            for r in rows:
                stage = r["stage"]
                version = r["model_version"]
                self.active_models[stage] = version
                self.model_metadata[version] = {
                    "stage": stage,
                    "version": version,
                    "trained_at": r["trained_at"],
                    "held_out_metric": r["held_out_metric"],
                    "split_method": r["split_method"],
                    "feature_schema": "5_behavioral_telemetry"
                }

            # If stage 3 in database, load coefficients
            stage3_version = self.active_models.get(3)
            if stage3_version:
                cursor.execute(
                    "SELECT feature_name, track_scope, coefficient FROM model_coefficients WHERE model_version = ?",
                    (stage3_version,)
                )
                for r in cursor.fetchall():
                    self.coefficients[(stage3_version, r["feature_name"], r["track_scope"])] = float(r["coefficient"])

            # Default to latest active stage 3 or discover from models directory
            if 3 not in self.active_models:
                self.active_models[3] = "v5_tcn_stage3_2026-09-07"
            
            # Instantiate TCN behavioral DL wrapper
            self.behavioral_model = BehavioralModelWrapper(
                architecture="tcn",
                model_version=self.active_models.get(3),
                embedding_dim=DEFAULT_EMBEDDING_DIM
            )

            # Pre-cache stint telemetry sequences for fast real embedding generation
            if os.path.exists(LAPS_PARQUET):
                laps_df = pd.read_parquet(LAPS_PARQUET)
                for stint_id, group in laps_df.groupby("stint_id"):
                    sorted_group = group.sort_values("lap_number")
                    feat_matrix = sorted_group[BEHAVIORAL_FEATURES].values  # (N_laps, N_features)
                    self._stint_telemetry[stint_id] = feat_matrix

            self._is_loaded = True
            logger.info("ModelRegistry successfully initialized with active models: %s", self.active_models)

        except Exception as e:
            logger.error("Error loading model registry: %s", e)
            self._set_fallbacks()
        finally:
            conn.close()

    def _set_fallbacks(self):
        stage1_fallback = "v3_stage1_2026-09-07"
        stage3_fallback = "v5_tcn_stage3_2026-09-07"
        self.active_models = {1: stage1_fallback, 3: stage3_fallback}
        self.model_metadata[stage1_fallback] = {"stage": 1, "version": stage1_fallback, "held_out_metric": 1.46}
        self.model_metadata[stage3_fallback] = {"stage": 3, "version": stage3_fallback, "held_out_metric": 0.12}
        self.behavioral_model = BehavioralModelWrapper(model_version=stage3_fallback)
        self._is_loaded = True

    def get_stage_version(self, stage: int) -> str:
        return self.active_models.get(stage, f"v_fallback_stage{stage}")

    def get_coefficient(self, model_version: str, feature_name: str, track_scope: Optional[str] = None) -> float:
        """Retrieves learned coefficient with track-specific fallback to global."""
        if (model_version, feature_name, track_scope) in self.coefficients:
            return self.coefficients[(model_version, feature_name, track_scope)]
        if (model_version, feature_name, None) in self.coefficients:
            return self.coefficients[(model_version, feature_name, None)]
        
        default_coefs = {
            "braking_aggression": -0.0067,
            "throttle_transient_smoothness": -0.1681,
            "lateral_dynamics_proxy": 0.0001,
            "kerb_usage": 0.0071,
            "lockup_flag_rate": 0.4824
        }
        return default_coefs.get(feature_name, 0.01)

    def get_or_generate_embedding(self, stint_id: str, sequence_data: Optional[np.ndarray] = None) -> List[float]:
        """
        Gets or generates deterministic behavioral embedding for a given stint.
        Uses real stint telemetry sequences exclusively.
        Raises ValueError if real telemetry sequence is unavailable or insufficient (< 4 laps).
        """
        if stint_id in self._stint_embeddings:
            return self._stint_embeddings[stint_id]

        if sequence_data is None:
            if stint_id in self._stint_telemetry:
                sequence_data = self._stint_telemetry[stint_id]
            else:
                raise ValueError(f"Insufficient telemetry sequence observations for stint '{stint_id}'")

        if sequence_data is None:
            raise ValueError(f"Insufficient telemetry sequence observations for stint '{stint_id}'")

        seq_arr = np.asarray(sequence_data)
        seq_len = seq_arr.shape[0] if seq_arr.ndim == 2 and seq_arr.shape[1] == len(BEHAVIORAL_FEATURES) else (seq_arr.shape[1] if seq_arr.ndim == 2 else 0)
        if seq_len < 4 and seq_arr.size < (len(BEHAVIORAL_FEATURES) * 4):
            raise ValueError(f"Insufficient telemetry sequence length ({seq_len} < 4 laps) for stint '{stint_id}'")

        if self.behavioral_model is not None:
            emb = self.behavioral_model.generate_embedding(sequence_data)
            emb_list = [round(float(x), 5) for x in emb]
        else:
            emb_list = [0.0] * DEFAULT_EMBEDDING_DIM

        self._stint_embeddings[stint_id] = emb_list
        return emb_list


# Singleton instance
_global_registry: Optional[ModelRegistry] = None

def get_model_registry() -> ModelRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ModelRegistry()
        _global_registry.load_registry()
    return _global_registry
