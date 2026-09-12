"""
trackshift/ingest/season.py — Multi-Season FastF1 Historical Data Ingestion Pipeline.

Supports:
- 2024 (Verified full season & migration)
- 2025 (Historical/Live calendar and completed sessions)

CLI Usage:
    python -m trackshift.ingest.season --year 2024
    python -m trackshift.ingest.season --year 2025
    python -m trackshift.ingest.season --year 2024 --event cota --session R --force
"""

import os
import sys
import argparse
import sqlite3
import datetime
import logging
import pandas as pd
import fastf1

# Ensure base dir is in path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
SCHEMA_PATH = os.path.join(API_DIR, 'schema.sql')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
GEOMETRY_PARQUET = os.path.join(DATA_DIR, 'circuit_geometry.parquet')

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("trackshift.ingest")

CIRCUIT_METADATA = {
    "monza": {"name": "Autodromo Nazionale Monza", "country": "Italy", "country_code": "IT", "location": "Monza", "lat": 45.6156, "lon": 9.2811, "rotation": 0.0},
    "spa": {"name": "Circuit de Spa-Francorchamps", "country": "Belgium", "country_code": "BE", "location": "Stavelot", "lat": 50.4372, "lon": 5.9714, "rotation": 0.0},
    "silverstone": {"name": "Silverstone Circuit", "country": "United Kingdom", "country_code": "GB", "location": "Silverstone", "lat": 52.0786, "lon": -1.0169, "rotation": 0.0},
    "monaco": {"name": "Circuit de Monaco", "country": "Monaco", "country_code": "MC", "location": "Monte Carlo", "lat": 43.7347, "lon": 7.4206, "rotation": 0.0},
    "hungaroring": {"name": "Hungaroring", "country": "Hungary", "country_code": "HU", "location": "Mogyoród", "lat": 47.5789, "lon": 19.2486, "rotation": 0.0},
    "bahrain": {"name": "Bahrain International Circuit", "country": "Bahrain", "country_code": "BH", "location": "Sakhir", "lat": 26.0325, "lon": 50.5106, "rotation": 0.0},
    "jeddah": {"name": "Jeddah Corniche Circuit", "country": "Saudi Arabia", "country_code": "SA", "location": "Jeddah", "lat": 21.6319, "lon": 39.1044, "rotation": 0.0},
    "abu_dhabi": {"name": "Yas Marina Circuit", "country": "United Arab Emirates", "country_code": "AE", "location": "Abu Dhabi", "lat": 24.4672, "lon": 54.6031, "rotation": 0.0},
    "cota": {"name": "Circuit of the Americas", "country": "United States", "country_code": "US", "location": "Austin", "lat": 30.1328, "lon": -97.6411, "rotation": 0.0},
    "miami": {"name": "Miami International Autodrome", "country": "United States", "country_code": "US", "location": "Miami", "lat": 25.9581, "lon": -80.2389, "rotation": 0.0},
    "las_vegas": {"name": "Las Vegas Strip Circuit", "country": "United States", "country_code": "US", "location": "Las Vegas", "lat": 36.1147, "lon": -115.1685, "rotation": 0.0},
    "interlagos": {"name": "Autódromo José Carlos Pace", "country": "Brazil", "country_code": "BR", "location": "São Paulo", "lat": -23.7036, "lon": -46.6997, "rotation": 0.0},
    "suzuka": {"name": "Suzuka International Racing Course", "country": "Japan", "country_code": "JP", "location": "Suzuka", "lat": 34.8431, "lon": 136.541, "rotation": 0.0},
    "singapore": {"name": "Marina Bay Street Circuit", "country": "Singapore", "country_code": "SG", "location": "Marina Bay", "lat": 1.2914, "lon": 103.864, "rotation": 0.0},
    "albert_park": {"name": "Albert Park Circuit", "country": "Australia", "country_code": "AU", "location": "Melbourne", "lat": -37.8497, "lon": 144.968, "rotation": 0.0},
    "baku": {"name": "Baku City Circuit", "country": "Azerbaijan", "country_code": "AZ", "location": "Baku", "lat": 40.3725, "lon": 49.8533, "rotation": 0.0},
    "catalunya": {"name": "Circuit de Barcelona-Catalunya", "country": "Spain", "country_code": "ES", "location": "Montmeló", "lat": 41.5700, "lon": 2.2611, "rotation": 0.0},
    "montreal": {"name": "Circuit Gilles Villeneuve", "country": "Canada", "country_code": "CA", "location": "Montreal", "lat": 45.5000, "lon": -73.5228, "rotation": 0.0},
    "red_bull_ring": {"name": "Red Bull Ring", "country": "Austria", "country_code": "AT", "location": "Spielberg", "lat": 47.2197, "lon": 14.7647, "rotation": 0.0},
    "zandvoort": {"name": "Circuit Zandvoort", "country": "Netherlands", "country_code": "NL", "location": "Zandvoort", "lat": 52.3888, "lon": 4.5409, "rotation": 0.0},
    "losail": {"name": "Lusail International Circuit", "country": "Qatar", "country_code": "QA", "location": "Lusail", "lat": 25.4900, "lon": 51.4542, "rotation": 0.0},
    "rodriguez": {"name": "Autódromo Hermanos Rodríguez", "country": "Mexico", "country_code": "MX", "location": "Mexico City", "lat": 19.4042, "lon": -99.0907, "rotation": 0.0},
    "shanghai": {"name": "Shanghai International Circuit", "country": "China", "country_code": "CN", "location": "Shanghai", "lat": 31.3389, "lon": 121.2200, "rotation": 0.0},
    "imola": {"name": "Autodromo Enzo e Dino Ferrari", "country": "Italy", "country_code": "IT", "location": "Imola", "lat": 44.3439, "lon": 11.7167, "rotation": 0.0}
}

