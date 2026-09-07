import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "api" / "tyredebt.db"

def test_database_model_provenance():
    assert DB_PATH.exists(), "tyredebt.db does not exist"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check model registry
    cursor.execute("SELECT model_version, stage, is_active, held_out_metric, split_method FROM model_registry WHERE is_active = 1")
    rows = cursor.fetchall()
    assert len(rows) >= 2, "Both Stage 1 and Stage 3 active models must be registered"
    
    stages = [r[1] for r in rows]
    assert 1 in stages
    assert 3 in stages
    
    # Check coefficients in Stage 3
    cursor.execute("""
        SELECT mc.feature_name, mc.coefficient 
        FROM model_coefficients mc
        JOIN model_registry mr ON mc.model_version = mr.model_version
        WHERE mr.is_active = 1 AND mr.stage = 3
    """)
    coef_rows = cursor.fetchall()
    assert len(coef_rows) >= 4, "Stage 3 must have at least 4 active learned coefficients"
    
    for feat, coef in coef_rows:
        assert isinstance(coef, (int, float))
        assert not (coef == 0.45 and feat == "braking_aggression"), "Hardcoded [0.45, -0.30...] must not exist!"
    
    conn.close()

def test_multi_stint_dataset_integrity():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT DISTINCT r.race_id FROM stints s JOIN sessions ses ON s.session_id = ses.session_id JOIN races r ON ses.race_id = r.race_id")
    races = cursor.fetchall()
    assert len(races) >= 2, f"Expected at least 2 distinct Grand Prix sessions, got {len(races)}"
    
    cursor.execute("SELECT DISTINCT driver_id FROM stints")
    drivers = cursor.fetchall()
    assert len(drivers) >= 3, f"Expected at least 3 distinct drivers, got {len(drivers)}"
    
    cursor.execute("SELECT DISTINCT compound FROM stints")
    compounds = cursor.fetchall()
    assert len(compounds) >= 2, f"Expected multiple tyre compounds, got {len(compounds)}"
    
    cursor.execute("SELECT COUNT(*) FROM stints")
    stint_count = cursor.fetchone()[0]
    assert stint_count >= 6, f"Expected at least 6 stints, got {stint_count}"
    
    conn.close()
    
    # Check parquet dataset
    parquet_path = DB_PATH.parent.parent / "data" / "laps.parquet"
    assert parquet_path.exists(), "laps.parquet does not exist"
    import pandas as pd
    df = pd.read_parquet(parquet_path)
    assert len(df) >= 100, f"Expected >= 100 laps in dataset, got {len(df)}"
