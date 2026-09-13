"""
TrackShift — Module 1: Tyre Debt Liquidation
============================================
Calculates cumulative debt, recent debt burn rate, and projects future performance
cost under staying-out scenarios (+1, +2, +3, +5, +10, +15 laps).
Classifies liquidation urgency into LOW, MODERATE, HIGH, CRITICAL based on
explicit configuration thresholds.

Scientific hardening (2026-09):
- stage1_m1_loss now imports STAGE1_M1_INTERCEPT/SLOPE from domain_constants.
  No independent hardcoded literals.
"""

from typing import Dict, Any, List
import numpy as np

from trackshift.strategy.config import DEBT_LIQUIDATION_THRESHOLDS
from trackshift.domain_constants import (
    STAGE1_M1_INTERCEPT,
    STAGE1_M1_SLOPE,
    stage1_m1_loss,
)

# Re-export stage1_m1_loss for backward compatibility with existing importers
__all__ = ["stage1_m1_loss", "calculate_debt_liquidation"]


def calculate_debt_liquidation(
    lap_debts: List[float],
    current_tyre_age: int,
    k_window: int = 3
) -> Dict[str, Any]:
    """
    Computes cumulative debt, recent debt burn rate, projected future debt,
    and liquidation classification.

    Parameters
    ----------
    lap_debts : list of float
        Per-lap debt increments within current stint up to current lap.
    current_tyre_age : int
        Physical tyre age on current lap.
    k_window : int
        Lookback window for burn rate calculation.

    Returns
    -------
    dict with:
      current_debt_sec           : Cumulative debt in seconds
      debt_burn_rate_sec_per_lap : Rate of debt accumulation (s/lap) over last k laps
      horizon_projections        : Projections for +1, +2, +3, +5, +10, +15 laps
      liquidation_state          : 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL'
      explanation                : Component-level description
    """
    if not lap_debts:
        cum_debt = 0.0
        burn_rate = 0.0
    else:
        cum_debt = float(np.sum(lap_debts))
        n = len(lap_debts)
        if n == 1:
            burn_rate = float(lap_debts[-1])
        else:
            k = min(k_window, n)
            recent_chunk = lap_debts[-k:]
            burn_rate = float(np.mean(recent_chunk))

    burn_rate = max(0.0, burn_rate)
    horizons = [1, 2, 3, 5, 10, 15]
    horizon_projections = {}

    for h in horizons:
        proj_age = current_tyre_age + h
        proj_debt = cum_debt + (h * burn_rate)
        perf_cost = stage1_m1_loss(proj_age) + proj_debt
        horizon_projections[f"+{h}_laps"] = {
            "horizon_laps": h,
            "projected_tyre_age": proj_age,
            "projected_cumulative_debt": round(proj_debt, 4),
            "projected_marginal_loss_sec": round(stage1_m1_loss(proj_age) + (burn_rate * h), 4),
            "total_performance_cost_sec": round(perf_cost, 4),
        }

    # Classification
    th = DEBT_LIQUIDATION_THRESHOLDS
    if cum_debt > th["debt_high"] or burn_rate > th["burn_high"]:
        state = "CRITICAL"
    elif cum_debt > th["debt_moderate"] or burn_rate > th["burn_moderate"]:
        state = "HIGH"
    elif cum_debt > th["debt_low"] or burn_rate > th["burn_low"]:
        state = "MODERATE"
    else:
        state = "LOW"

    return {
        "current_debt_sec": round(cum_debt, 4),
        "debt_burn_rate_sec_per_lap": round(burn_rate, 4),
        "current_tyre_age": current_tyre_age,
        "liquidation_state": state,
        "horizon_projections": horizon_projections,
        "thresholds_used": th,
        "provenance": {
            "stage1_model": f"M1 Linear ({STAGE1_M1_INTERCEPT} + {STAGE1_M1_SLOPE} * age)",
            "stage1_constants_source": "trackshift.domain_constants",
            "stage2_formula": "cumulative sum of max(0, residual)",
            "classification": "data_derived_config_bounds",
        },
    }
