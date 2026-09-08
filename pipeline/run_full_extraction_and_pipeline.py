import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import fastf1
import time

BASE_DIR = r"c:\Users\harsh\Downloads\TrackShift-main"
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')

fastf1.Cache.enable_cache(DATA_DIR)

from pipeline.features import (
    compute_braking_aggression,
    compute_throttle_transient_smoothness,
    compute_lateral_dynamics_proxy,
    compute_kerb_usage,
    compute_lockup_flag_rate,
    estimate_fuel_load
)

def run_extraction():
    print("=" * 80)
    print("TRACKSHIFT — FULL MULTI-SEASON REAL TELEMETRY EXTRACTION")
    print("=" * 80)
    
    conn = sqlite3.connect(DB_PATH)
    stints = pd.read_sql_query("""
        SELECT s.stint_id, s.session_id, s.driver_id, s.compound, s.start_lap, s.end_lap, s.tyre_age_start, s.is_valid,
               ses.race_id, ses.session_type, r.event_name, r.round, r.season, r.track_id
        FROM stints s
        JOIN sessions ses ON s.session_id = ses.session_id
        JOIN races r ON ses.race_id = r.race_id
        WHERE ses.status = 'VERIFIED'
        ORDER BY r.season, r.round, s.driver_id, s.start_lap
    """, conn)
    conn.close()

    session_groups = list(stints.groupby('session_id'))
    print(f"Total verified sessions to process: {len(session_groups)}")
    
    all_laps = []
    report_rows = []
    t_start = time.time()

    for idx, (session_id, grp) in enumerate(session_groups, 1):
        t0 = time.time()
        season = int(grp.iloc[0]['season'])
        rnd = int(grp.iloc[0]['round'])
        stype = grp.iloc[0]['session_type']
        ev_name = grp.iloc[0]['event_name']
        cid = grp.iloc[0]['track_id']
        
        try:
            sess = fastf1.get_session(season, rnd, stype)
            sess.load(telemetry=True, laps=True, weather=False)
        except Exception as e:
            print(f"[{idx:02d}/{len(session_groups)}] ERROR {session_id}: {e}", flush=True)
            report_rows.append({
                "season": season, "session": session_id, "event": ev_name,
                "drivers": 0, "tel_rows": 0, "feature_rows": 0, "status": f"FAILED: {e}"
            })
            continue

        laps = getattr(sess, 'laps', None)
        if laps is None or laps.empty:
            print(f"[{idx:02d}/{len(session_groups)}] WARN no laps for {session_id}", flush=True)
            report_rows.append({
                "season": season, "session": session_id, "event": ev_name,
                "drivers": 0, "tel_rows": 0, "feature_rows": 0, "status": "NO_LAPS"
            })
            continue

        sess_rows = 0
        drivers_seen = set()
        total_tel_rows = 0

        for driver, d_stints in grp.groupby('driver_id'):
            d_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')
            if d_laps.empty:
                continue

            try:
                d_tel = d_laps.get_telemetry()
            except Exception:
                continue

            if d_tel is None or d_tel.empty or 'Brake' not in d_tel.columns or 'Throttle' not in d_tel.columns:
                continue

            drivers_seen.add(driver)
            total_tel_rows += len(d_tel)

            for _, stint in d_stints.iterrows():
                st_id = stint['stint_id']
                s_lap = stint['start_lap']
                e_lap = stint['end_lap']
                comp = stint['compound']

                st_laps = d_laps[(d_laps['LapNumber'] >= s_lap) & (d_laps['LapNumber'] <= e_lap)]

                for _, lap in st_laps.iterrows():
                    l_no = int(lap['LapNumber'])
                    lap_start = lap.get('LapStartTime')
                    lap_time = lap.get('LapTime')
                    if pd.isna(lap_start) or pd.isna(lap_time):
                        continue
                    lap_time_s = lap_time.total_seconds() if hasattr(lap_time, 'total_seconds') else float(lap_time)
                    lap_end = lap_start + lap_time

                    tel_slice = d_tel[(d_tel['Time'] >= lap_start) & (d_tel['Time'] <= lap_end)]
                    if tel_slice.empty:
                        continue

                    b_agg = compute_braking_aggression(tel_slice)
                    t_smo = compute_throttle_transient_smoothness(tel_slice)
                    l_dyn = compute_lateral_dynamics_proxy(tel_slice)
                    k_use = compute_kerb_usage(tel_slice)
                    l_rat = compute_lockup_flag_rate(tel_slice)
                    fuel = estimate_fuel_load(l_no, s_lap, stype)
                    is_green = 1 if lap.get('TrackStatus') == '1' else 0

                    if pd.notna(b_agg) and pd.notna(lap_time_s):
                        all_laps.append({
                            'stint_id': st_id,
                            'circuit_id': cid,
                            'session_id': session_id,
                            'driver_id': driver,
                            'compound': comp,
                            'lap_number': l_no,
                            'lap_time': lap_time_s,
                            'is_green_flag': is_green,
                            'fuel_load_est': fuel,
                            'braking_aggression': b_agg,
                            'throttle_transient_smoothness': t_smo,
                            'lateral_dynamics_proxy': l_dyn,
                            'kerb_usage': k_use,
                            'lockup_flag_rate': l_rat
                        })
                        sess_rows += 1

        elapsed = time.time() - t0
        print(f"[{idx:02d}/{len(session_groups)}] {session_id} ({season} R{rnd:02d}): {len(drivers_seen)} drivers, {sess_rows} features ({elapsed:.1f}s)", flush=True)
        report_rows.append({
            "season": season,
            "session": session_id,
            "event": ev_name,
            "drivers": len(drivers_seen),
            "tel_rows": total_tel_rows,
            "feature_rows": sess_rows,
            "status": "VERIFIED_EXTRACTED"
        })

    total_time = time.time() - t_start
    print(f"\nExtraction complete in {total_time:.1f}s.")
    
    df = pd.DataFrame(all_laps)
    df.to_parquet(LAPS_PARQUET, index=False)
    print(f"[OK] Saved {len(df)} multi-season real laps to {LAPS_PARQUET}")
    print(f"Sessions count: {df['session_id'].nunique()}/33")
    print(f"Stints count: {df['stint_id'].nunique()}")
    print("Breakdown by season:", df['session_id'].str.split('_').str[0].value_counts().to_dict())

    rep_df = pd.DataFrame(report_rows)
    rep_df.to_csv(os.path.join(DATA_DIR, "extraction_report.csv"), index=False)

    print("\n--- Synchronizing Stage 1 Baseline Model ---")
    from pipeline.model_stage1 import train_baseline_model
    train_baseline_model()

    print("\n--- Synchronizing Stage 2 Residual Ledger ---")
    from pipeline.model_stage2 import build_residual_ledger
    build_residual_ledger()

    print("\n--- Synchronizing Stage 3 Uncertainty Bootstrap ---")
    from pipeline.uncertainty_bootstrap import run_stint_bootstrap
    run_stint_bootstrap(n_bootstrap=100)

    print("\n[VERIFICATION READY] All multi-season datasets synchronized from genuine telemetry.")

if __name__ == "__main__":
    run_extraction()
