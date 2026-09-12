"""
TrackShift Confounder-Aware Tyre Performance Degradation Curve Engine
====================================================================
Generates context-adjusted tyre performance degradation curves from telemetry
with bootstrap uncertainty intervals [Q0.10, Q0.90].

Terminology:
- "Estimated Tyre Performance Degradation Curve" (never "true physical tyre wear")
- "Observable Confounder Adjustment"
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from trackshift.tyre_intelligence.confounders import (
    ObservableConfounderEstimator,
    ConfounderContext,
    FUEL_EFFECT_COEFFICIENT,
    TRACK_EVOLUTION_COEFFICIENT,
    TRAFFIC_EFFECT_COEFFICIENT,
)
from trackshift.tyre_intelligence.model import (
    ObservableDecompositionModel,
    ContextualResidualLedger,
    STAGE1_M1_INTERCEPT,
    STAGE1_M1_SLOPE,
)


@dataclass
class DegradationPoint:
    """A single tyre age point on the estimated degradation curve."""
    tyre_age: int
    raw_pace_delta: float
    m1_baseline_delta: float
    context_adjusted_delta: float
    confounder_breakdown: Dict[str, float]
    uncertainty_q10: float
    uncertainty_q50: float
    uncertainty_q90: float
    contextual_debt: float
    m1_debt: float


@dataclass
class EstimatedDegradationCurve:
    """Estimated Tyre Performance Degradation Curve for a stint/driver."""
    driver_id: str
    stint_id: str
    circuit_id: str
    compound: str
    session_id: str
    points: List[DegradationPoint] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    provenance_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "driver_id": self.driver_id,
            "stint_id": self.stint_id,
            "circuit_id": self.circuit_id,
            "compound": self.compound,
            "session_id": self.session_id,
            "points": [
                {
                    "tyre_age": p.tyre_age,
                    "raw_pace_delta": round(float(p.raw_pace_delta), 4),
                    "m1_baseline_delta": round(float(p.m1_baseline_delta), 4),
                    "context_adjusted_delta": round(float(p.context_adjusted_delta), 4),
                    "confounder_breakdown": {k: round(float(v), 4) for k, v in p.confounder_breakdown.items()},
                    "uncertainty_q10": round(float(p.uncertainty_q10), 4),
                    "uncertainty_q50": round(float(p.uncertainty_q50), 4),
                    "uncertainty_q90": round(float(p.uncertainty_q90), 4),
                    "contextual_debt": round(float(p.contextual_debt), 4),
                    "m1_debt": round(float(p.m1_debt), 4),
                }
                for p in self.points
            ],
            "summary": self.summary,
            "provenance_metadata": self.provenance_metadata,
        }


class TyreDegradationCurveGenerator:
    """
    Constructs context-adjusted tyre performance degradation curves using
    observable confounder stripping and bootstrap uncertainty estimation.
    """

    def __init__(
        self,
        confounder_estimator: Optional[ObservableConfounderEstimator] = None,
        decomposition_model: Optional[ObservableDecompositionModel] = None,
        n_bootstraps: int = 100,
        random_seed: int = 42,
    ):
        self.confounder_estimator = confounder_estimator or ObservableConfounderEstimator()
        self.decomposition_model = decomposition_model or ObservableDecompositionModel()
        self.n_bootstraps = n_bootstraps
        self.random_seed = random_seed

    def generate_curve(
        self,
        stint_df: pd.DataFrame,
        driver_id: str,
        stint_id: str,
        circuit_id: str = "unknown",
        session_id: str = "unknown",
        compound: str = "MEDIUM",
        max_tyre_age: Optional[int] = None,
    ) -> EstimatedDegradationCurve:
        """
        Generate estimated degradation curve for a given stint.

        Parameters
        ----------
        stint_df : pd.DataFrame
            Stint laps data (sorted by lap_number / tyre age).
        driver_id : str
            Driver code.
        stint_id : str
            Stint identifier.
        circuit_id : str
            Circuit key.
        session_id : str
            Session key.
        compound : str
            Tyre compound.
        max_tyre_age : int, optional
            Limit to lap age <= max_tyre_age (for causal checkpoint evaluation).
        """
        df = stint_df.copy()
        if max_tyre_age is not None and "lap_number" in df.columns:
            # Strictly causal cutoff
            df = df.iloc[:max_tyre_age].copy()

        if len(df) == 0:
            return EstimatedDegradationCurve(
                driver_id=driver_id,
                stint_id=stint_id,
                circuit_id=circuit_id,
                compound=compound,
                session_id=session_id,
            )

        # Baseline lap time (first clean push lap or minimum lap time in first 3 laps)
        base_lap_time = float(df["lap_time"].iloc[0]) if "lap_time" in df.columns else 90.0
        if "lap_time" in df.columns and len(df) >= 2:
            base_lap_time = float(df["lap_time"].iloc[:min(3, len(df))].min())

        # Build ledger
        ledger = self.decomposition_model.decompose_stint(df, driver_id, stint_id, base_lap_time)

        # Bootstrap residual noise for uncertainty bounds
        resids = np.array([pt.contextual_residual for pt in ledger.points])
        if len(resids) > 1:
            rng = np.random.RandomState(self.random_seed)
            boot_samples = rng.choice(resids, size=(self.n_bootstraps, len(resids)), replace=True)
            q10_res = np.percentile(boot_samples, 10, axis=0)
            q50_res = np.percentile(boot_samples, 50, axis=0)
            q90_res = np.percentile(boot_samples, 90, axis=0)
        else:
            q10_res = np.zeros(len(ledger.points)) - 0.15
            q50_res = np.zeros(len(ledger.points))
            q90_res = np.zeros(len(ledger.points)) + 0.15

        points: List[DegradationPoint] = []
        for i, pt in enumerate(ledger.points):
            points.append(
                DegradationPoint(
                    tyre_age=pt.tyre_age,
                    raw_pace_delta=pt.observed_pace_delta,
                    m1_baseline_delta=pt.m1_baseline_delta,
                    context_adjusted_delta=pt.context_adjusted_delta,
                    confounder_breakdown={
                        "fuel_effect_delta": pt.fuel_effect,
                        "track_evolution_delta": pt.track_evolution_effect,
                        "traffic_delta": pt.traffic_effect,
                        "total_confounder_adjustment": pt.total_confounder_delta,
                    },
                    uncertainty_q10=float(pt.context_adjusted_delta + q10_res[i]),
                    uncertainty_q50=float(pt.context_adjusted_delta + q50_res[i]),
                    uncertainty_q90=float(pt.context_adjusted_delta + q90_res[i]),
                    contextual_debt=pt.contextual_debt_accumulated,
                    m1_debt=pt.m1_debt_accumulated,
                )
            )

        summary = {
            "total_laps_analyzed": len(points),
            "final_m1_debt": round(float(points[-1].m1_debt), 4) if points else 0.0,
            "final_contextual_debt": round(float(points[-1].contextual_debt), 4) if points else 0.0,
            "mean_confounder_adjustment_s": round(float(np.mean([p.confounder_breakdown["total_confounder_adjustment"] for p in points])), 4) if points else 0.0,
            "fuel_saving_s": round(float(np.sum([p.confounder_breakdown["fuel_effect_delta"] for p in points])), 4) if points else 0.0,
            "track_grip_gain_s": round(float(np.sum([p.confounder_breakdown["track_evolution_delta"] for p in points])), 4) if points else 0.0,
            "traffic_loss_s": round(float(np.sum([p.confounder_breakdown["traffic_delta"] for p in points])), 4) if points else 0.0,
        }

        provenance_metadata = {
            "m1_formula": f"y_hat = {STAGE1_M1_INTERCEPT} + {STAGE1_M1_SLOPE} * tyre_age",
            "fuel_coefficient": FUEL_EFFECT_COEFFICIENT,
            "track_evolution_coefficient": TRACK_EVOLUTION_COEFFICIENT,
            "traffic_coefficient": TRAFFIC_EFFECT_COEFFICIENT,
            "uncertainty_method": f"Non-parametric bootstrap (B={self.n_bootstraps}, seed={self.random_seed})",
            "classification": "Observable Contextual Adjustment (Frozen Stage 1/Stage 2 Preserved)",
        }

        return EstimatedDegradationCurve(
            driver_id=driver_id,
            stint_id=stint_id,
            circuit_id=circuit_id,
            compound=compound,
            session_id=session_id,
            points=points,
            summary=summary,
            provenance_metadata=provenance_metadata,
        )
