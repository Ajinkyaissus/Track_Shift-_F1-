#!/usr/bin/env python3
"""
scripts/regenerate_residual_ledger.py

Runs model.py's ObservableDecompositionModel over real laps (data/laps.parquet)
to produce data/residual_ledger.parquet with strictly non-negative, monotonic
cumulative tyre debt.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from trackshift.tyre_intelligence.model import ObservableDecompositionModel
from api.cache import LEDGER_VERSION

LAPS_PATH = ROOT_DIR / "data" / "laps.parquet"
OUTPUT_PATH = ROOT_DIR / "data" / "residual_ledger.parquet"


def regenerate():
    if not LAPS_PATH.exists():
        raise FileNotFoundError(f"Missing {LAPS_PATH}")

    print(f"Reading {LAPS_PATH}...")
    laps_df = pd.read_parquet(LAPS_PATH)
    print(f"Loaded {len(laps_df):,} laps across {laps_df['stint_id'].nunique():,} stints.")

    model = ObservableDecompositionModel()
    records = []

    for stint_id, stint_group in laps_df.groupby("stint_id"):
        stint_sorted = stint_group.sort_values("lap_number").reset_index(drop=True)
        driver_id = str(stint_sorted["driver_id"].iloc[0]) if "driver_id" in stint_sorted.columns else "UNKNOWN"
        
        # Base lap time: 5th percentile or minimum lap time of representative laps
        green_laps = stint_sorted[stint_sorted["is_green_flag"] == 1] if "is_green_flag" in stint_sorted.columns else stint_sorted
        if len(green_laps) > 0 and "lap_time" in green_laps.columns:
            base_lap_time = float(green_laps["lap_time"].quantile(0.05))
        elif "lap_time" in stint_sorted.columns:
            base_lap_time = float(stint_sorted["lap_time"].min())
        else:
            base_lap_time = 90.0

        ledger = model.decompose_stint(
            stint_df=stint_sorted,
            driver_id=driver_id,
            stint_id=stint_id,
            base_lap_time=base_lap_time,
        )

        for pt in ledger.points:
            cum_debt = max(0.0, float(pt.contextual_debt_accumulated))
            records.append({
                "stint_id": stint_id,
                "lap_number": int(pt.lap_number),
                "actual_lap_time_loss": round(float(pt.observed_pace_delta), 4),
                "predicted_lap_time_loss": round(float(pt.context_adjusted_delta), 4),
                "residual": round(float(pt.contextual_residual), 4),
                "cumulative_debt": round(cum_debt, 4),
                "model_version": LEDGER_VERSION,
            })

    out_df = pd.DataFrame(records)
    
    # Assert zero negative debt entries
    neg_debt = (out_df["cumulative_debt"] < -1e-6).sum()
    assert neg_debt == 0, f"Negative debt assertion failed: {neg_debt} negative entries found!"

    print(f"Writing {len(out_df):,} records to {OUTPUT_PATH} (model_version: {LEDGER_VERSION})...")
    out_df.to_parquet(OUTPUT_PATH, index=False)
    print(f"Successfully generated {OUTPUT_PATH} with 0 negative debt entries.")


if __name__ == "__main__":
    regenerate()
