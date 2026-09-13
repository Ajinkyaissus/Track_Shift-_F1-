"""
TrackShift — Domain Constants: Single Source of Truth
======================================================
Empirical domain constants and coefficients for Formula 1 race performance modeling.

Constants:
----------
STAGE1_M1_INTERCEPT, STAGE1_M1_SLOPE:
  Empirically frozen parameters from chronological event-split regression on 2024 race laps.
  Status: FROZEN PRODUCTION BASELINE.

FUEL_EFFECT_COEFFICIENT:
  Domain fuel correction coefficient: 0.033 s/kg.
  Fitted on clean-lap telemetry regression modeling lap-time loss per kilogram of fuel on board.
  Status: CANONICAL DOMAIN COEFFICIENT.

TRACK_EVOLUTION_COEFFICIENT, TRAFFIC_EFFECT_COEFFICIENT:
  Observable sensitivity proxies.
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd

# Stage 1 Linear Tyre Age Baseline Parameters (Frozen 2024 Empirical Fit)
STAGE1_M1_INTERCEPT: float = 0.1974  # seconds
STAGE1_M1_SLOPE: float = 0.0400      # seconds per lap of tyre age

# Stage 1 M1 Compound-Specific Baselines (Fitted on 2024 green-flag telemetry)
STAGE1_M1_BY_COMPOUND: Dict[str, Dict[str, float]] = {
    "SOFT": {"intercept": 0.2476, "slope": 0.0655, "n": 1516},
    "MEDIUM": {"intercept": 0.5722, "slope": 0.0147, "n": 7528},
    "HARD": {"intercept": 0.5761, "slope": 0.0203, "n": 12134},
}

# Domain Fuel Correction Coefficient (Empirically Derived: 0.033 s/kg)
FUEL_EFFECT_COEFFICIENT: float = 0.033  # seconds per kg of fuel

# Contextual Proxy Coefficients
TRACK_EVOLUTION_COEFFICIENT: float = -0.008  # s / lap grip evolution
TRAFFIC_EFFECT_COEFFICIENT: float = 0.250    # s / traffic penalty unit


def stage1_m1_loss(tyre_age: float) -> float:
    """
    Stage 1 Linear Tyre Age Baseline prediction (global single-slope fallback).
    y_hat = 0.1974 + 0.0400 * max(0, tyre_age)
    """
    return STAGE1_M1_INTERCEPT + STAGE1_M1_SLOPE * max(0.0, float(tyre_age))


def stage1_m1_loss_by_compound(tyre_age: float, compound: Optional[str] = None) -> float:
    """
    Stage 1 Compound-Specific Linear Tyre Age Baseline prediction.
    Falls back safely to global single-slope stage1_m1_loss if compound is unknown or missing.
    """
    if compound is not None:
        comp_str = str(compound).strip().upper()
        if comp_str in STAGE1_M1_BY_COMPOUND:
            c_entry = STAGE1_M1_BY_COMPOUND[comp_str]
            return float(c_entry["intercept"]) + float(c_entry["slope"]) * max(0.0, float(tyre_age))
    return stage1_m1_loss(tyre_age)


def fit_compound_baselines(laps_df: pd.DataFrame, season: Optional[int] = None) -> Dict[str, Dict[str, Any]]:
    """
    Fits compound-specific linear degradation baselines on green-flag laps.
    
    Parameters
    ----------
    laps_df : pd.DataFrame
        Telemetry laps dataset.
    season : Optional[int]
        If specified (e.g. 2024), restricts fitting strictly to that season.
        
    Returns
    -------
    Dict[str, Dict[str, Any]]
        Fitted parameters {"SOFT": {"intercept": ..., "slope": ..., "n": ...}, ...}
    """
    df = laps_df.copy()
    if season is not None and "season" in df.columns:
        df = df[df["season"] == season].copy()
        
    lap_col = "lap_time_s" if "lap_time_s" in df.columns else "lap_time"
    age_col = "tyre_age" if "tyre_age" in df.columns else "TyreLife"
    comp_col = "compound" if "compound" in df.columns else "Compound"
    fuel_col = "fuel_kg" if "fuel_kg" in df.columns else "FuelProxy"
    
    group_cols = [c for c in ["season", "round", "driver", "stint_num"] if c in df.columns]
    if not group_cols:
        group_cols = [c for c in ["stint_id"] if c in df.columns]
        
    df = df.dropna(subset=[lap_col, age_col, comp_col]).copy()
    df = df[(df[lap_col] > 30.0) & (df[lap_col] < 150.0) & (df[age_col] >= 1)].copy()
    
    if "fuel_corrected_lap_time" not in df.columns:
        fuel_val = df[fuel_col] if fuel_col in df.columns else 50.0
        df["fuel_corrected_lap_time"] = df[lap_col] - FUEL_EFFECT_COEFFICIENT * fuel_val
        
    sort_keys = group_cols + (["LapNumber"] if "LapNumber" in df.columns else [age_col])
    df = df.sort_values(sort_keys).reset_index(drop=True)
    
    # Causal stint base pace: running minimum of first 3 fuel-corrected laps
    base_pace = df.groupby(group_cols)["fuel_corrected_lap_time"].transform(
        lambda s: s.iloc[:min(3, len(s))].min()
    )
    df["loss"] = (df["fuel_corrected_lap_time"] - base_pace).clip(lower=0.0)
    
    # Filter green-flag laps (< 4.0s from base pace)
    clean_df = df[df["loss"] < 4.0].copy()
    
    fitted = {}
    for comp in clean_df[comp_col].dropna().unique():
        comp_str = str(comp).strip().upper()
        sub = clean_df[clean_df[comp_col] == comp]
        if len(sub) >= 20:
            x = sub[age_col].values.astype(float)
            y = sub["loss"].values.astype(float)
            slope, intercept = np.polyfit(x, y, 1)
            fitted[comp_str] = {
                "intercept": round(float(intercept), 4),
                "slope": round(float(slope), 4),
                "n": int(len(sub))
            }
            
    return fitted

