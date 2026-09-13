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

Scientific hardening note (2026-09):
- Tyre age is now derived from the `tyre_age` column in stint_df (preferred),
  or reconstructed from `tyre_age_start + (lap_number - start_lap)` if available,
  or falls back to sequential index ONLY after explicit sort — with provenance logged.
- track_evolution_proxy absent → uses 0.0, source = "unavailable" (never lap_number).
- All frozen M1 constants imported from trackshift.domain_constants (one source).
- estimate_contextual_lap_performance and compute_stint_contextual_residuals have been
  moved to trackshift.tyre_intelligence.research.contextual_pipeline (zero prod callers).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import logging
import pandas as pd

from trackshift.domain_constants import (
    STAGE1_M1_INTERCEPT,
    STAGE1_M1_SLOPE,
    stage1_m1_loss_by_compound,
)
from trackshift.tyre_intelligence.confounders import ObservableConfounderEstimator

logger = logging.getLogger("trackshift.tyre_intelligence.model")

# Re-export for downstream importers (backward-compatible)
__all__ = [
    "STAGE1_M1_INTERCEPT",
    "STAGE1_M1_SLOPE",
    "stage1_m1_loss_by_compound",
    "DecompositionPoint",
    "ContextualResidualLedger",
    "ObservableDecompositionModel",
]

# Tyre age source labels (provenance vocabulary)
TYRE_AGE_SOURCE_DATASET_FIELD = "dataset_field"
TYRE_AGE_SOURCE_RECONSTRUCTED = "reconstructed_from_stint_history"
TYRE_AGE_SOURCE_SEQUENTIAL_FALLBACK = "sequential_fallback_verified"
TYRE_AGE_SOURCE_UNAVAILABLE = "unavailable"


def _derive_tyre_age(row: "pd.Series", idx: int, start_lap: Optional[int], tyre_age_start: Optional[int]) -> tuple:
    """
    Derive physical tyre age for a single row with provenance tracking.

    Priority:
    1. `tyre_age` column directly in row (FastF1 TyreLife-derived field).
    2. Reconstruct: tyre_age_start + (lap_number - start_lap).
    3. Sequential index (only if caller verified sort is chronological).

    Returns
    -------
    (age: int, source: str)
    """
    # Priority 1: direct tyre_age column
    raw_age = row.get("tyre_age")
    if raw_age is not None and not (isinstance(raw_age, float) and pd.isna(raw_age)):
        return int(raw_age), TYRE_AGE_SOURCE_DATASET_FIELD

    # Priority 2: reconstruct from stint history
    lap_num = row.get("lap_number")
    if (
        tyre_age_start is not None
        and start_lap is not None
        and lap_num is not None
        and not pd.isna(lap_num)
    ):
        age = int(tyre_age_start) + (int(lap_num) - int(start_lap))
        return max(1, age), TYRE_AGE_SOURCE_RECONSTRUCTED

    # Priority 3: sequential fallback (only if data is confirmed sorted)
    return idx + 1, TYRE_AGE_SOURCE_SEQUENTIAL_FALLBACK


