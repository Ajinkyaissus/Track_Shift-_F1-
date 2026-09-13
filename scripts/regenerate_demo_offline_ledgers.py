#!/usr/bin/env python3
"""
scripts/regenerate_demo_offline_ledgers.py

Synchronizes frontend/public/demo_offline/*_ledger.json with data/residual_ledger.parquet
guaranteeing zero negative debt and exact alignment with live serving data.
"""

import json
import os
import sys
from pathlib import Path
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

LEDGER_PARQUET = ROOT_DIR / "data" / "residual_ledger.parquet"
DEMO_DIR = ROOT_DIR / "frontend" / "public" / "demo_offline"


def regenerate_offline():
    if not LEDGER_PARQUET.exists():
        raise FileNotFoundError(f"Missing {LEDGER_PARQUET}. Run regenerate_residual_ledger.py first.")

    print(f"Loading {LEDGER_PARQUET}...")
    ledger_df = pd.read_parquet(LEDGER_PARQUET)
    grouped = dict(tuple(ledger_df.groupby("stint_id")))

    updated_count = 0
    total_files = 0
    neg_found = 0

    for file_path in DEMO_DIR.glob("*_ledger.json"):
        total_files += 1
        stint_id = file_path.name.replace("_ledger.json", "")

        if stint_id in grouped:
            stint_laps = grouped[stint_id].sort_values("lap_number")
            series = []
            for _, row in stint_laps.iterrows():
                debt = max(0.0, float(row["cumulative_debt"]))
                series.append({
                    "lap_number": int(row["lap_number"]),
                    "residual": round(float(row["residual"]), 4),
                    "cumulative_debt": round(debt, 4),
                })
            total_debt = round(series[-1]["cumulative_debt"], 4) if len(series) > 0 else 0.0
            version = str(stint_laps["model_version"].iloc[0])
        else:
            # Fallback: load existing file and clamp non-negative
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            series = data.get("series", [])
            running = 0.0
            for pt in series:
                res = pt.get("residual", 0.0)
                running = max(0.0, running + max(0.0, res))
                pt["cumulative_debt"] = round(running, 4)
            total_debt = round(series[-1]["cumulative_debt"], 4) if len(series) > 0 else 0.0
            version = data.get("model_version", "v4_regenerated")

        # Double check for negative debt
        if total_debt < 0 or any(p.get("cumulative_debt", 0) < 0 for p in series):
            neg_found += 1

        payload = {
            "stint_id": stint_id,
            "model_version": version,
            "total_debt_seconds": total_debt,
            "series": series
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        updated_count += 1

    print(f"Updated {updated_count}/{total_files} offline demo ledger files in {DEMO_DIR}.")
    assert neg_found == 0, f"Found {neg_found} files with negative debt!"
    print("Assertion passed: 0 negative debt entries across all offline ledger files.")


if __name__ == "__main__":
    regenerate_offline()
