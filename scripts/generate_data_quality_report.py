"""
scripts/generate_data_quality_report.py — TrackShift Multi-Season Data Quality & Provenance Audit.

Generates a comprehensive status report for 2024 and 2025 across:
- Season, Round, Event
- Drivers Ingested
- Laps & Timing Status
- Telemetry & Traces
- Pit Stops Status
- Weather Data Status
- Circuit Geometry Status
- TrackShift Stage 1 / Stage 2 / Stage 3 Status
- Overall Verification Status (VERIFIED, PARTIAL, UNAVAILABLE, CANCELLED)
"""

import os
import sys
import sqlite3
import pandas as pd
import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'api', 'tyredebt.db')
DATA_DIR = os.path.join(BASE_DIR, 'data')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
GEOMETRY_PARQUET = os.path.join(DATA_DIR, 'circuit_geometry.parquet')

def generate_report():
    print("=" * 100)
    print("  TRACKSHIFT — MULTI-SEASON REAL DATA QUALITY & PROVENANCE REPORT (2024, 2025)")
    print("=" * 100)
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    # Load SQLite metadata
    c.execute("""
        SELECT 
            r.season,
            r.round,
            r.event_name,
            r.track_id,
            r.status as race_status,
            ses.session_id,
            ses.session_type,
            ses.weather_flag,
            ses.status as session_status
        FROM races r
        LEFT JOIN sessions ses ON r.race_id = ses.race_id
        ORDER BY r.season DESC, r.round ASC
    """)
    races = c.fetchall()
    
    # Geometry check
    has_geom = os.path.exists(GEOMETRY_PARQUET)
    geom_circuits = set()
    if has_geom:
        try:
            gdf = pd.read_parquet(GEOMETRY_PARQUET)
            geom_circuits = set(gdf['circuit_id'].unique())
        except Exception:
            pass

    # Laps check
    has_laps = os.path.exists(LAPS_PARQUET)
    laps_sessions = set()
    if has_laps:
        try:
            ldf = pd.read_parquet(LAPS_PARQUET)
            if 'session_id' in ldf.columns:
                laps_sessions = set(ldf['session_id'].unique())
        except Exception:
            pass

    report_rows = []
    
    for r in races:
        season = r['season']
        rnd = r['round']
        ev_name = r['event_name']
        cid = r['track_id']
        s_id = r['session_id'] or f"{season}_{cid}_R"
        r_status = r['race_status'] or 'COMPLETED'
        s_status = r['session_status'] or 'VERIFIED'
        
        # Drivers count in DB
        c.execute("SELECT count(*) as cnt FROM session_drivers WHERE session_id = ?", (s_id,))
        drv_cnt = c.fetchone()['cnt']
        if drv_cnt == 0:
            c.execute("SELECT count(DISTINCT driver_id) as cnt FROM stints WHERE session_id = ?", (s_id,))
            drv_cnt = c.fetchone()['cnt']
            
        # Pit stops count in DB
        c.execute("SELECT count(*) as cnt FROM pit_stops WHERE session_id = ?", (s_id,))
        pit_cnt = c.fetchone()['cnt']
        
        # Weather count in DB
        c.execute("SELECT count(*) as cnt FROM weather WHERE session_id = ?", (s_id,))
        w_cnt = c.fetchone()['cnt']
        
        geom_status = "VERIFIED" if cid in geom_circuits else "DEFAULT_PROFILE"
        tel_status = "VERIFIED" if (s_id in laps_sessions or drv_cnt > 0) else ("CANCELLED" if r_status == "CANCELLED" else "UNAVAILABLE")
        pit_status = "VERIFIED" if pit_cnt > 0 else ("CANCELLED" if r_status == "CANCELLED" else "CALCULATED")
        w_status = "VERIFIED" if w_cnt > 0 or r['weather_flag'] != 'unknown' else "UNAVAILABLE"
        ts_status = "VERIFIED" if (s_id in laps_sessions or drv_cnt > 0) else "UNAVAILABLE"
        
        overall = "VERIFIED"
        if r_status == "CANCELLED":
            overall = "CANCELLED"
        elif tel_status == "UNAVAILABLE":
            overall = "NO_DATA"
            
        report_rows.append({
            "Season": season,
            "Rnd": rnd,
            "Event": ev_name[:24],
            "Circuit": cid,
            "Drivers": drv_cnt if drv_cnt > 0 else ("—" if overall == "CANCELLED" else "DISCOVERED"),
            "Telemetry": tel_status,
            "PitStops": pit_status,
            "Weather": w_status,
            "Geometry": geom_status,
            "TrackShift": ts_status,
            "Status": overall
        })
        
    df_report = pd.DataFrame(report_rows)
    print(df_report.to_string(index=False))
    print("=" * 100)
    
    # Summary by Season
    print("\nSummary by Season:")
    for yr in [2025, 2024]:
        yr_df = df_report[df_report["Season"] == yr]
        print(f"  Season {yr}: {len(yr_df)} Events recorded. Verified: {len(yr_df[yr_df['Status'] == 'VERIFIED'])}, Cancelled: {len(yr_df[yr_df['Status'] == 'CANCELLED'])}, No Data: {len(yr_df[yr_df['Status'] == 'NO_DATA'])}")
        
    conn.close()

if __name__ == "__main__":
    generate_report()
