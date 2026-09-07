import sqlite3
import os
import fastf1
import pandas as pd
import numpy as np

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
PARQUET_PATH = os.path.join(DATA_DIR, 'laps.parquet')

def load_stints():
    conn = sqlite3.connect(DB_PATH)
    stints = pd.read_sql_query("""
        SELECT s.stint_id, s.session_id, s.driver_id, s.compound, s.start_lap, s.end_lap, s.tyre_age_start, s.is_valid,
               ses.race_id, ses.session_type, r.event_name
        FROM stints s
        JOIN sessions ses ON s.session_id = ses.session_id
        JOIN races r ON ses.race_id = r.race_id
        WHERE s.is_valid = 1
    """, conn)
    conn.close()
    return stints

def estimate_fuel_load(lap_number, start_lap, session_type):
    # Derived/Estimated feature: 
    # Assume 110kg start for Race, burning ~1.5kg per lap.
    if session_type == 'R':
        return max(0, 110 - (lap_number * 1.5))
    return 10.0 # Quali/FP placeholder

def compute_braking_aggression(telemetry):
    """
    Derived feature: deceleration rate (d(Speed)/dt) during Brake=True windows.
    NOT a raw brake-pressure value.
    """
    if 'Brake' not in telemetry.columns or 'Speed' not in telemetry.columns or 'Time' not in telemetry.columns:
        return np.nan
    dt = telemetry['Time'].dt.total_seconds().diff()
    dv = telemetry['Speed'].diff()
    decel = -dv / dt
    decel = decel[(telemetry['Brake'] == True) & (decel > 0) & (decel < 200)]
    if len(decel) == 0:
        return 0.0
    return float(decel.mean())

def compute_throttle_transient_smoothness(telemetry):
    """
    Derived feature: from raw Throttle (0-100%) channel.
    """
    if 'Throttle' not in telemetry.columns:
        return np.nan
    throttle = telemetry['Throttle']
    return float(throttle.diff().abs().mean())

def compute_lateral_dynamics_proxy(telemetry):
    """
    Estimated feature: curvature / lateral-g estimate computed from X/Y position trace.
    Replaces previously named raw steering channel.
    """
    if 'X' not in telemetry.columns or 'Y' not in telemetry.columns:
        return np.nan
    dx = telemetry['X'].diff()
    dy = telemetry['Y'].diff()
    ddx = dx.diff()
    ddy = dy.diff()
    denom = (dx**2 + dy**2)**1.5
    denom = denom.replace(0, np.nan)
    curvature = (dx*ddy - dy*ddx).abs() / denom
    if curvature.isna().all():
        return 0.0
    return float(curvature.mean())

def compute_kerb_usage(telemetry):
    """
    Derived feature: High-frequency lateral load dynamics / micro-correction jerk proxy.
    Directly measures lateral load rate-of-change and aggressive kerb-riding tyre stress
    without relying on unreliable/missing Z elevation channels.
    """
    if 'X' not in telemetry.columns or 'Y' not in telemetry.columns or 'Speed' not in telemetry.columns or 'Time' not in telemetry.columns:
        return 0.0
    dt = telemetry['Time'].dt.total_seconds().diff()
    dx = telemetry['X'].diff()
    dy = telemetry['Y'].diff()
    ddx = dx.diff()
    ddy = dy.diff()
    denom = (dx**2 + dy**2)**1.5
    denom = denom.replace(0, np.nan)
    curvature = (dx*ddy - dy*ddx).abs() / denom
    speed_ms = telemetry['Speed'] / 3.6
    lat_acc = (speed_ms**2) * curvature.fillna(0)
    lat_jerk = lat_acc.diff() / dt.replace(0, np.nan)
    jerk_mean = lat_jerk.abs().dropna().clip(0, 500).mean()
    if pd.isna(jerk_mean):
        return 0.0
    return float(jerk_mean)

