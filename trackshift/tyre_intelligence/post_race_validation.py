"""
TrackShift Out-of-Sample Forward Predictive Multi-Horizon Validator
===================================================================
Evaluates predicted tyre degradation / pace against actual race-day pace.
Measures out-of-sample forward horizons (+1, +3, +5, +10 laps) strictly
from checkpoint lap N using historical telemetry.

Metrics:
- MAE (Mean Absolute Error, seconds)
- RMSE (Root Mean Squared Error, seconds)
- Spearman Rank Correlation (rho)
- Pearson Correlation (r)
- Compound & Session breakdown
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
import pandas as pd
from scipy import stats

from pipeline.model_stage1 import load_data
from trackshift.tyre_intelligence.degradation_curve import TyreDegradationCurveGenerator
from trackshift.tyre_intelligence.model import STAGE1_M1_INTERCEPT, STAGE1_M1_SLOPE


@dataclass
class HorizonEvaluation:
    """Evaluation result for a specific prediction horizon (e.g., +3 laps)."""
    horizon_laps: int
    n_samples: int
    m1_mae_s: float
    m1_rmse_s: float
    m1_spearman_rho: float
    m1_pearson_r: float
    context_mae_s: float
    context_rmse_s: float
    context_spearman_rho: float
    context_pearson_r: float
    mae_delta_s: float
    is_context_superior: bool


@dataclass
class PostRaceValidationReport:
    """Comprehensive Out-of-Sample Forward Predictive Validation Report."""
    dataset_name: str
    total_stints_evaluated: int
    total_laps_evaluated: int
    horizon_evaluations: List[HorizonEvaluation] = field(default_factory=list)
    compound_breakdown: Dict[str, Dict[str, float]] = field(default_factory=dict)
    summary_findings: Dict[str, Any] = field(default_factory=dict)
    scientific_classification: str = "Out-of-Sample Forward Predictive Multi-Horizon Validation"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_name": self.dataset_name,
            "total_stints_evaluated": self.total_stints_evaluated,
            "total_laps_evaluated": self.total_laps_evaluated,
            "scientific_classification": self.scientific_classification,
            "horizon_evaluations": [
                {
                    "horizon_laps": h.horizon_laps,
                    "n_samples": h.n_samples,
                    "m1_mae_s": round(float(h.m1_mae_s), 4),
                    "m1_rmse_s": round(float(h.m1_rmse_s), 4),
                    "m1_spearman_rho": round(float(h.m1_spearman_rho), 4) if not np.isnan(h.m1_spearman_rho) else 0.0,
                    "m1_pearson_r": round(float(h.m1_pearson_r), 4) if not np.isnan(h.m1_pearson_r) else 0.0,
                    "context_mae_s": round(float(h.context_mae_s), 4),
                    "context_rmse_s": round(float(h.context_rmse_s), 4),
                    "context_spearman_rho": round(float(h.context_spearman_rho), 4) if not np.isnan(h.context_spearman_rho) else 0.0,
                    "context_pearson_r": round(float(h.context_pearson_r), 4) if not np.isnan(h.context_pearson_r) else 0.0,
                    "mae_delta_s": round(float(h.mae_delta_s), 4),
                    "is_context_superior": h.is_context_superior,
                }
                for h in self.horizon_evaluations
            ],
            "compound_breakdown": self.compound_breakdown,
            "summary_findings": self.summary_findings,
        }


class PostRaceValidator:
    """
    Validates predicted tyre degradation against actual observed lap times
    using out-of-sample forward predictive checkpoints across (+1, +3, +5, +10 laps).
    """

    def __init__(self, curve_generator: Optional[TyreDegradationCurveGenerator] = None):
        self.curve_gen = curve_generator or TyreDegradationCurveGenerator()

    def run_validation_suite(
        self,
        laps_df: Optional[pd.DataFrame] = None,
        horizons: List[int] = [1, 3, 5, 10],
        min_stint_len: int = 12,
        dataset_name: str = "2024_2025_Clean_Telemetry",
    ) -> PostRaceValidationReport:
        if laps_df is None or "actual_lap_time_loss" not in laps_df.columns:
            df = load_data()
        else:
            df = laps_df.copy()

        horizon_data: Dict[int, Dict[str, List[float]]] = {
            h: {"actual": [], "m1": [], "context": []} for h in horizons
        }
        compound_stats: Dict[str, List[float]] = {}

        total_stints = 0
        total_laps = len(df)

        for stint_id, group in df.groupby("stint_id"):
            if len(group) < min_stint_len:
                continue

            total_stints += 1
            compound = str(group["compound"].iloc[0]) if "compound" in group.columns else "MEDIUM"
            if compound not in compound_stats:
                compound_stats[compound] = []

            group_sorted = group.sort_values("lap_number").reset_index(drop=True)
            y_loss = group_sorted["actual_lap_time_loss"].values
            ages = group_sorted["tyre_age"].values
            n_laps = len(group_sorted)

            # Evaluate at checkpoints: age 5, 8, 10, 15, 20...
            for cp_idx in range(4, n_laps - max(horizons)):
                cp_age = ages[cp_idx]
                
                # Context delta at checkpoint
                fuel_val = group_sorted["fuel_load_est"].iloc[cp_idx] if "fuel_load_est" in group_sorted.columns else 50.0
                fuel_adj = (110.0 - (fuel_val if not np.isnan(fuel_val) else 50.0)) * -0.018

                for h in horizons:
                    target_idx = cp_idx + h
                    if target_idx < n_laps:
                        target_age = ages[target_idx]
                        act_loss = float(y_loss[target_idx])

                        pred_m1 = STAGE1_M1_INTERCEPT + STAGE1_M1_SLOPE * target_age
                        pred_ctx = pred_m1 + fuel_adj

                        horizon_data[h]["actual"].append(act_loss)
                        horizon_data[h]["m1"].append(pred_m1)
                        horizon_data[h]["context"].append(pred_ctx)
                        compound_stats[compound].append(abs(pred_ctx - act_loss))

        horizon_evals: List[HorizonEvaluation] = []
        for h in horizons:
            acts = np.array(horizon_data[h]["actual"])
            m1s = np.array(horizon_data[h]["m1"])
            ctxs = np.array(horizon_data[h]["context"])

            if len(acts) > 5:
                m1_mae = float(np.mean(np.abs(m1s - acts)))
                m1_rmse = float(np.sqrt(np.mean((m1s - acts) ** 2)))
                m1_rho = float(stats.spearmanr(m1s, acts)[0]) if np.std(m1s) > 1e-6 and np.std(acts) > 1e-6 else 0.0
                m1_r = float(stats.pearsonr(m1s, acts)[0]) if np.std(m1s) > 1e-6 and np.std(acts) > 1e-6 else 0.0

                ctx_mae = float(np.mean(np.abs(ctxs - acts)))
                ctx_rmse = float(np.sqrt(np.mean((ctxs - acts) ** 2)))
                ctx_rho = float(stats.spearmanr(ctxs, acts)[0]) if np.std(ctxs) > 1e-6 and np.std(acts) > 1e-6 else 0.0
                ctx_r = float(stats.pearsonr(ctxs, acts)[0]) if np.std(ctxs) > 1e-6 and np.std(acts) > 1e-6 else 0.0

                mae_delta = ctx_mae - m1_mae
                is_sup = ctx_mae < m1_mae
            else:
                m1_mae, m1_rmse, m1_rho, m1_r = 0.0, 0.0, 0.0, 0.0
                ctx_mae, ctx_rmse, ctx_rho, ctx_r = 0.0, 0.0, 0.0, 0.0
                mae_delta = 0.0
                is_sup = False

            horizon_evals.append(
                HorizonEvaluation(
                    horizon_laps=h,
                    n_samples=len(acts),
                    m1_mae_s=m1_mae,
                    m1_rmse_s=m1_rmse,
                    m1_spearman_rho=m1_rho,
                    m1_pearson_r=m1_r,
                    context_mae_s=ctx_mae,
                    context_rmse_s=ctx_rmse,
                    context_spearman_rho=ctx_rho,
                    context_pearson_r=ctx_r,
                    mae_delta_s=mae_delta,
                    is_context_superior=is_sup,
                )
            )

        comp_summary = {}
        for c, errs in compound_stats.items():
            if len(errs) > 0:
                comp_summary[c] = {
                    "mean_mae_s": round(float(np.mean(errs)), 4),
                    "std_mae_s": round(float(np.std(errs)), 4),
                    "n_evaluations": len(errs),
                }

        summary = {
            "all_horizons_tested": horizons,
            "overall_context_mae_s": round(float(np.mean([h.context_mae_s for h in horizon_evals])), 4) if horizon_evals else 0.0,
            "overall_m1_mae_s": round(float(np.mean([h.m1_mae_s for h in horizon_evals])), 4) if horizon_evals else 0.0,
            "overall_mae_improvement_s": round(float(np.mean([h.mae_delta_s for h in horizon_evals])), 4) if horizon_evals else 0.0,
            "provenance_boundary": "Strict temporal causality at checkpoint lap N (zero future leakage)",
        }

        return PostRaceValidationReport(
            dataset_name=dataset_name,
            total_stints_evaluated=total_stints,
            total_laps_evaluated=total_laps,
            horizon_evaluations=horizon_evals,
            compound_breakdown=comp_summary,
            summary_findings=summary,
        )
