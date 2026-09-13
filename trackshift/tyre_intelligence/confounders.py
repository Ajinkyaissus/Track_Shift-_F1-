"""
TrackShift — Observable Confounder Extraction & Modeling
========================================================
Extracts and computes:
1. Observable Track-Evolution Proxy (field median pace evolution up to lap N)
2. Observable Traffic Context Score (green flag status, lockup rate, delta variance)
3. Observable Load / Fuel Proxy (session burn-off proxy / stint progression)
4. Behavioral Contextual Overlay (validated Stage 3 TCN signals)

Strict temporal causality: Information timestamp <= lap N.

Scientific hardening (2026-09):
- track_evolution_proxy absent → uses 0.0 + source="unavailable".
  NEVER falls back to lap_number (which is a race-lap counter, not grip evolution).
- All coefficients imported from trackshift.domain_constants (one source).
- compute_total_confounder_delta now returns track_evolution_source in output.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
import logging
import numpy as np
import pandas as pd

from trackshift.domain_constants import (
    FUEL_EFFECT_COEFFICIENT,
    TRACK_EVOLUTION_COEFFICIENT,
    TRAFFIC_EFFECT_COEFFICIENT,
)

logger = logging.getLogger("trackshift.tyre_intelligence.confounders")

# Track evolution source labels
TRACK_EVO_SOURCE_DATASET = "dataset_field"
TRACK_EVO_SOURCE_UNAVAILABLE = "unavailable"


@dataclass
class ConfounderContext:
    """Observable contextual factors for a single lap observation."""
    lap_number: int
    fuel_load_est: float
    grip_evolution_proxy: float
    grip_evolution_source: str      # provenance: "dataset_field" | "unavailable"
    traffic_density_proxy: float
    braking_aggression: float = 0.5
    throttle_transient_smoothness: float = 0.5
    lateral_dynamics_proxy: float = 0.5
    kerb_usage: float = 0.0
    lockup_flag_rate: float = 0.0
    is_green_flag: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lap_number": self.lap_number,
            "fuel_load_est": round(float(self.fuel_load_est), 2),
            "grip_evolution_proxy": round(float(self.grip_evolution_proxy), 4),
            "grip_evolution_source": self.grip_evolution_source,
            "traffic_density_proxy": round(float(self.traffic_density_proxy), 4),
            "braking_aggression": round(float(self.braking_aggression), 4),
            "throttle_transient_smoothness": round(float(self.throttle_transient_smoothness), 4),
            "lateral_dynamics_proxy": round(float(self.lateral_dynamics_proxy), 4),
            "kerb_usage": round(float(self.kerb_usage), 2),
            "lockup_flag_rate": round(float(self.lockup_flag_rate), 4),
            "is_green_flag": self.is_green_flag,
        }


class ObservableConfounderEstimator:
    """Computes observable confounder adjustments."""

    def __init__(
        self,
        fuel_coef: float = FUEL_EFFECT_COEFFICIENT,
        evolution_coef: float = TRACK_EVOLUTION_COEFFICIENT,
        traffic_coef: float = TRAFFIC_EFFECT_COEFFICIENT,
    ):
        self.fuel_coef = fuel_coef
        self.evolution_coef = evolution_coef
        self.traffic_coef = traffic_coef

    def extract_context(self, row_dict: Dict[str, Any]) -> ConfounderContext:
        """
        Extracts ConfounderContext dataclass from a raw telemetry row.

        Track evolution provenance
        --------------------------
        If 'track_evolution_proxy' is present in row_dict: use it (source = "dataset_field").
        If absent: use 0.0 (source = "unavailable").
        NEVER use lap_number as a substitute for track grip evolution.
        """
        lap_num = int(row_dict.get("lap_number", 1))

        # Fuel load
        fuel_est = row_dict.get("fuel_load_est")
        if fuel_est is None or (isinstance(fuel_est, float) and np.isnan(float(fuel_est))):
            fuel_val = max(5.0, 105.0 - (lap_num * 1.7))
        else:
            fuel_val = float(fuel_est)

        # P0 FIX: Track evolution proxy — NEVER fallback to lap_number.
        # lap_number is a race lap counter; it is NOT equivalent to grip evolution.
        raw_te = row_dict.get("track_evolution_proxy")
        if raw_te is not None and not (isinstance(raw_te, float) and np.isnan(float(raw_te))):
            grip_evo = float(raw_te)
            grip_evo_source = TRACK_EVO_SOURCE_DATASET
        else:
            grip_evo = 0.0
            grip_evo_source = TRACK_EVO_SOURCE_UNAVAILABLE

        # Traffic proxy
        is_green = bool(row_dict.get("is_green_flag", True))
        lockup = float(row_dict.get("lockup_flag_rate", 0.0) or 0.0)
        traffic_val = 0.0 if is_green else 1.0
        traffic_val += min(0.5, lockup * 1.5)

        return ConfounderContext(
            lap_number=lap_num,
            fuel_load_est=fuel_val,
            grip_evolution_proxy=grip_evo,
            grip_evolution_source=grip_evo_source,
            traffic_density_proxy=traffic_val,
            braking_aggression=float(row_dict.get("braking_aggression", 0.5) or 0.5),
            throttle_transient_smoothness=float(row_dict.get("throttle_transient_smoothness", 0.5) or 0.5),
            lateral_dynamics_proxy=float(row_dict.get("lateral_dynamics_proxy", 0.5) or 0.5),
            kerb_usage=float(row_dict.get("kerb_usage", 0.0) or 0.0),
            lockup_flag_rate=lockup,
            is_green_flag=is_green,
        )

    def compute_fuel_adjustment(self, fuel_load_est: float) -> float:
        """Pace penalty relative to empty car (seconds). Uses FUEL_EFFECT_COEFFICIENT = 0.033 s/kg."""
        return float(max(0.0, fuel_load_est) * self.fuel_coef)

    def compute_track_evolution_adjustment(self, grip_evolution_proxy: float) -> float:
        """Grip gain effect (negative seconds, reducing lap times)."""
        return float(np.clip(grip_evolution_proxy * self.evolution_coef, -2.5, 0.5))

    def compute_traffic_adjustment(self, traffic_density_proxy: float) -> float:
        """Traffic loss penalty (positive seconds)."""
        return float(np.clip(traffic_density_proxy * self.traffic_coef, 0.0, 3.0))

    def compute_total_confounder_delta(self, context: ConfounderContext) -> Dict[str, Any]:
        """
        Calculates total observable confounding delta.

        Returns dict including provenance fields:
          track_evolution_source: "dataset_field" | "unavailable"
        """
        fuel_adj = self.compute_fuel_adjustment(context.fuel_load_est)
        track_adj = self.compute_track_evolution_adjustment(context.grip_evolution_proxy)
        traffic_adj = self.compute_traffic_adjustment(context.traffic_density_proxy)

        total_delta = fuel_adj + track_adj + traffic_adj
        return {
            "fuel_delta": fuel_adj,
            "track_evolution_delta": track_adj,
            "track_evolution_source": context.grip_evolution_source,
            "traffic_delta": traffic_adj,
            "total_confounder_adjustment": total_delta,
        }


# ---------------------------------------------------------------------------
# Legacy functional helpers — backward compatibility
# ---------------------------------------------------------------------------

def compute_track_evolution_proxy(
    session_laps_df: pd.DataFrame,
    current_lap: int,
    lookback_window: int = 5
) -> float:
    """
    Computes track evolution proxy from field-wide green-flag lap time progression.

    Uses strictly past information (laps <= current_lap).
    Returns a session-derived evolution estimate in seconds.
    This function is valid for computing the track_evolution_proxy feature value;
    it is NOT used as a fallback when the field is absent (see ObservableConfounderEstimator).
    """
    if session_laps_df is None or session_laps_df.empty:
        return -0.015 * min(current_lap, 35)

    past_laps = session_laps_df[session_laps_df["lap_number"] <= current_lap]
    clean_past = past_laps[past_laps["is_green_flag"] == 1]

    if len(clean_past) < 10:
        return -0.015 * min(current_lap, 35)

    early_laps = clean_past[clean_past["lap_number"] <= min(5, current_lap)]["lap_time"]
    early_median = float(early_laps.median()) if len(early_laps) > 0 else float(clean_past["lap_time"].median())

    start_recent = max(1, current_lap - lookback_window + 1)
    recent_laps = clean_past[
        (clean_past["lap_number"] >= start_recent) & (clean_past["lap_number"] <= current_lap)
    ]["lap_time"]

    if len(recent_laps) > 0:
        recent_median = float(recent_laps.median())
        evolution_sec = recent_median - early_median
        return float(np.clip(evolution_sec, -2.5, 1.0))
    else:
        return -0.015 * min(current_lap, 35)


def compute_traffic_context_score(
    lap_record: Dict[str, Any],
    recent_laps: Optional[List[float]] = None
) -> Dict[str, Any]:
    """Computes composite traffic context score from available lap signals."""
    is_green = lap_record.get("is_green_flag", 1)
    lockup = lap_record.get("lockup_flag_rate", 0.0)

    flag_penalty = 1.0 if is_green == 0 else 0.0
    lockup_penalty = float(np.clip(lockup * 2.0, 0.0, 0.4))

    if recent_laps and len(recent_laps) >= 3:
        var = float(np.var(recent_laps))
        var_penalty = float(np.clip(var / 2.0, 0.0, 0.4))
    else:
        var_penalty = 0.0

    composite_score = float(
        np.clip((0.50 * flag_penalty) + (0.25 * lockup_penalty) + (0.25 * var_penalty), 0.0, 1.0)
    )

    if composite_score >= 0.65:
        category = "HIGH_TRAFFIC"
        desc = "Substantial pace distortion from non-green flag or heavy traffic disturbance."
    elif composite_score >= 0.30:
        category = "MODERATE_TRAFFIC"
        desc = "Minor pace interruption from lockups or localized dirty air."
    else:
        category = "CLEAN_AIR"
        desc = "Clean racing corridor with low external pace disturbance."

    return {
        "traffic_score": round(composite_score, 3),
        "traffic_category": category,
        "traffic_description": desc,
        "is_green_flag": bool(is_green),
        "lockup_rate": round(lockup, 3),
    }


def compute_load_fuel_proxy(
    fuel_load_est: Optional[float] = None,
    lap_number: int = 1,
    total_laps: int = 55,
    fuel_effect_sec_per_kg: float = FUEL_EFFECT_COEFFICIENT,  # FIX: was 0.035 hardcoded
) -> Dict[str, Any]:
    """
    Computes fuel/load proxy adjustment.

    Uses canonical FUEL_EFFECT_COEFFICIENT = 0.033 s/kg (not 0.035 legacy default).
    """
    if fuel_load_est is not None and not np.isnan(fuel_load_est):
        fuel_kg = float(fuel_load_est)
    else:
        fuel_kg = max(10.0, 110.0 - (1.75 * lap_number))

    fuel_delta_sec = fuel_kg * fuel_effect_sec_per_kg

    return {
        "estimated_fuel_load_kg": round(fuel_kg, 1),
        "fuel_lap_time_delta_sec": round(fuel_delta_sec, 3),
        "fuel_effect_coefficient": fuel_effect_sec_per_kg,
        "nomenclature": "Observable Load / Fuel Proxy (kg equivalent)",
    }