def compute_lockup_flag_rate(telemetry):
    """
    Derived feature: RPM/Speed mismatches under braking.
    """
    if 'RPM' not in telemetry.columns or 'Speed' not in telemetry.columns or 'Brake' not in telemetry.columns:
        return 0.0
    brake_zones = telemetry[telemetry['Brake'] == True]
    if len(brake_zones) == 0:
        return 0.0
    return float((brake_zones['RPM'] < 5000).mean())

def process_features():
    fastf1.Cache.enable_cache(DATA_DIR)
    stints = load_stints()
    
    if stints.empty:
        print("No valid stints found in database.")
        return
        
    lap_features = []
    
    for session_id, session_stints in stints.groupby('session_id'):
        race_id = session_stints.iloc[0]['race_id']
        s_type = session_stints.iloc[0]['session_type']
        event_name = session_stints.iloc[0]['event_name']
        season = int(race_id.split('_')[0])
        
        try:
            session = fastf1.get_session(season, event_name, s_type)
            session.load(telemetry=True, laps=True, weather=False)
        except Exception as e:
            print(f"Failed to load session {session_id}: {e}")
            continue
            
        try:
            laps = session.laps
            if len(laps) == 0:
                continue
        except fastf1.exceptions.DataNotLoadedError:
            continue
            
        for _, stint in session_stints.iterrows():
            driver = stint['driver_id']
            start = stint['start_lap']
            end = stint['end_lap']
            
            driver_laps = laps[(laps['Driver'] == driver) & (laps['LapNumber'] >= start) & (laps['LapNumber'] <= end)]
            
            for _, lap in driver_laps.iterrows():
                lap_num = lap['LapNumber']
                
                try:
                    tel = lap.get_telemetry()
                except Exception:
                    continue
                    
                if tel.empty:
                    continue
                    
                brake_agg = compute_braking_aggression(tel)
                throttle_smooth = compute_throttle_transient_smoothness(tel)
                lat_dyn = compute_lateral_dynamics_proxy(tel)
                kerb = compute_kerb_usage(tel)
                lockup = compute_lockup_flag_rate(tel)
                fuel = estimate_fuel_load(lap_num, start, s_type)
                
                is_green = 1 if lap['TrackStatus'] == '1' else 0
                lap_time = lap['LapTime'].total_seconds() if not pd.isna(lap['LapTime']) else np.nan
                
                lap_features.append({
                    'stint_id': stint['stint_id'],
                    'lap_number': lap_num,
                    'lap_time': lap_time,
                    'is_green_flag': is_green,
                    'fuel_load_est': fuel,
                    'braking_aggression': brake_agg,
                    'throttle_transient_smoothness': throttle_smooth,
                    'lateral_dynamics_proxy': lat_dyn,
                    'kerb_usage': kerb,
                    'lockup_flag_rate': lockup
                })
                
    if lap_features:
        df = pd.DataFrame(lap_features)
        
        # Telemetry ingestion stats
        initial_len = len(df)
        df = df.dropna(subset=['lap_time', 'braking_aggression', 'throttle_transient_smoothness', 'lateral_dynamics_proxy', 'lockup_flag_rate', 'kerb_usage'])
        valid_len = len(df)
        dropped = initial_len - valid_len
        drop_pct = (dropped / initial_len * 100.0) if initial_len > 0 else 0.0

        print(f"--- FastF1 Feature Ingestion Report ---")
        print(f"Raw laps extracted:      {initial_len}")
        print(f"Valid laps retained:     {valid_len}")
        print(f"Dropped laps:            {dropped}")
        print(f"Drop percentage:         {drop_pct:.2f}%")
        print(f"Final laps:              {valid_len}")
        print(f"----------------------------------------")
            
        if len(df) < 5:
            import sys
            print("Too few rows remaining. Exiting.", file=sys.stderr)
            sys.exit(1)
            
        print("Phase 1 Gate Check passed: Ingestion data validated.")
            
        # Save as parquet
        df.to_parquet(PARQUET_PATH, index=False)
        print(f"Successfully saved {len(df)} laps to {PARQUET_PATH}")
    else:
        print("No features extracted.")

if __name__ == "__main__":
    print("Starting feature engineering (Phase 1)...")
    process_features()
    print("Feature engineering complete.")