def resolve_circuit_slug(event_name: str, location: str) -> str:
    ev_lower = event_name.lower()
    loc_lower = location.lower()
    
    if "spanish" in ev_lower or "barcelona" in loc_lower or "catalunya" in loc_lower:
        return "catalunya"
    if "monza" in ev_lower or "italian" in ev_lower:
        return "monza"
    if "belgian" in ev_lower or "spa-francorchamps" in ev_lower or "stavelot" in loc_lower or "spa" in ev_lower.split():
        return "spa"
    if "silverstone" in ev_lower or "british" in ev_lower:
        return "silverstone"
    if "monaco" in ev_lower:
        return "monaco"
    if "hungaroring" in ev_lower or "hungarian" in ev_lower:
        return "hungaroring"
    if "bahrain" in ev_lower or "sakhir" in loc_lower:
        return "bahrain"
    if "saudi" in ev_lower or "jeddah" in loc_lower:
        return "jeddah"
    if "abu dhabi" in ev_lower or "yas" in loc_lower:
        return "abu_dhabi"
    if "miami" in ev_lower or "miami" in loc_lower:
        return "miami"
    if "las vegas" in ev_lower or "vegas" in loc_lower:
        return "las_vegas"
    if "united states" in ev_lower or "austin" in loc_lower or "cota" in ev_lower:
        return "cota"
    if "são paulo" in ev_lower or "sao paulo" in ev_lower or "brazil" in ev_lower or "interlagos" in loc_lower:
        return "interlagos"
    if "japan" in ev_lower or "suzuka" in loc_lower:
        return "suzuka"
    if "singapore" in ev_lower or "marina" in loc_lower:
        return "singapore"
    if "australian" in ev_lower or "melbourne" in loc_lower or "albert" in loc_lower:
        return "albert_park"
    if "azerbaijan" in ev_lower or "baku" in loc_lower:
        return "baku"
    if "canadian" in ev_lower or "montreal" in loc_lower or "gilles" in loc_lower:
        return "montreal"
    if "austrian" in ev_lower or "spielberg" in loc_lower or "red bull" in loc_lower:
        return "red_bull_ring"
    if "dutch" in ev_lower or "zandvoort" in loc_lower:
        return "zandvoort"
    if "qatar" in ev_lower or "losail" in loc_lower or "lusail" in loc_lower:
        return "losail"
    if "mexico" in ev_lower or "rodriguez" in loc_lower:
        return "rodriguez"
    if "china" in ev_lower or "chinese" in ev_lower or "shanghai" in loc_lower:
        return "shanghai"
    if "emilia" in ev_lower or "imola" in loc_lower:
        return "imola"
        
    return loc_lower.replace(" ", "_")

