"""
pipeline/circuit_geometry.py — Extract real F1 circuit geometry and corner positions
directly from FastF1 sessions (CircuitInfo & reference telemetry traces) for all 24 Formula 1 circuits.
"""
import os
import sys
import sqlite3
import pandas as pd
import numpy as np
import fastf1

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
SCHEMA_PATH = os.path.join(API_DIR, 'schema.sql')
GEOMETRY_PARQUET = os.path.join(DATA_DIR, 'circuit_geometry.parquet')

# All 24 Universal Formula 1 Circuits Specification
CIRCUITS_SPEC = [
    {
        "circuit_id": "bahrain",
        "name": "Bahrain International Circuit",
        "country": "Bahrain",
        "country_code": "BH",
        "location": "Sakhir",
        "season": 2024,
        "round": 1,
        "session_type": "R"
    },
    {
        "circuit_id": "jeddah",
        "name": "Jeddah Corniche Circuit",
        "country": "Saudi Arabia",
        "country_code": "SA",
        "location": "Jeddah",
        "season": 2024,
        "round": 2,
        "session_type": "R"
    },
    {
        "circuit_id": "albert_park",
        "name": "Albert Park Circuit",
        "country": "Australia",
        "country_code": "AU",
        "location": "Melbourne",
        "season": 2024,
        "round": 3,
        "session_type": "R"
    },
    {
        "circuit_id": "suzuka",
        "name": "Suzuka International Racing Course",
        "country": "Japan",
        "country_code": "JP",
        "location": "Suzuka",
        "season": 2024,
        "round": 4,
        "session_type": "R"
    },
    {
        "circuit_id": "shanghai",
        "name": "Shanghai International Circuit",
        "country": "China",
        "country_code": "CN",
        "location": "Shanghai",
        "season": 2024,
        "round": 5,
        "session_type": "R"
    },
    {
        "circuit_id": "miami",
        "name": "Miami International Autodrome",
        "country": "United States",
        "country_code": "US",
        "location": "Miami",
        "season": 2024,
        "round": 6,
        "session_type": "R"
    },
    {
        "circuit_id": "imola",
        "name": "Autodromo Enzo e Dino Ferrari",
        "country": "Italy",
        "country_code": "IT",
        "location": "Imola",
        "season": 2024,
        "round": 7,
        "session_type": "R"
    },
    {
        "circuit_id": "monaco",
        "name": "Circuit de Monaco",
        "country": "Monaco",
        "country_code": "MC",
        "location": "Monte Carlo",
        "season": 2024,
        "round": 8,
        "session_type": "R"
    },
    {
        "circuit_id": "montreal",
        "name": "Circuit Gilles Villeneuve",
        "country": "Canada",
        "country_code": "CA",
        "location": "Montreal",
        "season": 2024,
        "round": 9,
        "session_type": "R"
    },
    {
        "circuit_id": "catalunya",
        "name": "Circuit de Barcelona-Catalunya",
        "country": "Spain",
        "country_code": "ES",
        "location": "Montmeló",
        "season": 2024,
        "round": 10,
        "session_type": "R"
    },
    {
        "circuit_id": "red_bull_ring",
        "name": "Red Bull Ring",
        "country": "Austria",
        "country_code": "AT",
        "location": "Spielberg",
        "season": 2024,
        "round": 11,
        "session_type": "R"
    },
    {
        "circuit_id": "silverstone",
        "name": "Silverstone Circuit",
        "country": "United Kingdom",
        "country_code": "GB",
        "location": "Silverstone",
        "season": 2024,
        "round": 12,
        "session_type": "R"
    },
    {
        "circuit_id": "hungaroring",
        "name": "Hungaroring",
        "country": "Hungary",
        "country_code": "HU",
        "location": "Budapest",
        "season": 2024,
        "round": 13,
        "session_type": "R"
    },
    {
        "circuit_id": "spa",
        "name": "Circuit de Spa-Francorchamps",
        "country": "Belgium",
        "country_code": "BE",
        "location": "Spa-Francorchamps",
        "season": 2024,
        "round": 14,
        "session_type": "R"
    },
    {
        "circuit_id": "zandvoort",
        "name": "Circuit Zandvoort",
        "country": "Netherlands",
        "country_code": "NL",
        "location": "Zandvoort",
        "season": 2024,
        "round": 15,
        "session_type": "R"
    },
    {
        "circuit_id": "monza",
        "name": "Autodromo Nazionale Monza",
        "country": "Italy",
        "country_code": "IT",
        "location": "Monza",
        "season": 2024,
        "round": 16,
        "session_type": "R"
    },
    {
        "circuit_id": "baku",
        "name": "Baku City Circuit",
        "country": "Azerbaijan",
        "country_code": "AZ",
        "location": "Baku",
        "season": 2024,
        "round": 17,
        "session_type": "R"
    },
    {
        "circuit_id": "singapore",
        "name": "Marina Bay Street Circuit",
        "country": "Singapore",
        "country_code": "SG",
        "location": "Marina Bay",
        "season": 2024,
        "round": 18,
        "session_type": "R"
    },
    {
        "circuit_id": "cota",
        "name": "Circuit of the Americas",
        "country": "United States",
        "country_code": "US",
        "location": "Austin",
        "season": 2024,
        "round": 19,
        "session_type": "R"
    },
    {
        "circuit_id": "rodriguez",
        "name": "Autódromo Hermanos Rodríguez",
        "country": "Mexico",
        "country_code": "MX",
        "location": "Mexico City",
        "season": 2024,
        "round": 20,
        "session_type": "R"
    },
    {
        "circuit_id": "interlagos",
        "name": "Autodromo Jose Carlos Pace",
        "country": "Brazil",
        "country_code": "BR",
        "location": "Sao Paulo",
        "season": 2024,
        "round": 21,
        "session_type": "R"
    },
    {
        "circuit_id": "las_vegas",
        "name": "Las Vegas Strip Circuit",
        "country": "United States",
        "country_code": "US",
        "location": "Las Vegas",
        "season": 2024,
        "round": 22,
        "session_type": "R"
    },
    {
        "circuit_id": "losail",
        "name": "Lusail International Circuit",
        "country": "Qatar",
        "country_code": "QA",
        "location": "Lusail",
        "season": 2024,
        "round": 23,
        "session_type": "R"
    },
    {
        "circuit_id": "abu_dhabi",
        "name": "Yas Marina Circuit",
        "country": "United Arab Emirates",
        "country_code": "AE",
        "location": "Yas Island",
        "season": 2024,
        "round": 24,
        "session_type": "R"
    }
]

