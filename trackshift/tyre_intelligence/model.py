"""
TrackShift — Confounder-Aware Tyre Performance Analysis Model
=============================================================
Combines the frozen Stage 1 Linear Tyre Age Baseline with observable
contextual adjustments (Track Evolution, Traffic Context, Load/Fuel Proxy,
and Validated Stage 3 Behavioral Heads).

Formulation:
  expected_contextual_loss = Stage1_M1(tyre_age) + contextual_adjustment
  contextual_residual = observed_loss - expected_contextual_loss
  contextual_debt_increment = max(0, contextual_residual)
  cumulative_contextual_debt = sum(contextual_debt_increment)

Strictly non-causal terminology:
- 'Observable Confounder Adjustment'
- 'Context-Aware Tyre-Performance Estimation'
- 'Contextual Residual Deviation'
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import numpy as np
import pandas as pd

from trackshift.strategy.debt_liquidation import stage1_m1_loss
from trackshift.tyre_intelligence.confounders import (
    ObservableConfounderEstimator,
    ConfounderContext,
    compute_track_evolution_proxy,
    compute_traffic_context_score,
    compute_load_fuel_proxy,
    FUEL_EFFECT_COEFFICIENT,
    TRACK_EVOLUTION_COEFFICIENT,
    TRAFFIC_EFFECT_COEFFICIENT,
)

# Frozen Stage 1 M1 Baseline Constants
STAGE1_M1_INTERCEPT: float = 0.1974
STAGE1_M1_SLOPE: float = 0.0400

# Explicit Contextual Regression Coefficients (Fitted on Train Split)
CONTEXT_COEFFICIENTS = {
    "fuel_load_kg_slope": -0.018,       # Lap time loss increases as fuel burns off
    "track_evolution_coef": 0.35,      # Sensitivity to track rubbering in
    "traffic_penalty_scale": 0.45,      # Direct time loss per unit traffic score
    "braking_aggression_scale": 0.008,  # Micro-wear / thermal surge per unit decel
    "lateral_dynamics_scale": 0.12,     # Tyre lateral load friction offset
    "anomaly_penalty_scale": 0.25       # Performance cost per unit behavioral anomaly
}


@dataclass
class DecompositionPoint:
    """Single lap point for observable confounder decomposition."""
    lap_number: int
    tyre_age: int
    observed_lap_time: float
    observed_pace_delta: float
    m1_baseline_delta: float
    context_adjusted_delta: float
    fuel_effect: float
    track_evolution_effect: float
    traffic_effect: float
    total_confounder_delta: float
    m1_residual: float
    contextual_residual: float
    m1_debt_accumulated: float
    contextual_debt_accumulated: float


@dataclass
class ContextualResidualLedger:
    """Ledger of decomposed stint points."""
    driver_id: str
    stint_id: str
    points: List[DecompositionPoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "driver_id": self.driver_id,
            "stint_id": self.stint_id,
            "total_laps": len(self.points),
            "points": [
                {
                    "lap_number": p.lap_number,
                    "tyre_age": p.tyre_age,
                    "observed_lap_time": round(float(p.observed_lap_time), 3),
                    "observed_pace_delta": round(float(p.observed_pace_delta), 3),
                    "m1_baseline_delta": round(float(p.m1_baseline_delta), 3),
                    "context_adjusted_delta": round(float(p.context_adjusted_delta), 3),
                    "total_confounder_delta": round(float(p.total_confounder_delta), 3),
                    "contextual_residual": round(float(p.contextual_residual), 3),
                    "contextual_debt_accumulated": round(float(p.contextual_debt_accumulated), 3),
                    "m1_debt_accumulated": round(float(p.m1_debt_accumulated), 3),
                }
                for p in self.points
            ]
        }


class ObservableDecompositionModel:
    """
    Decomposes raw stint telemetry into Stage 1 M1 baseline, observable
    confounder adjustments, and contextual residuals.
    """

    def __init__(self, confounder_estimator: Optional[ObservableConfounderEstimator] = None):
        self.confounders = confounder_estimator or ObservableConfounderEstimator()

    def decompose_stint(
        self,
        stint_df: pd.DataFrame,
        driver_id: str,
        stint_id: str,
        base_lap_time: float,
    ) -> ContextualResidualLedger:
        points: List[DecompositionPoint] = []
        cum_m1_debt = 0.0
        cum_context_debt = 0.0

        for idx, (_, row) in enumerate(stint_df.iterrows()):
            lap_num = int(row.get("lap_number", idx + 1))
            age = idx + 1
            raw_time = float(row.get("lap_time", base_lap_time))
            observed_delta = raw_time - base_lap_time

            # Stage 1 M1 linear baseline delta
            m1_delta = STAGE1_M1_INTERCEPT + STAGE1_M1_SLOPE * age

            # Extract observable confounders
            ctx = self.confounders.extract_context(row.to_dict())
            conf_breakdown = self.confounders.compute_total_confounder_delta(ctx)

            fuel_eff = conf_breakdown["fuel_delta"]
            track_eff = conf_breakdown["track_evolution_delta"]
            traf_eff = conf_breakdown["traffic_delta"]
            tot_conf = conf_breakdown["total_confounder_adjustment"]

            # Expected contextual pace delta
            context_delta = m1_delta + tot_conf

            # Residuals
            m1_res = observed_delta - m1_delta
            context_res = observed_delta - context_delta

            cum_m1_debt += max(0.0, m1_res)
            cum_context_debt += max(0.0, context_res)

            points.append(
                DecompositionPoint(
                    lap_number=lap_num,
                    tyre_age=age,
                    observed_lap_time=raw_time,
                    observed_pace_delta=observed_delta,
                    m1_baseline_delta=m1_delta,
                    context_adjusted_delta=context_delta,
                    fuel_effect=fuel_eff,
                    track_evolution_effect=track_eff,
                    traffic_effect=traf_eff,
                    total_confounder_delta=tot_conf,
                    m1_residual=m1_res,
                    contextual_residual=context_res,
                    m1_debt_accumulated=cum_m1_debt,
                    contextual_debt_accumulated=cum_context_debt,
                )
            )

        return ContextualResidualLedger(
            driver_id=driver_id,
            stint_id=stint_id,
            points=points,
        )


def estimate_contextual_lap_performance(
    tyre_age: int,
    lap_number: int,
    total_laps: int = 55,
    fuel_load_est: Optional[float] = None,
    track_evolution_proxy_sec: float = 0.0,
    traffic_context_score: float = 0.0,
    braking_aggression: float = 50.0,
    lateral_dynamics_proxy: float = 0.20,
    stage3_anomaly_score: float = 0.0,
    stage3_drift_score: float = 0.0
) -> Dict[str, Any]:
    s1_loss = stage1_m1_loss(tyre_age)

    fuel_info = compute_load_fuel_proxy(fuel_load_est, lap_number, total_laps)
    fuel_kg = fuel_info["estimated_fuel_load_kg"]
    fuel_burn_kg = max(0.0, 110.0 - fuel_kg)
    fuel_comp = fuel_burn_kg * CONTEXT_COEFFICIENTS["fuel_load_kg_slope"]

    te_comp = track_evolution_proxy_sec * CONTEXT_COEFFICIENTS["track_evolution_coef"]
    traffic_comp = traffic_context_score * CONTEXT_COEFFICIENTS["traffic_penalty_scale"]

    brake_delta = max(0.0, braking_aggression - 48.0) * CONTEXT_COEFFICIENTS["braking_aggression_scale"]
    lateral_delta = max(0.0, lateral_dynamics_proxy - 0.15) * CONTEXT_COEFFICIENTS["lateral_dynamics_scale"]
    anomaly_delta = stage3_anomaly_score * CONTEXT_COEFFICIENTS["anomaly_penalty_scale"]

    behavioral_comp = brake_delta + lateral_delta + anomaly_delta
    total_context_adj = fuel_comp + te_comp + traffic_comp + behavioral_comp
    expected_context_loss = s1_loss + total_context_adj

    return {
        "tyre_age": tyre_age,
        "lap_number": lap_number,
        "baseline_stage1_loss_sec": round(s1_loss, 4),
        "contextual_adjustment_sec": round(total_context_adj, 4),
        "expected_contextual_loss_sec": round(expected_context_loss, 4),
        "component_breakdown": {
            "tyre_age_m1_sec": round(s1_loss, 4),
            "fuel_load_effect_sec": round(fuel_comp, 4),
            "track_evolution_effect_sec": round(te_comp, 4),
            "traffic_context_effect_sec": round(traffic_comp, 4),
            "behavioral_context_effect_sec": round(behavioral_comp, 4)
        },
        "scientific_nomenclature": "Context-Aware Tyre-Performance Estimation (Observable Confounder Adjustment)"
    }


def compute_stint_contextual_residuals(
    stint_laps: List[Dict[str, Any]],
    track_evolution_series: Optional[List[float]] = None
) -> Dict[str, Any]:
    lap_records = []
    cum_s1_debt = 0.0
    cum_context_debt = 0.0

    for idx, lap in enumerate(stint_laps):
        lap_num = lap.get("lap_number", idx + 1)
        age = lap.get("tyre_age", idx + 1)
        obs_loss = lap.get("actual_lap_time_loss", 0.0)
        fuel_est = lap.get("fuel_load_est", None)
        te = track_evolution_series[idx] if (track_evolution_series and idx < len(track_evolution_series)) else 0.0

        traffic_info = compute_traffic_context_score(lap)
        traf_score = traffic_info["traffic_score"]

        est = estimate_contextual_lap_performance(
            tyre_age=age,
            lap_number=lap_num,
            fuel_load_est=fuel_est,
            track_evolution_proxy_sec=te,
            traffic_context_score=traf_score,
            braking_aggression=lap.get("braking_aggression", 50.0),
            lateral_dynamics_proxy=lap.get("lateral_dynamics_proxy", 0.20),
            stage3_anomaly_score=lap.get("stage3_anomaly_score", 0.0),
            stage3_drift_score=lap.get("stage3_drift_score", 0.0)
        )

        s1_pred = est["baseline_stage1_loss_sec"]
        context_pred = est["expected_contextual_loss_sec"]

        s1_res = obs_loss - s1_pred
        s1_inc = max(0.0, s1_res)
        cum_s1_debt += s1_inc

        context_res = obs_loss - context_pred
        context_inc = max(0.0, context_res)
        cum_context_debt += context_inc

        lap_records.append({
            "lap_number": lap_num,
            "tyre_age": age,
            "observed_loss_sec": round(obs_loss, 4),
            "stage1_baseline_sec": round(s1_pred, 4),
            "contextual_expected_sec": round(context_pred, 4),
            "stage2_raw_residual_sec": round(s1_res, 4),
            "contextual_residual_sec": round(context_res, 4),
            "cumulative_stage2_debt_sec": round(cum_s1_debt, 4),
            "cumulative_context_debt_sec": round(cum_context_debt, 4),
            "confounder_breakdown": est["component_breakdown"],
            "traffic_info": traffic_info
        })

    return {
        "stint_laps_evaluated": len(lap_records),
        "total_stage2_debt_sec": round(cum_s1_debt, 4),
        "total_context_adjusted_debt_sec": round(cum_context_debt, 4),
        "lap_records": lap_records,
        "provenance": {
            "stage1_model": "Frozen M1 Linear Baseline",
            "contextual_model": "Confounder-Aware Observable Decomposition",
            "leakage_boundary": "Strictly chronological per-lap estimation"
        }
    }
