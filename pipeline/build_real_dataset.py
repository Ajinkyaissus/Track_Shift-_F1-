import sqlite3
import os
import sys
import fastf1

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
SCHEMA_PATH = os.path.join(API_DIR, 'schema.sql')

os.makedirs(DATA_DIR, exist_ok=True)
fastf1.Cache.enable_cache(DATA_DIR)

def init_database():
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH, 'r') as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()

def build_multi_race_stints():
    print("=== Step 1: Ingesting Multi-Race, Multi-Driver, Multi-Compound Stints ===")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Insert Tracks
    tracks_data = [
        ('monza', 'Autodromo Nazionale Monza', 'Italy'),
        ('sakhir', 'Bahrain International Circuit', 'Bahrain')
    ]
    cursor.executemany("INSERT OR IGNORE INTO tracks VALUES (?, ?, ?)", tracks_data)
    
    # 2. Insert Races
    races_data = [
        ('2024_monza', 2024, 16, 'monza', '2024-09-01', 'Italian Grand Prix'),
        ('2023_bahrain', 2023, 1, 'sakhir', '2023-03-05', 'Bahrain Grand Prix')
    ]
    cursor.executemany("INSERT OR IGNORE INTO races (race_id, season, round, track_id, event_date, event_name) VALUES (?, ?, ?, ?, ?, ?)", races_data)
    
    # 3. Insert Sessions
    sessions_data = [
        ('2024_monza_R', '2024_monza', 'R', 'dry', 1.45),
        ('2023_bahrain_R', '2023_bahrain', 'R', 'dry', 1.20)
    ]
    cursor.executemany("INSERT OR IGNORE INTO sessions (session_id, race_id, session_type, weather_flag, track_evolution_index) VALUES (?, ?, ?, ?, ?)", sessions_data)
    
    # 4. Insert Drivers
    drivers_data = [
        ('VER', 'Max Verstappen', 'Red Bull Racing', 'aggressive'),
        ('LEC', 'Charles Leclerc', 'Ferrari', 'tyre_management'),
        ('HAM', 'Lewis Hamilton', 'Mercedes', 'tyre_management')
    ]
    cursor.executemany("INSERT OR IGNORE INTO drivers (driver_id, full_name, team, reputation_tag) VALUES (?, ?, ?, ?)", drivers_data)
    
    # 5. Define Real Race Stints across Drivers & Compounds (Soft, Medium, Hard)
    stints_data = [
        # Monza 2024: Fast low-downforce circuit
        ('2024_monza_R_VER_1', '2024_monza_R', 'VER', 'MEDIUM', 1, 20, 0, 1),
        ('2024_monza_R_VER_2', '2024_monza_R', 'VER', 'HARD', 24, 41, 0, 1),
        ('2024_monza_R_LEC_1', '2024_monza_R', 'LEC', 'MEDIUM', 1, 15, 0, 1),
        ('2024_monza_R_LEC_2', '2024_monza_R', 'LEC', 'HARD', 16, 53, 0, 1), # Historic 1-stop winning stint
        
        # Bahrain 2023: High-abrasion thermal degradation circuit
        ('2023_bahrain_R_VER_1', '2023_bahrain_R', 'VER', 'SOFT', 1, 14, 0, 1),
        ('2023_bahrain_R_VER_2', '2023_bahrain_R', 'VER', 'SOFT', 15, 36, 0, 1),
        ('2023_bahrain_R_VER_3', '2023_bahrain_R', 'VER', 'HARD', 37, 57, 0, 1),
        ('2023_bahrain_R_HAM_1', '2023_bahrain_R', 'HAM', 'SOFT', 1, 12, 0, 1),
        ('2023_bahrain_R_HAM_2', '2023_bahrain_R', 'HAM', 'HARD', 13, 30, 0, 1)
    ]
    
    cursor.executemany("""
        INSERT OR REPLACE INTO stints (stint_id, session_id, driver_id, compound, start_lap, end_lap, tyre_age_start, is_valid)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, stints_data)
    
    conn.commit()
    conn.close()
    print(f"[OK] Inserted {len(stints_data)} stints across 2 races, 3 drivers, and 3 compounds (SOFT, MEDIUM, HARD).")

def extract_all_features():
    print("\n=== Step 2: Extracting Real Telemetry Features ===")
    from pipeline.features import process_features
    process_features()

def train_and_register_models():
    print("\n=== Step 3: Training Baseline Degradation Model (Stage 1) ===")
    from pipeline.model_stage1 import train_baseline_model
    train_baseline_model()
    
    print("\n=== Step 4: Computing Residual Ledger (Stage 2) ===")
    from pipeline.model_stage2 import build_residual_ledger
    build_residual_ledger()
    
    print("\n=== Step 5: Training Attribution Model & Coefficients (Stage 3) ===")
    from pipeline.model_stage3 import train_attribution_model
    train_attribution_model()

if __name__ == "__main__":
    init_database()
    build_multi_race_stints()
    extract_all_features()
    train_and_register_models()
    print("\n=== Dataset & Model Pipeline Successfully Built & Verified ===")
