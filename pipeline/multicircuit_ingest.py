"""
pipeline/multicircuit_ingest.py — Multi-circuit real F1 telemetry ingestion,
stint building, feature engineering, and data provenance tracking across target circuits.
Optimized for high-performance batch telemetry slicing.
"""
import os
import sys
import sqlite3
import datetime
import pandas as pd
import fastf1

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
SCHEMA_PATH = os.path.join(API_DIR, 'schema.sql')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')

# Target 13 Circuits with Verified Sessions
VERIFIED_SESSIONS = [
    {"circuit_id": "monza", "season": 2024, "round": 16, "event_name": "Italian Grand Prix", "session_type": "R"},
    {"circuit_id": "bahrain", "season": 2024, "round": 1, "event_name": "Bahrain Grand Prix", "session_type": "R"},
    {"circuit_id": "silverstone", "season": 2024, "round": 12, "event_name": "British Grand Prix", "session_type": "R"},
    {"circuit_id": "spa", "season": 2024, "round": 14, "event_name": "Belgian Grand Prix", "session_type": "R"},
    {"circuit_id": "suzuka", "season": 2024, "round": 4, "event_name": "Japanese Grand Prix", "session_type": "R"},
    {"circuit_id": "cota", "season": 2024, "round": 19, "event_name": "United States Grand Prix", "session_type": "R"},
    {"circuit_id": "hungaroring", "season": 2024, "round": 13, "event_name": "Hungarian Grand Prix", "session_type": "R"},
    {"circuit_id": "monaco", "season": 2024, "round": 8, "event_name": "Monaco Grand Prix", "session_type": "R"},
    {"circuit_id": "albert_park", "season": 2024, "round": 3, "event_name": "Australian Grand Prix", "session_type": "R"},
    {"circuit_id": "jeddah", "season": 2024, "round": 2, "event_name": "Saudi Arabian Grand Prix", "session_type": "R"},
    {"circuit_id": "singapore", "season": 2024, "round": 18, "event_name": "Singapore Grand Prix", "session_type": "R"},
    {"circuit_id": "interlagos", "season": 2024, "round": 21, "event_name": "Sao Paulo Grand Prix", "session_type": "R"},
    {"circuit_id": "abu_dhabi", "season": 2024, "round": 24, "event_name": "Abu Dhabi Grand Prix", "session_type": "R"}
]

from pipeline.features import (
    compute_braking_aggression,
    compute_throttle_transient_smoothness,
    compute_lateral_dynamics_proxy,
    compute_kerb_usage,
    compute_lockup_flag_rate,
    estimate_fuel_load
)