@dataclass
class DecompositionPoint:
    """Single lap point for observable confounder decomposition."""
    lap_number: int
    tyre_age: int
    tyre_age_source: str          # Provenance: how tyre_age was obtained
    observed_lap_time: float
    observed_pace_delta: float
    m1_baseline_delta: float
    context_adjusted_delta: float
    fuel_effect: float
    track_evolution_effect: float
    track_evolution_source: str   # Provenance: "dataset_field" | "unavailable"
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
                    "tyre_age_source": p.tyre_age_source,
                    "observed_lap_time": round(float(p.observed_lap_time), 3),
                    "observed_pace_delta": round(float(p.observed_pace_delta), 3),
                    "m1_baseline_delta": round(float(p.m1_baseline_delta), 3),
                    "context_adjusted_delta": round(float(p.context_adjusted_delta), 3),
                    "total_confounder_delta": round(float(p.total_confounder_delta), 3),
                    "track_evolution_source": p.track_evolution_source,
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

    Tyre Age Lineage
    ----------------
    Input stint_df must contain a `tyre_age` column (FastF1 TyreLife-derived).
    If absent, the model attempts reconstruction from `tyre_age_start` and
    `start_lap` columns. If neither is available, falls back to sequential
    index (only after deterministic sort by lap_number) — with explicit
    provenance logging.

    Missing laps are handled correctly: gaps in lap_number are preserved
    in tyre_age when using the dataset_field or reconstructed sources.
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
        """
        Decompose a stint into M1 baseline and contextual residuals.

        Parameters
        ----------
        stint_df : pd.DataFrame
            Stint lap rows. MUST be sortable by lap_number for chronological order.
            Should contain `tyre_age` column for physically correct tyre age.
        driver_id : str
        stint_id : str
        base_lap_time : float
            Reference lap time for delta computation.

        Returns
        -------
        ContextualResidualLedger
        """
        # P0 FIX: Sort by lap_number BEFORE iterating — never assume row order is chronological.
        if "lap_number" in stint_df.columns:
            df = stint_df.sort_values("lap_number").reset_index(drop=True)
        else:
            df = stint_df.reset_index(drop=True)
            logger.warning(
                "decompose_stint: stint_df for %s/%s has no lap_number column. "
                "Row order assumed chronological — verify upstream data.",
                driver_id, stint_id
            )

        # Extract stint context for tyre age reconstruction (priority 2 fallback)
        tyre_age_start: Optional[int] = None
        start_lap: Optional[int] = None
        if "tyre_age_start" in df.columns and not df["tyre_age_start"].isna().all():
            tyre_age_start = int(df["tyre_age_start"].iloc[0])
        if "start_lap" in df.columns and not df["start_lap"].isna().all():
            start_lap = int(df["start_lap"].iloc[0])

        points: List[DecompositionPoint] = []
        cum_m1_debt = 0.0
        cum_context_debt = 0.0

        # Track if we used fallback so we warn once, not per-lap
        used_fallback = False

        for idx, row in df.iterrows():
            # -- Tyre age (with provenance) --
            age, age_source = _derive_tyre_age(row, int(idx), start_lap, tyre_age_start)
            if age_source == TYRE_AGE_SOURCE_SEQUENTIAL_FALLBACK and not used_fallback:
                logger.warning(
                    "decompose_stint: stint %s/%s using sequential_fallback_verified for tyre_age. "
                    "Add tyre_age column to stint_df for physical correctness.",
                    driver_id, stint_id
                )
                used_fallback = True

            lap_num = int(row.get("lap_number", idx + 1))
            raw_time = float(row.get("lap_time", base_lap_time))
            observed_delta = raw_time - base_lap_time

            # Stage 1 M1 linear baseline delta (compound-aware with safe single-slope fallback)
            comp_val = row.get("compound") if "compound" in row else row.get("Compound")
            m1_delta = stage1_m1_loss_by_compound(age, comp_val)

            # Extract observable confounders (track_evolution_source tracked internally)
            ctx = self.confounders.extract_context(row.to_dict())
            conf_breakdown = self.confounders.compute_total_confounder_delta(ctx)

            fuel_eff = conf_breakdown["fuel_delta"]
            track_eff = conf_breakdown["track_evolution_delta"]
            track_evo_src = conf_breakdown.get("track_evolution_source", "unavailable")
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
                    tyre_age_source=age_source,
                    observed_lap_time=raw_time,
                    observed_pace_delta=observed_delta,
                    m1_baseline_delta=m1_delta,
                    context_adjusted_delta=context_delta,
                    fuel_effect=fuel_eff,
                    track_evolution_effect=track_eff,
                    track_evolution_source=track_evo_src,
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