def init_database():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    with open(SCHEMA_PATH, 'r') as f:
        schema = f.read()
    conn.executescript(schema)
    
    # Safe schema migrations for existing database
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE sessions ADD COLUMN status TEXT DEFAULT 'VERIFIED'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE races ADD COLUMN status TEXT DEFAULT 'COMPLETED'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE provenance ADD COLUMN data_version TEXT DEFAULT 'v1_real'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE provenance ADD COLUMN status TEXT DEFAULT 'VERIFIED'")
    except Exception:
        pass
        
    conn.commit()
    return conn


SUPPORTED_SEASONS = [2024, 2025]


def ingest_season(year: int, target_event: str = None, session_type: str = "R", force: bool = False, refresh: bool = False):
    if year not in SUPPORTED_SEASONS:
        raise ValueError(f"Unsupported season: {year}. TrackShift supports seasons: {SUPPORTED_SEASONS}")

    logger.info(f"=================================================================")
    logger.info(f"  TRACKSHIFT — INGESTING REAL {year} FORMULA 1 DATA")
    logger.info(f"=================================================================")
    
    fastf1.Cache.enable_cache(DATA_DIR)
    conn = init_database()
    cursor = conn.cursor()
    
    # 1. Register Season in seasons table
    cursor.execute("""
        INSERT OR REPLACE INTO seasons (year, total_rounds, status)
        VALUES (?, ?, ?)
    """, (year, 24 if year >= 2024 else 22, 'COMPLETED' if year <= 2024 else 'ACTIVE'))
    
    # 2. Fetch Event Schedule
    try:
        schedule = fastf1.get_event_schedule(year)
    except Exception as e:
        logger.error(f"Failed to fetch event schedule for {year}: {e}")
        conn.close()
        return False
        
    # Filter out testing rounds
    races = schedule[schedule['EventFormat'] != 'testing']
    
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    ingested_sessions_count = 0
    
    # Pre-register all calendar races for the season
    for _, event in races.iterrows():
        r_num = int(event['RoundNumber'])
        ev_name = str(event['EventName'])
        loc = str(event.get('Location', ''))
        c_id = resolve_circuit_slug(ev_name, loc)
        r_id = f"{year}_{c_id}"
        ev_date = event.get('EventDate', f'{year}-01-01')
        ev_date_s = ev_date.strftime('%Y-%m-%d') if hasattr(ev_date, 'strftime') else str(ev_date)[:10]
        
        c_meta = CIRCUIT_METADATA.get(c_id, {
            "name": ev_name,
            "country": event.get('Country', loc),
            "country_code": "",
            "location": loc,
            "lat": 0.0,
            "lon": 0.0,
            "rotation": 0.0
        })
        cursor.execute("""
            INSERT OR REPLACE INTO tracks (track_id, name, country, country_code, location, rotation, map_available, telemetry_available)
            VALUES (?, ?, ?, ?, ?, ?, 1, 1)
        """, (c_id, c_meta["name"], c_meta["country"], c_meta["country_code"], c_meta["location"], c_meta["rotation"]))

        cursor.execute("""
            INSERT OR IGNORE INTO races (race_id, season, round, track_id, event_date, event_name, status)
            VALUES (?, ?, ?, ?, ?, ?, 'UPCOMING')
        """, (r_id, year, r_num, c_id, ev_date_s, ev_name))
    conn.commit()

    for _, event in races.iterrows():
        round_num = int(event['RoundNumber'])
        event_name = str(event['EventName'])
        location = str(event.get('Location', ''))
        circuit_id = resolve_circuit_slug(event_name, location)
        race_id = f"{year}_{circuit_id}"
        session_id = f"{race_id}_{session_type}"
        event_date_val = event.get('EventDate', f'{year}-01-01')
        event_date_str = event_date_val.strftime('%Y-%m-%d') if hasattr(event_date_val, 'strftime') else str(event_date_val)[:10]

        # Filter if target event specified
        if target_event:
            target_slug = target_event.lower().replace(" ", "_")
            if target_slug not in circuit_id and target_slug not in event_name.lower():
                continue


        # Check incremental existence
        if not force:
            cursor.execute("SELECT status FROM sessions WHERE session_id = ? AND status = 'VERIFIED'", (session_id,))
            if cursor.fetchone():
                logger.info(f"  [Incremental] Session {session_id} already VERIFIED in database. Skipping download.")
                continue

        event_date_val = event.get('EventDate', f'{year}-01-01')
        event_date_str = event_date_val.strftime('%Y-%m-%d') if hasattr(event_date_val, 'strftime') else str(event_date_val)[:10]

        now_dt = datetime.datetime.now(datetime.timezone.utc).date()
        is_future = False
        if hasattr(event_date_val, 'date'):
            is_future = event_date_val.date() > now_dt
        elif isinstance(event_date_val, str) and len(event_date_val) >= 10:
            try:
                is_future = datetime.date.fromisoformat(event_date_val[:10]) > now_dt
            except Exception:
                pass

        if is_future:
            logger.info(f"  [UPCOMING] {event_name} ({year} R{round_num}) is scheduled for {event_date_str}.")
            cursor.execute("""
                INSERT OR REPLACE INTO races (race_id, season, round, track_id, event_date, event_name, status)
                VALUES (?, ?, ?, ?, ?, ?, 'UPCOMING')
            """, (race_id, year, round_num, circuit_id, event_date_str, event_name))
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (session_id, race_id, session_type, weather_flag, track_evolution_index, status)
                VALUES (?, ?, ?, 'unknown', NULL, 'UPCOMING')
            """, (session_id, race_id, session_type))
            conn.commit()
            continue

        logger.info(f"--> Ingesting {event_name} ({year} Round {round_num} [{session_type}]) Circuit: {circuit_id} ...")
        
        # Load FastF1 Session
        try:
            sess = fastf1.get_session(year, round_num, session_type)
            sess.load(telemetry=True, laps=True, weather=True)
        except Exception as e:

            logger.warning(f"  [FASTF1 UNAVAILABLE] Could not load {year} R{round_num} {session_type}: {e}")
            cursor.execute("""
                INSERT OR REPLACE INTO races (race_id, season, round, track_id, event_date, event_name, status)
                VALUES (?, ?, ?, ?, ?, ?, 'NO_DATA')
            """, (race_id, year, round_num, circuit_id, event_date_str, event_name))
            cursor.execute("""
                INSERT OR REPLACE INTO sessions (session_id, race_id, session_type, weather_flag, track_evolution_index, status)
                VALUES (?, ?, ?, 'unknown', NULL, 'NO_DATA')
            """, (session_id, race_id, session_type))
            cursor.execute("""
                INSERT INTO provenance (source, season, event_name, round_number, circuit_id, session_type, session_date, retrieved_at, data_version, status, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'v1_real', 'NO_DATA', ?)
            """, ("FastF1", year, event_name, round_num, circuit_id, session_type, event_date_str, now_iso, str(e)))
            conn.commit()
            continue

        laps = getattr(sess, 'laps', None)
        if laps is None or laps.empty:
            logger.warning(f"  [NO LAPS] Session {session_id} has empty laps.")
            continue

        # Register Race
        cursor.execute("""
            INSERT OR REPLACE INTO races (race_id, season, round, track_id, event_date, event_name, status)
            VALUES (?, ?, ?, ?, ?, ?, 'COMPLETED')
        """, (race_id, year, round_num, circuit_id, event_date_str, event_name))

        # Weather analysis
        weather_flag = 'dry'
        if hasattr(sess, 'weather_data') and not sess.weather_data.empty:
            if 'Rainfall' in sess.weather_data.columns:
                rf = sess.weather_data['Rainfall']
                if rf.max() > 0:
                    weather_flag = 'wet' if rf.min() > 0 else 'mixed'

        # Track Evolution Index
        track_evolution_index = 1.00
        green_laps = laps[laps['TrackStatus'] == '1'].dropna(subset=['LapTime'])
        if len(green_laps) >= 10:
            sorted_laps = green_laps.sort_values('LapStartTime')
            n_q = max(1, len(sorted_laps) // 5)
            first_q = sorted_laps.head(n_q)['LapTime'].dt.total_seconds().median()
            last_q = sorted_laps.tail(n_q)['LapTime'].dt.total_seconds().median()
            if pd.notna(first_q) and pd.notna(last_q):
                track_evolution_index = round(float(first_q - last_q), 2)

        # Register Session
        cursor.execute("""
            INSERT OR REPLACE INTO sessions (session_id, race_id, session_type, weather_flag, track_evolution_index, status)
            VALUES (?, ?, ?, ?, ?, 'VERIFIED')
        """, (session_id, race_id, session_type, weather_flag, track_evolution_index))

        # Store Detailed Weather Rows
        if hasattr(sess, 'weather_data') and not sess.weather_data.empty:
            cursor.execute("DELETE FROM weather WHERE session_id = ?", (session_id,))
            for _, w_row in sess.weather_data.iterrows():
                time_val = str(w_row.get('Time', ''))
                cursor.execute("""
                    INSERT INTO weather (session_id, air_temp, track_temp, humidity, rainfall, wind_speed, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    session_id,
                    float(w_row.get('AirTemp', 0.0)) if pd.notna(w_row.get('AirTemp')) else None,
                    float(w_row.get('TrackTemp', 0.0)) if pd.notna(w_row.get('TrackTemp')) else None,
                    float(w_row.get('Humidity', 0.0)) if pd.notna(w_row.get('Humidity')) else None,
                    float(w_row.get('Rainfall', 0.0)) if pd.notna(w_row.get('Rainfall')) else None,
                    float(w_row.get('WindSpeed', 0.0)) if pd.notna(w_row.get('WindSpeed')) else None,
                    time_val
                ))

        # Ingest Drivers for this session dynamically
        session_drivers_list = [d for d in pd.unique(laps['Driver']) if pd.notna(d) and len(str(d)) == 3]
        cursor.execute("DELETE FROM session_drivers WHERE session_id = ?", (session_id,))
        
        for d in session_drivers_list:
            d_name = d
            d_team = "F1 Team"
            d_num = None
            d_nat = "UNK"
            try:
                d_info = sess.get_driver(d)
                d_name = d_info.get('FullName', d)
                d_team = d_info.get('TeamName', 'F1 Team')
                d_num = int(d_info.get('DriverNumber')) if pd.notna(d_info.get('DriverNumber')) else None
                d_nat = d_info.get('CountryCode', 'UNK')
            except Exception:
                pass
                
            reputation = 'tyre_management' if d in ['LEC', 'HAM', 'PER', 'SAI'] else ('aggressive' if d in ['VER', 'NOR', 'RUS', 'PIA'] else 'neutral')
            
            cursor.execute("""
                INSERT OR REPLACE INTO drivers (driver_id, full_name, team, reputation_tag)
                VALUES (?, ?, ?, ?)
            """, (d, d_name, d_team, reputation))
            
            cursor.execute("""
                INSERT OR REPLACE INTO session_drivers (session_id, driver_id, driver_number, abbreviation, full_name, team, country_code, grid_position, finish_position, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, 'CLASSIFIED')
            """, (session_id, d, d_num, d, d_name, d_team, d_nat))

        # Stints & Pit Stop Ingestion
        cursor.execute("DELETE FROM stints WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM pit_stops WHERE session_id = ?", (session_id,))
        
        for driver in session_drivers_list:
            d_laps = laps[laps['Driver'] == driver].sort_values('LapNumber')
            if d_laps.empty:
                continue
                
            stint_num = 1
            current_stint_laps = []
            current_compound = None
            stop_count = 0
            
            for _, lap in d_laps.iterrows():
                comp = lap['Compound']
                lap_num = int(lap['LapNumber'])
                
                # Verified Pit Stop Detection
                if pd.notna(lap.get('PitInTime')) or (pd.notna(lap.get('PitOutTime')) and lap_num > 1):
                    stop_count += 1
                    pit_in_s = lap['PitInTime'].total_seconds() if pd.notna(lap.get('PitInTime')) and hasattr(lap['PitInTime'], 'total_seconds') else None
                    pit_out_s = lap['PitOutTime'].total_seconds() if pd.notna(lap.get('PitOutTime')) and hasattr(lap['PitOutTime'], 'total_seconds') else None
                    dur = round(pit_out_s - pit_in_s, 2) if (pit_out_s is not None and pit_in_s is not None and pit_out_s > pit_in_s) else 24.5
                    
                    cursor.execute("""
                        INSERT OR REPLACE INTO pit_stops (session_id, driver_id, lap_number, stop_number, duration, pit_in_time, pit_out_time)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (session_id, driver, lap_num, stop_count, dur, pit_in_s, pit_out_s))
                
                if pd.isna(comp) or comp not in ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']:
                    continue
                    
                if current_compound is None:
                    current_compound = comp
                    
                if comp != current_compound:
                    if len(current_stint_laps) >= 3:
                        stint_id = f"{session_id}_{driver}_{stint_num}"
                        s_lap = min(l['lap'] for l in current_stint_laps)
                        e_lap = max(l['lap'] for l in current_stint_laps)
                        age_start = current_stint_laps[0]['tyre_life'] if pd.notna(current_stint_laps[0]['tyre_life']) else 0
                        cursor.execute("""
                            INSERT OR REPLACE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        """, (stint_id, session_id, driver, current_compound, s_lap, e_lap, int(age_start)))
                        stint_num += 1
                    current_stint_laps = []
                    current_compound = comp
                    
                is_green = 1 if lap['TrackStatus'] == '1' else 0
                current_stint_laps.append({'lap': lap_num, 'tyre_life': lap.get('TyreLife', 0), 'is_valid': is_green})
                
                if pd.notna(lap.get('PitInTime')):
                    if len(current_stint_laps) >= 3:
                        stint_id = f"{session_id}_{driver}_{stint_num}"
                        s_lap = min(l['lap'] for l in current_stint_laps)
                        e_lap = max(l['lap'] for l in current_stint_laps)
                        age_start = current_stint_laps[0]['tyre_life'] if pd.notna(current_stint_laps[0]['tyre_life']) else 0
                        cursor.execute("""
                            INSERT OR REPLACE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
                            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                        """, (stint_id, session_id, driver, current_compound, s_lap, e_lap, int(age_start)))
                        stint_num += 1
                    current_stint_laps = []
                    current_compound = None
                    
            if len(current_stint_laps) >= 3 and current_compound is not None:
                stint_id = f"{session_id}_{driver}_{stint_num}"
                s_lap = min(l['lap'] for l in current_stint_laps)
                e_lap = max(l['lap'] for l in current_stint_laps)
                age_start = current_stint_laps[0]['tyre_life'] if pd.notna(current_stint_laps[0]['tyre_life']) else 0
                cursor.execute("""
                    INSERT OR REPLACE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (stint_id, session_id, driver, current_compound, s_lap, e_lap, int(age_start)))

        # Record Provenance
        cursor.execute("""
            INSERT INTO provenance (source, season, event_name, round_number, circuit_id, session_type, session_date, retrieved_at, data_version, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'v1_real', 'VERIFIED', ?)
        """, ("FastF1", year, event_name, round_num, circuit_id, session_type, event_date_str, now_iso, f"Ingested {len(session_drivers_list)} drivers, weather={weather_flag}, evo={track_evolution_index}"))
        
        conn.commit()
        ingested_sessions_count += 1
        logger.info(f"  [SUCCESS] Ingested {session_id} ({len(session_drivers_list)} drivers, {len(laps)} laps)")

    conn.close()
    logger.info(f"Finished {year} ingestion. Ingested {ingested_sessions_count} sessions.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TrackShift Multi-Season FastF1 Historical Data Ingestion")
    parser.add_argument("--year", type=int, required=True, choices=[2024, 2025], help="F1 Season Year (2024 or 2025)")
    parser.add_argument("--event", type=str, default=None, help="Optional event filter (e.g. cota, monza, monaco)")
    parser.add_argument("--session", type=str, default="R", help="Session type: R (Race), Q (Qualifying), FP1, etc.")
    parser.add_argument("--force", action="store_true", help="Force re-ingest even if session exists")
    parser.add_argument("--refresh", action="store_true", help="Refresh FastF1 cache")
    
    args = parser.parse_args()
    ingest_season(args.year, target_event=args.event, session_type=args.session, force=args.force, refresh=args.refresh)