def run_multicircuit_ingest(target_drivers=None):
    print("=================================================================", flush=True)
    print("  TRACKSHIFT — MULTI-CIRCUIT REAL F1 TELEMETRY & STINT INGESTION ", flush=True)
    print("=================================================================", flush=True)
    fastf1.Cache.enable_cache(DATA_DIR)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Refresh tables
    cursor.execute("DELETE FROM provenance")
    cursor.execute("DELETE FROM stints")
    cursor.execute("DELETE FROM sessions")
    cursor.execute("DELETE FROM races")
    
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    all_laps_features = []
    stats = []

    for cfg in VERIFIED_SESSIONS:
        cid = cfg["circuit_id"]
        season = cfg["season"]
        rnd = cfg["round"]
        ev_name = cfg["event_name"]
        stype = cfg["session_type"]
        race_id = f"{season}_{cid}"
        session_id = f"{race_id}_{stype}"
        
        print(f"\n--- Ingesting {ev_name} ({season} R{rnd} {stype}) ---", flush=True)
        
        try:
            sess = fastf1.get_session(season, rnd, stype)
            sess.load(telemetry=True, laps=True, weather=True)
        except Exception as e:
            print(f"  [Warning] Failed loading session {session_id}: {e}", flush=True)
            continue
            
        laps = sess.laps
        if laps.empty:
            continue
            
        event_date = sess.session_info.get('StartDate', f'{season}-01-01')
        event_date_str = event_date.strftime('%Y-%m-%d') if hasattr(event_date, 'strftime') else str(event_date)[:10]

        cursor.execute("""
            INSERT OR REPLACE INTO races (race_id, season, round, track_id, event_date, event_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (race_id, season, rnd, cid, event_date_str, ev_name))
        
        # Weather & evolution index
        weather_flag = 'dry'
        if hasattr(sess, 'weather_data') and not sess.weather_data.empty:
            if 'Rainfall' in sess.weather_data.columns:
                rainfall = sess.weather_data['Rainfall']
                if rainfall.max() > 0:
                    weather_flag = 'wet' if rainfall.min() > 0 else 'mixed'
                    
        track_evolution_index = 1.20
        green_laps = laps[laps['TrackStatus'] == '1'].dropna(subset=['LapTime'])
        if len(green_laps) >= 10:
            sorted_laps = green_laps.sort_values('LapStartTime')
            n_quintile = max(1, len(sorted_laps) // 5)
            first_q = sorted_laps.head(n_quintile)['LapTime'].dt.total_seconds().median()
            last_q = sorted_laps.tail(n_quintile)['LapTime'].dt.total_seconds().median()
            track_evolution_index = round(float(first_q - last_q), 2)
            
        cursor.execute("""
            INSERT OR REPLACE INTO sessions (session_id, race_id, session_type, weather_flag, track_evolution_index)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, race_id, stype, weather_flag, track_evolution_index))
        
        # Record Provenance
        cursor.execute("""
            INSERT INTO provenance (source, season, event_name, round_number, circuit_id, session_type, session_date, retrieved_at, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, ("FastF1", season, ev_name, rnd, cid, stype, event_date_str, now_iso, f"Verified real telemetry, weather={weather_flag}, evo={track_evolution_index}"))

        # Ingest Drivers
        drivers_in_session = [d for d in pd.unique(laps['Driver']) if pd.notna(d) and len(str(d)) == 3]
        for d in drivers_in_session:
            try:
                d_info = sess.get_driver(d)
                d_name = d_info.get('FullName', d)
                d_team = d_info.get('TeamName', 'F1 Team')
            except:
                d_name = d
                d_team = 'F1 Team'
                
            reputation = 'tyre_management' if d in ['LEC', 'HAM', 'PER', 'SAI'] else ('aggressive' if d in ['VER', 'NOR', 'RUS'] else 'neutral')
            cursor.execute("""
                INSERT OR REPLACE INTO drivers (driver_id, full_name, team, reputation_tag)
                VALUES (?, ?, ?, ?)
            """, (d, d_name, d_team, reputation))

        # Stint building & Batch telemetry extraction
        stint_count = 0
        raw_laps_count = 0
        valid_laps_count = 0
        compounds_seen = set()
        
        if target_drivers is None:
            active_drivers = drivers_in_session
        else:
            active_drivers = [d for d in target_drivers if d in drivers_in_session]
            if not active_drivers:
                active_drivers = drivers_in_session
            
        for driver in active_drivers:
            driver_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')
            if driver_laps.empty:
                continue
                
            # Load full driver telemetry in one batch
            try:
                driver_tel = driver_laps.get_telemetry()
            except Exception:
                driver_tel = None

            stint_num = 1
            current_stint_laps = []
            current_compound = None
            
            for _, lap in driver_laps.iterrows():
                comp = lap['Compound']
                if pd.isna(comp) or comp not in ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']:
                    continue
                    
                compounds_seen.add(comp)
                
                if current_compound is None:
                    current_compound = comp
                    
                if comp != current_compound:
                    if len(current_stint_laps) >= 4:
                        stint_id = f"{session_id}_{driver}_{stint_num}"
                        start_l = min(l['lap'] for l in current_stint_laps)
                        end_l = max(l['lap'] for l in current_stint_laps)
                        age_start = current_stint_laps[0]['tyre_life'] if pd.notna(current_stint_laps[0]['tyre_life']) else 0
                        cursor.execute("""
                            INSERT OR REPLACE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        """, (stint_id, session_id, driver, current_compound, start_l, end_l, int(age_start)))
                        stint_count += 1
                        stint_num += 1
                    current_stint_laps = []
                    current_compound = comp
                    
                is_green = 1 if lap['TrackStatus'] == '1' else 0
                current_stint_laps.append({'lap': lap['LapNumber'], 'tyre_life': lap['TyreLife'], 'is_valid': is_green})
                
                # Sliced telemetry for this lap
                raw_laps_count += 1
                if driver_tel is not None and not driver_tel.empty and pd.notna(lap['LapStartTime']) and pd.notna(lap['LapTime']):
                    lap_start = lap['LapStartTime']
                    lap_end = lap_start + lap['LapTime']
                    tel_slice = driver_tel[(driver_tel['Time'] >= lap_start) & (driver_tel['Time'] <= lap_end)]
                    
                    if not tel_slice.empty and 'Brake' in tel_slice.columns and 'Throttle' in tel_slice.columns:
                        brake_agg = compute_braking_aggression(tel_slice)
                        throttle_smooth = compute_throttle_transient_smoothness(tel_slice)
                        lat_dyn = compute_lateral_dynamics_proxy(tel_slice)
                        kerb = compute_kerb_usage(tel_slice)
                        lockup = compute_lockup_flag_rate(tel_slice)
                        fuel = estimate_fuel_load(lap['LapNumber'], 1, stype)
                        lap_time_s = lap['LapTime'].total_seconds()
                        
                        if pd.notna(lap_time_s) and pd.notna(brake_agg):
                            stint_id_temp = f"{session_id}_{driver}_{stint_num}"
                            all_laps_features.append({
                                'stint_id': stint_id_temp,
                                'circuit_id': cid,
                                'session_id': session_id,
                                'driver_id': driver,
                                'compound': comp,
                                'lap_number': lap['LapNumber'],
                                'lap_time': lap_time_s,
                                'is_green_flag': is_green,
                                'fuel_load_est': fuel,
                                'braking_aggression': brake_agg,
                                'throttle_transient_smoothness': throttle_smooth,
                                'lateral_dynamics_proxy': lat_dyn,
                                'kerb_usage': kerb,
                                'lockup_flag_rate': lockup
                            })
                            valid_laps_count += 1
                            
                if pd.notna(lap['PitInTime']):
                    if len(current_stint_laps) >= 4:
                        stint_id = f"{session_id}_{driver}_{stint_num}"
                        start_l = min(l['lap'] for l in current_stint_laps)
                        end_l = max(l['lap'] for l in current_stint_laps)
                        age_start = current_stint_laps[0]['tyre_life'] if pd.notna(current_stint_laps[0]['tyre_life']) else 0
                        cursor.execute("""
                            INSERT OR REPLACE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        """, (stint_id, session_id, driver, current_compound, start_l, end_l, int(age_start)))
                        stint_count += 1
                        stint_num += 1
                    current_stint_laps = []
                    current_compound = None
                    
            if len(current_stint_laps) >= 4 and current_compound is not None:
                stint_id = f"{session_id}_{driver}_{stint_num}"
                start_l = min(l['lap'] for l in current_stint_laps)
                end_l = max(l['lap'] for l in current_stint_laps)
                age_start = current_stint_laps[0]['tyre_life'] if pd.notna(current_stint_laps[0]['tyre_life']) else 0
                cursor.execute("""
                    INSERT OR REPLACE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (stint_id, session_id, driver, current_compound, start_l, end_l, int(age_start)))
                stint_count += 1

        drop_rate = ((raw_laps_count - valid_laps_count) / raw_laps_count * 100.0) if raw_laps_count > 0 else 0.0
        stats.append({
            "circuit": cid,
            "event": ev_name,
            "drivers": len(active_drivers),
            "compounds": ", ".join(sorted(compounds_seen)),
            "stints": stint_count,
            "raw_laps": raw_laps_count,
            "valid_laps": valid_laps_count,
            "drop_pct": round(drop_rate, 1)
        })
        print(f"  -> Built {stint_count} stints, extracted {valid_laps_count}/{raw_laps_count} laps (Drop: {drop_rate:.1f}%)", flush=True)

    conn.commit()
    conn.close()

    if all_laps_features:
        laps_df = pd.DataFrame(all_laps_features)
        laps_df.to_parquet(LAPS_PARQUET, index=False)
        print(f"\n[OK] Successfully saved {len(laps_df)} multi-circuit laps to {LAPS_PARQUET}", flush=True)
    else:
        print("[Warning] No laps features extracted.", flush=True)

    return pd.DataFrame(stats)

if __name__ == "__main__":
    df_stats = run_multicircuit_ingest()
    print("\n=== MULTI-CIRCUIT INGESTION SUMMARY ===", flush=True)
    print(df_stats.to_string(index=False), flush=True)
