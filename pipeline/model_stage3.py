"""
pipeline/model_stage3.py — Stage 3 Behavioral Modeling & Observational Attribution Coordinator.
Orchestrates genuine TCN training, behavioral representation extraction,
linear sensitivity decomposition, and active model registry updates in SQLite.
"""

import os
import sys
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.linear_model import Ridge
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
MODELS_DIR = os.path.join(BASE_DIR, 'models', 'stage3')

LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')

from pipeline.train_stage3_tcn import (
    train_tcn_model,
    BEHAVIORAL_FEATURES
)


def train_attribution_model(seed: int = 42):
    """
    Executes genuine Stage 3 TCN training and registers learned observational
    sensitivity coefficients in SQLite.
    """
    if not os.path.exists(LEDGER_PARQUET):
        print(f"Error: {LEDGER_PARQUET} not found. Run model_stage2.py first to generate ledger.", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(LAPS_PARQUET):
        print(f"Error: {LAPS_PARQUET} not found. Run features.py first to generate laps data.", file=sys.stderr)
        sys.exit(1)

    print("=== Stage 3 Phase A: Training Behavioral MultiTask TCN ===")
    tcn_result = train_tcn_model(seed=seed)
    model = tcn_result["model"]
    scaler = tcn_result["scaler"]
    version = tcn_result["version"]
    test_metrics = tcn_result["metrics"]

    print(f"\n=== Stage 3 Phase B: Observational Sensitivity Modeling ({version}) ===")
    laps_df = pd.read_parquet(LAPS_PARQUET)
    ledger_df = pd.read_parquet(LEDGER_PARQUET)

    # Lag structure: behavioral features at lap n predict residual at lap n+1
    laps_df = laps_df.copy()
    laps_df['target_lap'] = laps_df['lap_number'] + 1
    data = ledger_df.merge(
        laps_df,
        left_on=['stint_id', 'lap_number'],
        right_on=['stint_id', 'target_lap'],
        suffixes=('_ledger', '_feat'),
        how='inner'
    )
    
    valid_mask = (data['lap_number_ledger'] - data['lap_number_feat']) == 1
    if not valid_mask.all():
        data = data[valid_mask]

    # Get event_date and track_id from database for chronological split
    conn = sqlite3.connect(DB_PATH)
    event_dates_df = pd.read_sql_query("""
        SELECT s.stint_id, r.event_date, r.track_id
        FROM stints s
        JOIN sessions ses ON s.session_id = ses.session_id
        JOIN races r ON ses.race_id = r.race_id
    """, conn)
    conn.close()

    cols_to_use = [c for c in event_dates_df.columns if c not in data.columns or c == 'stint_id']
    data = data.merge(event_dates_df[cols_to_use], on='stint_id', how='left')

    features = BEHAVIORAL_FEATURES
    data = data.dropna(subset=features + ['residual'])

    X = data[features]
    y = data['residual']

    # Chronological split matching TCN
    event_dates = data['event_date']
    unique_dates = sorted(event_dates.dropna().unique())
    if len(unique_dates) > 1:
        split_idx = int(len(unique_dates) * 0.70)
        split_date = unique_dates[min(split_idx, len(unique_dates) - 1)]
        train_mask = event_dates <= split_date
        test_mask = event_dates > split_date
    else:
        split_idx = int(len(data) * 0.70)
        indices = np.arange(len(data))
        train_mask = pd.Series(indices <= split_idx, index=data.index)
        test_mask = pd.Series(indices > split_idx, index=data.index)

    X_train, X_test = X[train_mask], X[test_mask]
    y_train, y_test = y[train_mask], y[test_mask]

    # Global Linear Ridge Model for observational sensitivity decomposition
    ridge_model = Ridge(alpha=1.0)
    ridge_model.fit(X_train, y_train)

    preds_test = ridge_model.predict(X_test) if len(X_test) > 0 else ridge_model.predict(X_train)
    r2_held_out = r2_score(y_test, preds_test) if len(X_test) > 1 else r2_score(y_train, ridge_model.predict(X_train))
    mae_held_out = mean_absolute_error(y_test, preds_test) if len(X_test) > 0 else mean_absolute_error(y_train, ridge_model.predict(X_train))
    rmse_held_out = np.sqrt(mean_squared_error(y_test, preds_test)) if len(X_test) > 0 else np.sqrt(mean_squared_error(y_train, ridge_model.predict(X_train)))

    print(f"Global Sensitivity Decomposition -> Held-out R²: {r2_held_out:+.4f} | MAE: {mae_held_out:.4f} | RMSE: {rmse_held_out:.4f}")

    # Track-specific models where sufficient samples exist (>= 4 laps)
    track_models = {}
    for track in data['track_id'].dropna().unique():
        t_mask = data['track_id'] == track
        X_t = X[t_mask]
        y_t = y[t_mask]
        if len(X_t) >= 4:
            tm = Ridge(alpha=1.0)
            tm.fit(X_t, y_t)
            track_models[track] = tm

    # Final coefficients fit on full dataset for stable production serving
    final_model = Ridge(alpha=1.0)
    final_model.fit(X, y)

    print("\nLearned Observational Sensitivity Coefficients:")
    for feat, coef in zip(features, final_model.coef_):
        print(f"  {feat}: {coef:+.6f}")

    # Register in SQLite Model Registry
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Deactivate previous stage 3 models
    cursor.execute("UPDATE model_registry SET is_active = 0 WHERE stage = 3")

    # Insert newly trained Stage 3 model
    cursor.execute('''
        INSERT OR REPLACE INTO model_registry (model_version, stage, trained_at, held_out_metric, split_method, is_active)
        VALUES (?, 3, ?, ?, ?, 1)
    ''', (version, datetime.now().isoformat(), float(r2_held_out), 'chronological_by_race_weekend'))

    # Insert global coefficients
    for feature, coef in zip(features, final_model.coef_):
        cursor.execute('''
            INSERT OR REPLACE INTO model_coefficients (model_version, feature_name, coefficient, shape_function_ref, track_scope)
            VALUES (?, ?, ?, NULL, NULL)
        ''', (version, feature, float(coef)))

    # Insert track-scoped coefficients
    for track, tm in track_models.items():
        for feature, coef in zip(features, tm.coef_):
            cursor.execute('''
                INSERT OR REPLACE INTO model_coefficients (model_version, feature_name, coefficient, shape_function_ref, track_scope)
                VALUES (?, ?, ?, NULL, ?)
            ''', (version, feature, float(coef), track))

    conn.commit()
    conn.close()

    print(f"\n[OK] Stage 3 Active Model registered successfully ({version}).")
    return version


if __name__ == "__main__":
    print("Starting Stage 3 Attribution modeling (Phase 4)...")
    train_attribution_model()
    print("Stage 3 Attribution modeling complete.")
