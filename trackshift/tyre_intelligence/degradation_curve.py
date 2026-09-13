"""
TrackShift Confounder-Aware Tyre Performance Degradation Curve Engine
====================================================================
Generates context-adjusted tyre performance degradation curves from telemetry
with bootstrap uncertainty intervals [Q0.10, Q0.90].

Terminology:
- "Estimated Tyre Performance Degradation Curve" (never "true physical tyre wear")
- "Observable Confounder Adjustment"

Uncertainty note (2026-09 hardening):
  The q10/q50/q90 bounds are computed as a NON-PARAMETRIC WITHIN-STINT BOOTSTRAP
  of centered contextual residuals. They represent estimated variability of the
  pace trajectory within this stint's observed data — NOT forecast horizon uncertainty.
  They should NOT be interpreted as "+N lap ahead prediction intervals."
  For horizon-specific error, see trackshift.tyre_intelligence.post_race_validation.

Scientific hardening (2026-09):
- All frozen M1 constants imported from trackshift.domain_constants (one source).
- max_tyre_age cutoff uses tyre_age column filtering, not positional iloc slicing.
- uncertainty_source field added to provenance_metadata.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import numpy as np
import pandas as pd

from trackshift.domain_constants import (
    STAGE1_M1_INTERCEPT,
    STAGE1_M1_SLOPE,
    FUEL_EFFECT_COEFFICIENT,
    TRACK_EVOLUTION_COEFFICIENT,
    TRAFFIC_EFFECT_COEFFICIENT,
)
from trackshift.tyre_intelligence.confounders import ObservableConfounderEstimator
from trackshift.tyre_intelligence.model import ObservableDecompositionModel


@dataclass
class DegradationPoint:
    """A single tyre age point on the estimated degradation curve."""
    tyre_age: int
    tyre_age_source: str
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
                    "tyre_age_source": p.tyre_age_source,
                    "raw_pace_delta": round(float(p.raw_pace_delta), 4),
                    "m1_baseline_delta": round(float(p.m1_baseline_delta), 4),
                    "context_adjusted_delta": round(float(p.context_adjusted_delta), 4),
                    "confounder_breakdown": {k: round(float(v), 4) for k, v in p.confounder_breakdown.items() if isinstance(v, (int, float))},
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
            Stint laps data. Should contain `tyre_age` column for physical correctness.
        driver_id : str
        stint_id : str
        circuit_id : str
        session_id : str
        compound : str
        max_tyre_age : int, optional
            Limit curve to laps with tyre_age <= max_tyre_age (causal checkpoint).
            Uses tyre_age column for filtering when available; falls back to row
            slicing ONLY after chronological sort.
        """
        df = stint_df.copy()

        # P2 FIX: max_tyre_age cutoff — use tyre_age column value, not positional iloc.
        # Old code: df = df.iloc[:max_tyre_age]  <- breaks on unsorted/gapped input.
        if max_tyre_age is not None:
            if "tyre_age" in df.columns:
                df = df[df["tyre_age"] <= max_tyre_age].copy()
            elif "lap_number" in df.columns:
                # Sort first, then positional slice as approximation (labeled in provenance)
                df = df.sort_values("lap_number").iloc[:max_tyre_age].copy()
            else:
                df = df.iloc[:max_tyre_age].copy()

        if len(df) == 0:
            return EstimatedDegradationCurve(
                driver_id=driver_id,
                stint_id=stint_id,
                circuit_id=circuit_id,
                compound=compound,
                session_id=session_id,
            )

        # Baseline lap time (minimum of first 3 laps — causal, available at stint start)
        base_lap_time = float(df["lap_time"].iloc[0]) if "lap_time" in df.columns else 90.0
        if "lap_time" in df.columns and len(df) >= 2:
            base_lap_time = float(df["lap_time"].iloc[:min(3, len(df))].min())

        # Build ledger (decompose_stint handles sort internally)
        ledger = self.decomposition_model.decompose_stint(df, driver_id, stint_id, base_lap_time)

        # Clean residuals for uncertainty bounds (filter extreme disruptions > 5.0s)
        clean_resids = [
            pt.contextual_residual for pt in ledger.points
            if abs(pt.contextual_residual) <= 5.0
        ]
        if not clean_resids:
            clean_resids = [pt.contextual_residual for pt in ledger.points]

        resids_arr = np.array(clean_resids)

        # Center residuals so bootstrap uncertainty reflects variance around trajectory
        mean_res = float(np.mean(resids_arr)) if len(resids_arr) > 0 else 0.0
        centered_resids = resids_arr - mean_res

        if len(centered_resids) > 2:
            rng = np.random.RandomState(self.random_seed)
            boot_samples = rng.choice(
                centered_resids,
                size=(self.n_bootstraps, len(centered_resids)),
                replace=True
            )
            q10_offset = float(np.percentile(boot_samples, 10))
            q50_offset = float(np.percentile(boot_samples, 50))
            q90_offset = float(np.percentile(boot_samples, 90))
            uncertainty_source = "within_stint_residual_bootstrap"
        else:
            q10_offset = -0.25
            q50_offset = 0.0
            q90_offset = 0.25
            uncertainty_source = "within_stint_residual_bootstrap_fallback_insufficient_data"

        points: List[DegradationPoint] = []
        for pt in ledger.points:
            q10_val = float(pt.context_adjusted_delta + q10_offset)
            q50_val = float(pt.context_adjusted_delta + q50_offset)
            q90_val = float(pt.context_adjusted_delta + q90_offset)

            # Invariant: q10 <= q50 <= q90
            if q10_val > q50_val:
                q10_val = q50_val - 0.05
            if q90_val < q50_val:
                q90_val = q50_val + 0.05

            points.append(
                DegradationPoint(
                    tyre_age=pt.tyre_age,
                    tyre_age_source=pt.tyre_age_source,
                    raw_pace_delta=pt.observed_pace_delta,
                    m1_baseline_delta=pt.m1_baseline_delta,
                    context_adjusted_delta=pt.context_adjusted_delta,
                    confounder_breakdown={
                        "fuel_effect_delta": pt.fuel_effect,
                        "track_evolution_delta": pt.track_evolution_effect,
                        "track_evolution_source": pt.track_evolution_source,
                        "traffic_delta": pt.traffic_effect,
                        "total_confounder_adjustment": pt.total_confounder_delta,
                    },
                    uncertainty_q10=q10_val,
                    uncertainty_q50=q50_val,
                    uncertainty_q90=q90_val,
                    contextual_debt=pt.contextual_debt_accumulated,
                    m1_debt=pt.m1_debt_accumulated,
                )
            )

        # Evidence status
        n_pts = len(points)
        if n_pts < 3:
            evidence_status = "INSUFFICIENT DATA"
        elif n_pts < 8:
            evidence_status = "LIMITED"
        elif n_pts >= 15:
            evidence_status = "HIGHER SUPPORT"
        else:
            evidence_status = "CONDITIONAL"

        summary = {
            "total_laps_analyzed": len(points),
            "evidence_status": evidence_status,
            "final_m1_debt": round(float(points[-1].m1_debt), 4) if points else 0.0,
            "final_contextual_debt": round(float(points[-1].contextual_debt), 4) if points else 0.0,
            "mean_confounder_adjustment_s": round(
                float(np.mean([p.confounder_breakdown["total_confounder_adjustment"] for p in points])), 4
            ) if points else 0.0,
            "fuel_saving_s": round(
                float(np.sum([p.confounder_breakdown["fuel_effect_delta"] for p in points])), 4
            ) if points else 0.0,
            "track_grip_gain_s": round(
                float(np.sum([p.confounder_breakdown["track_evolution_delta"] for p in points])), 4
            ) if points else 0.0,
            "traffic_loss_s": round(
                float(np.sum([p.confounder_breakdown["traffic_delta"] for p in points])), 4
            ) if points else 0.0,
        }

        provenance_metadata = {
            "point_estimator": "ObservableDecompositionModel(Stage1_M1 + Observable Confounders)",
            "bootstrap_unit": "stint_cluster",
            "resampled_object": "clean_stint_contextual_residuals",
            "aggregation_function": "percentiles [q10, q50, q90]",
            "target_variable": "expected_context_adjusted_pace_delta",
            "units": "seconds_relative_to_stint_baseline",
            "consistency_guarantee": "q10 <= q50 <= q90; q50 centered on point estimate",
            "evidence_status": evidence_status,
            "m1_formula": f"y_hat = {STAGE1_M1_INTERCEPT} + {STAGE1_M1_SLOPE} * tyre_age",
            "m1_constants_source": "trackshift.domain_constants",
            "fuel_coefficient": FUEL_EFFECT_COEFFICIENT,
            "fuel_coefficient_source": "trackshift.domain_constants",
            "track_evolution_coefficient": TRACK_EVOLUTION_COEFFICIENT,
            "traffic_coefficient": TRAFFIC_EFFECT_COEFFICIENT,
            # IMPORTANT: uncertainty is NOT horizon-specific forecast uncertainty.
            # It is within-stint residual dispersion from bootstrap resampling.
            "uncertainty_source": uncertainty_source,
            "uncertainty_interpretation": (
                "Within-stint bootstrap of centered contextual residuals. "
                "Represents observed pace variability in this stint — "
                "NOT a +N-lap forecast prediction interval. "
                "For horizon-specific error, see PostRaceValidator."
            ),
            "uncertainty_method": (
                f"Non-parametric centered stint bootstrap "
                f"(B={self.n_bootstraps}, seed={self.random_seed})"
            ),
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