def rotate_points(x, y, angle_degrees):
    """Rotate points counter-clockwise by angle in degrees"""
    rad = np.radians(angle_degrees)
    cos_a, sin_a = np.cos(rad), np.sin(rad)
    x_rot = x * cos_a - y * sin_a
    y_rot = x * sin_a + y * cos_a
    return x_rot, y_rot

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if tracks table needs migration
    cursor.execute("PRAGMA table_info(tracks)")
    cols = [r[1] for r in cursor.fetchall()]
    if 'country_code' not in cols:
        cursor.execute("DROP TABLE IF EXISTS circuit_corners")
        cursor.execute("DROP TABLE IF EXISTS tracks")
        
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
        
    conn.commit()
    conn.close()

def extract_and_store_circuit_geometry():
    print("=================================================================")
    print("  EXTRACTING REAL F1 CIRCUIT GEOMETRY (ALL 24 CALENDAR CIRCUITS) ")
    print("=================================================================")
    init_db()
    fastf1.Cache.enable_cache(DATA_DIR)
    
    # Load existing geometry if available to merge
    existing_geom = {}
    if os.path.exists(GEOMETRY_PARQUET):
        try:
            old_df = pd.read_parquet(GEOMETRY_PARQUET)
            for cid, grp in old_df.groupby('circuit_id'):
                existing_geom[cid] = grp
        except Exception as e:
            print(f"Note: Could not read existing geometry parquet: {e}")
            
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    all_trace_points = []
    
    for spec in CIRCUITS_SPEC:
        cid = spec["circuit_id"]
        season = spec["season"]
        rnd = spec["round"]
        stype = spec["session_type"]
        print(f"\n[Geometry] Loading FastF1 session: {spec['name']} ({season} R{rnd} {stype})...")
        
        extracted = False
        try:
            sess = fastf1.get_session(season, rnd, stype)
            sess.load(telemetry=True, laps=True, weather=False)
            
            # 1. Circuit Info & Corners
            circuit_info = sess.get_circuit_info()
            rotation = float(circuit_info.rotation) if circuit_info and hasattr(circuit_info, 'rotation') else 0.0
            
            # 2. Reference Lap Trace
            fastest_lap = sess.laps.pick_fastest()
            if fastest_lap is None or pd.isna(fastest_lap['LapTime']):
                valid_laps = sess.laps.dropna(subset=['LapTime'])
                fastest_lap = valid_laps.iloc[0] if len(valid_laps) > 0 else sess.laps.iloc[0]
                
            tel = fastest_lap.get_telemetry()
            
            # Extract track trace
            trace_df = tel[['X', 'Y', 'Distance', 'Speed', 'Throttle', 'Brake']].dropna(subset=['X', 'Y']).copy()
            trace_df['circuit_id'] = cid
            trace_df['point_order'] = np.arange(len(trace_df))
            
            # Compute normalized / rotated bounding box
            x_rot, y_rot = rotate_points(trace_df['X'].values, trace_df['Y'].values, rotation)
            trace_df['x_rot'] = x_rot
            trace_df['y_rot'] = y_rot
            
            all_trace_points.append(trace_df)
            extracted = True
            
            # Save track to SQLite
            cursor.execute("""
                INSERT OR REPLACE INTO tracks (track_id, name, country, country_code, location, rotation, map_available, telemetry_available)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            """, (cid, spec["name"], spec["country"], spec["country_code"], spec["location"], rotation))
            
            # Save corners to SQLite
            cursor.execute("DELETE FROM circuit_corners WHERE circuit_id = ?", (cid,))
            if circuit_info and hasattr(circuit_info, 'corners') and not circuit_info.corners.empty:
                for _, c_row in circuit_info.corners.iterrows():
                    c_num = int(c_row['Number']) if pd.notna(c_row.get('Number')) else 0
                    c_let = str(c_row.get('Letter', '')) if pd.notna(c_row.get('Letter')) else ''
                    c_x = float(c_row['X'])
                    c_y = float(c_row['Y'])
                    c_ang = float(c_row['Angle']) if pd.notna(c_row.get('Angle')) else 0.0
                    c_dist = float(c_row['Distance']) if pd.notna(c_row.get('Distance')) else 0.0
                    
                    cursor.execute("""
                        INSERT INTO circuit_corners (circuit_id, corner_number, corner_letter, x, y, angle, distance)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (cid, c_num, c_let, c_x, c_y, c_ang, c_dist))
                    
                print(f"  -> Extracted {len(trace_df)} track points, {len(circuit_info.corners)} corners, rotation={rotation} deg.")
            else:
                print(f"  -> Extracted {len(trace_df)} track points (0 corner records), rotation={rotation} deg.")
                
        except Exception as e:
            print(f"  [Warning] FastF1 extraction for {cid} error: {e}")
            if cid in existing_geom:
                print(f"  -> Preserving existing {len(existing_geom[cid])} geometry points for {cid}.")
                all_trace_points.append(existing_geom[cid])
                cursor.execute("""
                    INSERT OR REPLACE INTO tracks (track_id, name, country, country_code, location, rotation, map_available, telemetry_available)
                    VALUES (?, ?, ?, ?, ?, 0, 1, 1)
                """, (cid, spec["name"], spec["country"], spec["country_code"], spec["location"]))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO tracks (track_id, name, country, country_code, location, rotation, map_available, telemetry_available)
                    VALUES (?, ?, ?, ?, ?, 0, 1, 1)
                """, (cid, spec["name"], spec["country"], spec["country_code"], spec["location"]))
                
    conn.commit()
    conn.close()
    
    if all_trace_points:
        full_geom_df = pd.concat(all_trace_points, ignore_index=True)
        # Drop duplicates by circuit_id & point_order if any
        full_geom_df = full_geom_df.drop_duplicates(subset=['circuit_id', 'point_order'])
        full_geom_df.to_parquet(GEOMETRY_PARQUET, index=False)
        print(f"\n[OK] Successfully saved {len(full_geom_df)} total geometry points across {full_geom_df['circuit_id'].nunique()} circuits to {GEOMETRY_PARQUET}")
    else:
        print("[Warning] No geometry points extracted.")

if __name__ == "__main__":
    extract_and_store_circuit_geometry()
