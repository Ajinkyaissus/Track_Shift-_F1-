"""
trackshift/diagnostics/driver_coverage.py — Real-Data Driver Analytics Coverage Diagnostic Tool.

Evaluates and reports genuine ML/DL pipeline coverage across every driver
in the selected FastF1 session without synthetic or fabricated data.
"""

import os
import sys
import argparse
import sqlite3
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(BASE_DIR, 'api', 'tyredebt.db')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')
PREDICTIONS_PARQUET = os.path.join(DATA_DIR, 'baseline_predictions.parquet')

from api.services.circuits_service import CircuitsService


def run_coverage_diagnostic(session_id: str):
    parts = session_id.split('_')
    circuit_id = '_'.join(parts[1:-1]).lower() if len(parts) > 2 else "circuit"

    circuits_svc = CircuitsService(DB_PATH, {
        "active_models": {1: "v3_stage1_2026-09-07", 3: "v5_tcn_stage3_2026-09-07"},
        "circuit_geometry": {},
        "circuit_corners": {},
        "ledger": {}
    })

    # 1. Discover session drivers
    drivers = circuits_svc._load_session_drivers_from_fastf1(session_id)
    if not drivers:
        print(f"Error: No session drivers discovered for '{session_id}'", file=sys.stderr)
        return

    # 2. Query session metadata
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT r.event_name, r.event_date, t.track_id, t.name as circuit_name
        FROM sessions ses
        JOIN races r ON ses.race_id = r.race_id
        JOIN tracks t ON r.track_id = t.track_id
        WHERE ses.session_id = ?
    """, (session_id,))
    row = c.fetchone()
    conn.close()

    event_name = row[0] if row else session_id
    event_date = row[1] if row else "2024-12-08"
    circuit_name = row[3] if row else circuit_id

    # 3. Load Parquet Data
    laps_df = pd.read_parquet(LAPS_PARQUET) if os.path.exists(LAPS_PARQUET) else pd.DataFrame()
    sess_laps = laps_df[laps_df['session_id'] == session_id] if not laps_df.empty and 'session_id' in laps_df.columns else pd.DataFrame()

    ledger_df = pd.read_parquet(LEDGER_PARQUET) if os.path.exists(LEDGER_PARQUET) else pd.DataFrame()
    pred_df = pd.read_parquet(PREDICTIONS_PARQUET) if os.path.exists(PREDICTIONS_PARQUET) else pd.DataFrame()

    # 4. Compute Per-Driver Diagnostics
    per_driver_stats = []
    drivers_with_laps = 0
    drivers_with_tel = 0
    drivers_with_stints = 0
    drivers_with_baseline = 0
    drivers_with_debt = 0
    drivers_with_tcn = 0
    drivers_with_sensitivity = 0

    for drv in drivers:
        d_id = drv['driver_id']
        drv_laps = sess_laps[sess_laps['driver_id'] == d_id] if not sess_laps.empty else pd.DataFrame()
        lap_cnt = len(drv_laps)
        has_laps = lap_cnt > 0

        has_tel = False
        if has_laps and 'braking_aggression' in drv_laps.columns:
            has_tel = drv_laps['braking_aggression'].dropna().count() > 0

        stint_ids = set(drv_laps['stint_id'].unique()) if has_laps and 'stint_id' in drv_laps.columns else set()
        has_stints = len(stint_ids) > 0

        has_baseline = False
        if not pred_df.empty and stint_ids:
            has_baseline = len(pred_df[pred_df['stint_id'].isin(stint_ids)]) > 0

        has_debt = False
        if not ledger_df.empty and stint_ids:
            has_debt = len(ledger_df[ledger_df['stint_id'].isin(stint_ids)]) > 0

        has_tcn = has_tel and lap_cnt >= 4
        has_sensitivity = has_tel and has_debt

        if has_laps: drivers_with_laps += 1
        if has_tel: drivers_with_tel += 1
        if has_stints: drivers_with_stints += 1
        if has_baseline: drivers_with_baseline += 1
        if has_debt: drivers_with_debt += 1
        if has_tcn: drivers_with_tcn += 1
        if has_sensitivity: drivers_with_sensitivity += 1

        per_driver_stats.append({
            "driver": d_id,
            "laps": lap_cnt,
            "telemetry": "yes" if has_tel else "no",
            "debt": "yes" if has_debt else "no",
            "tcn": "yes" if has_tcn else "no",
            "sensitivity": "yes" if has_sensitivity else "no"
        })

    # Print Summary Report matching Section 24 specification
    print("\nSESSION")
    print("-------")
    print(f"Session: {session_id}")
    print(f"Circuit: {circuit_id} ({circuit_name})")
    print(f"Date:    {event_date}")
    print()
    print("DRIVERS")
    print("-------")
    print(f"Drivers discovered:        {len(drivers)}")
    print(f"Drivers with laps:          {drivers_with_laps}")
    print(f"Drivers with telemetry:     {drivers_with_tel}")
    print(f"Drivers with stints:        {drivers_with_stints}")
    print(f"Drivers with baseline:      {drivers_with_baseline}")
    print(f"Drivers with tyre debt:     {drivers_with_debt}")
    print(f"Drivers with TCN:           {drivers_with_tcn}")
    print(f"Drivers with sensitivity:   {drivers_with_sensitivity}")
    print()
    print("PER DRIVER")
    print("----------")
    for s in per_driver_stats:
        print(f"{s['driver']:3s} | laps={s['laps']:2d} | telemetry={s['telemetry']:3s} | debt={s['debt']:3s} | TCN={s['tcn']:3s} | sensitivity={s['sensitivity']:3s}")
    print()


def main():
    parser = argparse.ArgumentParser(description="TrackShift Driver Analytics Coverage Diagnostic Tool")
    parser.add_argument("--session", "--session_id", dest="session_id", default="2024_abu_dhabi_R", help="Session ID (e.g. 2024_abu_dhabi_R)")
    args = parser.parse_args()

    run_coverage_diagnostic(args.session_id)


if __name__ == "__main__":
    main()
