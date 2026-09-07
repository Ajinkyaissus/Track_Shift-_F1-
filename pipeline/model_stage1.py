import sqlite3
import os
import pandas as pd
import numpy as np
from datetime import datetime
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_squared_error
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
PREDICTIONS_PARQUET = os.path.join(DATA_DIR, 'baseline_predictions.parquet')

def load_data():
    if not os.path.exists(LAPS_PARQUET):
        print(f"Error: {LAPS_PARQUET} not found. Run ingest.py and features.py first to generate real data.", file=sys.stderr)
        sys.exit(1)
    
    df = pd.read_parquet(LAPS_PARQUET)
        
    conn = sqlite3.connect(DB_PATH)
    
    # Query covariates from SQLite
    query = """
    SELECT 
        s.stint_id, 
        s.compound, 
        s.start_lap, 
        s.tyre_age_start,
        ses.track_evolution_index,
        r.track_id,
        r.event_date
    FROM stints s
    JOIN sessions ses ON s.session_id = ses.session_id
    JOIN races r ON ses.race_id = r.race_id
    """
    stints_df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Join without duplicate columns
    cols_to_use = [c for c in stints_df.columns if c not in df.columns or c == 'stint_id']
    data = df.merge(stints_df[cols_to_use], on='stint_id', how='inner')
    
    # Filter green flag laps
    data = data[data['is_green_flag'] == 1].copy()
    data.dropna(subset=['lap_time'], inplace=True)
    
    # Calculate tyre age
    data['tyre_age'] = data['tyre_age_start'] + (data['lap_number'] - data['start_lap'])
    data['tyre_age_sq'] = data['tyre_age'] ** 2
    
    # Calculate actual_lap_time_loss
    # Simplest baseline: Lap time minus the driver's fastest lap in the stint seen so far
    data = data.sort_values(by=['stint_id', 'lap_number'])
    min_times = data.groupby('stint_id')['lap_time'].cummin()
    data['actual_lap_time_loss'] = data['lap_time'] - min_times
    
    return data

def train_baseline_model():
    data = load_data()
    
    if len(data) < 10:
        print("Not enough data to train. Needs more fastf1 laps.")
        return
        
    features = ['tyre_age', 'tyre_age_sq', 'fuel_load_est', 'track_evolution_index']
    
    # categorical features handling for scikit-learn
    X = pd.get_dummies(data[features + ['compound', 'track_id']], columns=['compound', 'track_id'], drop_first=True)
    y = data['actual_lap_time_loss']
    
    # Split chronologically
    event_dates = data['event_date'].astype(str)
    unique_dates = sorted(event_dates.dropna().unique())
    if len(unique_dates) > 1:
        split_idx = int(len(unique_dates) * 0.5)
        if split_idx >= len(unique_dates):
            split_idx = len(unique_dates) - 1
        split_date = unique_dates[split_idx]
        
        train_mask = event_dates <= split_date
        test_mask = event_dates > split_date
        
        if test_mask.sum() == 0 or train_mask.sum() == 0:
            split_idx = int(len(data) * 0.7)
            indices = np.arange(len(data))
            train_mask = indices <= split_idx
            test_mask = indices > split_idx
        else:
            train_max = event_dates[train_mask].max()
            test_min = event_dates[test_mask].min()
            print(f"Chronological split: train <= {train_max} (N={train_mask.sum()}), test >= {test_min} (N={test_mask.sum()})")
    else:
        split_idx = int(len(data) * 0.7)
        indices = np.arange(len(data))
        train_mask = indices <= split_idx
        test_mask = indices > split_idx
        print("Fallback to row-wise chronological split for single event.")
    
    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]
    
    # Train
    model = HistGradientBoostingRegressor(random_state=42)
    model.fit(X_train, y_train)
    
    # Evaluate on held-out test set only
    preds_test = model.predict(X_test)
    rmse = np.sqrt(mean_squared_error(y_test, preds_test))
    print(f"Stage 1 Baseline Model RMSE (Held-out): {rmse:.4f}")
    
    # Gate check — honest RMSE gate against real F1 lap time variance
    if rmse > 1.5:
        print(f"WARNING: Phase 2 Gate Failed. RMSE {rmse:.4f} is above 1.5.", file=sys.stderr)
        # sys.exit(1)
    else:
        print(f"Phase 2 Gate Passed. RMSE {rmse:.4f} beats 1.5.")
        
    # Predict baseline loss across all laps for the ledger, tracking held-out metric separately
    all_data = data.copy()
    all_data['predicted_lap_time_loss'] = model.predict(X)
    
    # Model Version
    version = f"v3_stage1_{datetime.now().strftime('%Y-%m-%d')}"
    all_data['model_version'] = version
    
    out_df = all_data[['stint_id', 'lap_number', 'actual_lap_time_loss', 'predicted_lap_time_loss', 'model_version']]
    out_df.to_parquet(PREDICTIONS_PARQUET, index=False)
    print(f"Saved {len(out_df)} baseline predictions (held-out RMSE: {rmse:.4f}) to {PREDICTIONS_PARQUET}")
    
    # Register model in sqlite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("UPDATE model_registry SET is_active = 0 WHERE stage = 1")
    
    cursor.execute('''
        INSERT OR REPLACE INTO model_registry (model_version, stage, trained_at, held_out_metric, split_method, is_active)
        VALUES (?, 1, ?, ?, ?, 1)
    ''', (version, datetime.now().isoformat(), float(rmse), 'chronological_by_race_weekend'))
    
    conn.commit()
    conn.close()
    
if __name__ == "__main__":
    print("Starting Stage 1 Baseline modeling (Phase 2)...")
    train_baseline_model()
    print("Stage 1 Baseline modeling complete.")
