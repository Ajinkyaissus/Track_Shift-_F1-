import sqlite3
import os
import fastf1
import pandas as pd

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
SCHEMA_PATH = os.path.join(API_DIR, 'schema.sql')

def init_db():
    # Execute schema.sql to initialize if not exists
    # timeout=30 prevents "database is locked" errors when two ingest runs overlap
    conn = sqlite3.connect(DB_PATH, timeout=30)
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
    conn.executescript(schema)
    conn.commit()
    return conn

SUPPORTED_SEASONS = [2024, 2025]

def ingest_data(seasons=[2024, 2025], limit_races=None, target_round=None):
    for s in seasons:
        if s not in SUPPORTED_SEASONS:
            raise ValueError(f"Unsupported season: {s}. Supported seasons: {SUPPORTED_SEASONS}")
    fastf1.Cache.enable_cache(DATA_DIR)
    conn = init_db()
    cursor = conn.cursor()
    
    for season in seasons:
        try:
            schedule = fastf1.get_event_schedule(season)
        except fastf1.exceptions.RateLimitExceededError:
            print("Rate limit exceeded. Please wait an hour before trying again.")
            return
            
        # Filter for actual races (exclude testing)
        races = schedule[schedule['EventFormat'] != 'testing']
        
        if target_round:
            races = races[races['RoundNumber'] == target_round]
            
        if limit_races:
            races = races.head(limit_races)
            
        for _, event in races.iterrows():
            race_id = f"{season}_{event['EventName'].replace(' ', '').lower()}"
            event_name = event['EventName']
            track_id = event['Location'].lower().replace(' ', '_')
            
            # Insert track
            cursor.execute('''
                INSERT OR IGNORE INTO tracks (track_id, name, country)
                VALUES (?, ?, ?)
            ''', (track_id, event['EventName'], event['Country']))
            
            # Insert race
            cursor.execute('''
                INSERT OR IGNORE INTO races (race_id, season, round, track_id, event_date, event_name)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (race_id, season, event['RoundNumber'], track_id, event['EventDate'].isoformat(), event_name))
            
            # For Phase 0 MVP, we just load Race (R) session
            session_types = ['R']
            for s_type in session_types:
                try:
                    session = fastf1.get_session(season, event['RoundNumber'], s_type)
                    session.load(telemetry=True, laps=True, weather=True)
                except fastf1.exceptions.RateLimitExceededError:
                    print(f"Rate limit exceeded while loading {race_id}. Stopping.")
                    conn.commit()
                    conn.close()
                    return
                except Exception as e:
                    print(f"Failed to load {race_id} {s_type}: {e}")
                    continue
                
                try:
                    laps = session.laps
                    if len(laps) == 0:
                        print(f"No laps data found for {race_id} {s_type}")
                        continue
                except fastf1.exceptions.DataNotLoadedError:
                    print(f"FastF1 data not loaded for {race_id} {s_type}")
                    continue

                session_id = f"{race_id}_{s_type}"
                
                # Derive weather_flag from actual weather data
                weather_flag = 'unknown'
                if hasattr(session, 'weather_data') and not session.weather_data.empty:
                    if 'Rainfall' in session.weather_data.columns:
                        rainfall = session.weather_data['Rainfall']
                        if rainfall.max() == 0:
                            weather_flag = 'dry'
                        elif rainfall.min() > 0:
                            weather_flag = 'wet'
                        else:
                            weather_flag = 'mixed'
                
                # Calculate track_evolution_index
                # Formula: median lap time of first 20% of laps minus median lap time of last 20% of laps (green flag only)
                track_evolution_index = 1.0
                if len(laps) > 0:
                    green_laps = laps[laps['TrackStatus'] == '1'].dropna(subset=['LapTime'])
                    if len(green_laps) >= 10:
                        sorted_laps = green_laps.sort_values('LapStartTime')
                        n_quintile = max(1, len(sorted_laps) // 5)
                        first_q = sorted_laps.head(n_quintile)['LapTime'].dt.total_seconds().median()
                        last_q = sorted_laps.tail(n_quintile)['LapTime'].dt.total_seconds().median()
                        track_evolution_index = float(first_q - last_q)
                
                cursor.execute('''
                    INSERT OR IGNORE INTO sessions (session_id, race_id, session_type, weather_flag, track_evolution_index)
                    VALUES (?, ?, ?, ?, ?)
                ''', (session_id, race_id, s_type, weather_flag, track_evolution_index))
                
                # Insert drivers
                drivers = pd.unique(laps['Driver'])
                for d in drivers:
                    if not pd.isna(d) and len(str(d)) == 3:
                        # Find driver name
                        try:
                            driver_info = session.get_driver(d)
                            full_name = driver_info['FullName']
                            team = driver_info['TeamName']
                        except:
                            full_name = d
                            team = "Unknown"
                            
                        cursor.execute('''
                            INSERT OR IGNORE INTO drivers (driver_id, full_name, team)
                            VALUES (?, ?, ?)
                        ''', (d, full_name, team))
                
                # Gate Check: verify telemetry and tyre fields exist
                has_compound = 'Compound' in laps.columns and 'TyreLife' in laps.columns
                print(f"Gate Check: Tyre compound/age fields present: {has_compound}")
                
                # To check telemetry, we need to load telemetry for at least one lap
                if len(laps) > 0:
                    telemetry_ok = False
                    for _, check_lap in laps.head(5).iterrows():
                        try:
                            tel = check_lap.get_telemetry()
                            if not tel.empty:
                                has_braking = 'Brake' in tel.columns and tel['Brake'].notna().any()
                                has_throttle = 'Throttle' in tel.columns and tel['Throttle'].notna().any()
                                has_xy = 'X' in tel.columns and 'Y' in tel.columns and tel['X'].notna().any()
                                if has_braking and has_throttle and has_xy:
                                    telemetry_ok = True
                                    break
                        except Exception:
                            continue
                        
                    if not (telemetry_ok and has_compound):
                        import sys
                        print(f"WARNING: GATE FAILED for {race_id} {s_type}. Missing required telemetry or tyre fields.", file=sys.stderr)
                        continue
                    else:
                        print("GATE PASSED: All required fields present.")

                # Create stints based on boundary rules
                for driver in drivers:
                    driver_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')
                    
                    if driver_laps.empty:
                        continue
                        
                    stint_num = 1
                    current_stint_laps = []
                    current_compound = None
                    
                    for idx, lap in driver_laps.iterrows():
                        # Exclude SC/VSC/Red flag
                        is_valid_lap = True
                        if not pd.isna(lap['TrackStatus']) and lap['TrackStatus'] != '1':
                            is_valid_lap = False # Has SC/VSC/Yellow etc.
                            
                        compound = lap['Compound']
                        if pd.isna(compound):
                            continue
                            
                        if current_compound is None:
                            current_compound = compound
                            
                        if compound != current_compound:
                            # End previous stint, save it
                            if current_stint_laps:
                                save_stint(cursor, session_id, driver, current_compound, stint_num, current_stint_laps)
                                stint_num += 1
                                current_stint_laps = []
                            current_compound = compound
                        
                        current_stint_laps.append({'lap': lap['LapNumber'], 'tyre_life': lap['TyreLife'], 'is_valid': is_valid_lap})
                        
                        if not pd.isna(lap['PitInTime']):
                            # End stint on pit in
                            save_stint(cursor, session_id, driver, current_compound, stint_num, current_stint_laps)
                            stint_num += 1
                            current_stint_laps = []
                            current_compound = None # Next lap will define new compound
                            
                    # Save last stint if any
                    if current_stint_laps:
                        save_stint(cursor, session_id, driver, current_compound, stint_num, current_stint_laps)
            
    conn.commit()
    conn.close()

def save_stint(cursor, session_id, driver, compound, stint_num, laps_data):
    if not laps_data:
        return
        
    start_lap = min(l['lap'] for l in laps_data)
    end_lap = max(l['lap'] for l in laps_data)
    
    # is_valid = 0 for stints excluded by the boundary rule: SC/VSC/red-flag-affected
    is_valid = 1 if all(l['is_valid'] for l in laps_data) else 0
    
    # Find initial tyre age
    first_lap_data = next(l for l in laps_data if l['lap'] == start_lap)
    tyre_age_start = first_lap_data['tyre_life']
    if pd.isna(tyre_age_start):
        tyre_age_start = 0
    else:
        tyre_age_start = int(tyre_age_start)
        
    stint_id = f"{session_id}_{driver}_{stint_num}"
    
    cursor.execute('''
        INSERT OR IGNORE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (stint_id, session_id, driver, compound, start_lap, end_lap, tyre_age_start, is_valid))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest F1 telemetry data.")
    parser.add_argument("--season", type=int, choices=[2024, 2025], help="Specific season to ingest (2024 or 2025)")
    parser.add_argument("--round", type=int, help="Specific round to ingest (e.g., 1)")
    parser.add_argument("--limit", type=int, help="Limit number of races to ingest")
    
    args = parser.parse_args()
    
    seasons = [args.season] if args.season else [2024, 2025]
    
    print(f"Starting data ingestion for seasons: {seasons}...")
    ingest_data(seasons=seasons, limit_races=args.limit, target_round=args.round)
    print("Data ingestion complete.")
