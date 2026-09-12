"""
scripts/diagnose_stage1.py — Deep Forensic Analysis of Stage 1 Baseline Model.
"""

import os
import sys
import sqlite3
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')

LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
PREDICTIONS_PARQUET = os.path.join(DATA_DIR, 'baseline_predictions.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')


def analyze_dataset():
    print("=" * 80)
    print(" STAGE 1 BASELINE MODEL DATASET FORENSIC AUDIT")
    print("=" * 80)

    laps_df = pd.read_parquet(LAPS_PARQUET)
    preds_df = pd.read_parquet(PREDICTIONS_PARQUET)
    ledger_df = pd.read_parquet(LEDGER_PARQUET)

    conn = sqlite3.connect(DB_PATH)
    stints_df = pd.read_sql_query("""
        SELECT s.stint_id, s.session_id, s.driver_id, s.compound, s.start_lap, s.end_lap, s.tyre_age_start,
               ses.track_evolution_index, ses.session_type, r.track_id, r.event_date, r.season
        FROM stints s
        JOIN sessions ses ON s.session_id = ses.session_id
        JOIN races r ON ses.race_id = r.race_id
    """, conn)
    conn.close()

    cols_to_use = [c for c in stints_df.columns if c not in laps_df.columns or c == 'stint_id']
    data = laps_df.merge(stints_df[cols_to_use], on='stint_id', how='inner')
    # If session_id not in data, derive from stint_id (e.g. 2024_monza_R_VER_1 -> 2024_monza_R)
    if 'session_id' not in data.columns:
        data['session_id'] = data['stint_id'].apply(lambda x: '_'.join(x.split('_')[:3]))
    if 'driver_id' not in data.columns:
        data['driver_id'] = data['stint_id'].apply(lambda x: x.split('_')[3] if len(x.split('_')) > 3 else 'UNK')
    data = data.merge(preds_df[['stint_id', 'lap_number', 'actual_lap_time_loss', 'predicted_lap_time_loss']], on=['stint_id', 'lap_number'], how='left')
    data = data.merge(ledger_df[['stint_id', 'lap_number', 'residual', 'cumulative_debt']], on=['stint_id', 'lap_number'], how='left')

    print(f"\n1. Overall Dataset Dimensions:")
    print(f"   Total laps in laps_df:       {len(laps_df):,}")
    print(f"   Total laps in merged data:   {len(data):,}")
    print(f"   Unique stints:               {data['stint_id'].nunique():,}")
    print(f"   Unique sessions:             {data['session_id'].nunique():,}")
    print(f"   Unique circuits:             {data['track_id'].nunique():,}")
    print(f"   Unique drivers:              {data['driver_id'].nunique():,}")
    print(f"   Seasons covered:             {sorted(data['season'].unique())}")
    print(f"   Unique event dates:          {data['event_date'].nunique():,}")

    print(f"\n2. Data Quality & Abnormal Lap Analysis:")
    green_flag_count = (data['is_green_flag'] == 1).sum()
    non_green_count = (data['is_green_flag'] != 1).sum()
    print(f"   Green flag laps:             {green_flag_count:,} ({green_flag_count/len(data)*100:.1f}%)")
    print(f"   Non-green / SC laps:         {non_green_count:,} ({non_green_count/len(data)*100:.1f}%)")

    nan_laptimes = data['lap_time'].isna().sum()
    print(f"   NaN lap times:               {nan_laptimes:,}")
    
    lap_times = data['lap_time'].dropna()
    print(f"   Lap time range (seconds):    [{lap_times.min():.2f}s, {lap_times.max():.2f}s]")
    print(f"   Lap time < 40s (abnormal):   {(lap_times < 40.0).sum():,}")
    print(f"   Lap time > 180s (abnormal):  {(lap_times > 180.0).sum():,}")

    print(f"\n3. Target Construction & Invariant Audit:")
    # Verify how actual_lap_time_loss was built
    data = data.sort_values(by=['stint_id', 'lap_number'])
    cummin_target = data['lap_time'] - data.groupby('stint_id')['lap_time'].cummin()
    full_stint_min_target = data['lap_time'] - data.groupby('stint_id')['lap_time'].transform('min')
    
    print(f"   actual_lap_time_loss (cummin) min/max: [{cummin_target.min():.3f}s, {cummin_target.max():.3f}s]")
    print(f"   actual_lap_time_loss (full_stint_min) min/max: [{full_stint_min_target.min():.3f}s, {full_stint_min_target.max():.3f}s]")

    print(f"\n4. Feature Range & Distribution Audit:")
    data['tyre_age_calc'] = data['tyre_age_start'] + (data['lap_number'] - data['start_lap'])
    neg_tyre_age = data[data['tyre_age_calc'] < 0]
    print(f"   Negative tyre_age rows:      {len(neg_tyre_age):,} / {len(data):,}")
    if len(neg_tyre_age) > 0:
        sample_neg = neg_tyre_age[['stint_id', 'lap_number', 'start_lap', 'end_lap', 'tyre_age_start', 'tyre_age_calc']].head(5)
        print(f"   Sample negative tyre_age rows:\n{sample_neg}")
    print(f"   tyre_age min/max/median:     [{data['tyre_age_calc'].min()}, {data['tyre_age_calc'].max()}], median={data['tyre_age_calc'].median()}")
    print(f"   fuel_load_est min/max/median: [{data['fuel_load_est'].min():.1f}kg, {data['fuel_load_est'].max():.1f}kg], median={data['fuel_load_est'].median():.1f}kg")
    print(f"   track_evolution_index min/max/median: [{data['track_evolution_index'].min():.2f}, {data['track_evolution_index'].max():.2f}], median={data['track_evolution_index'].median():.2f}")
    print(f"   Compounds in dataset:        {data['compound'].value_counts().to_dict()}")

    print(f"\n5. Current Model Metrics (Entire Dataset vs Chronological Split):")
    valid = data[data['predicted_lap_time_loss'].notna() & data['actual_lap_time_loss'].notna()].copy()
    y_true = valid['actual_lap_time_loss'].values
    y_pred = valid['predicted_lap_time_loss'].values

    mae_all = mean_absolute_error(y_true, y_pred)
    rmse_all = np.sqrt(mean_squared_error(y_true, y_pred))
    r2_all = r2_score(y_true, y_pred)
    print(f"   ALL DATA (N={len(valid):,}):  MAE={mae_all:.4f}s | RMSE={rmse_all:.4f}s | R2={r2_all:+.4f}")

    # Chronological Split
    unique_dates = sorted(valid['event_date'].dropna().unique())
    split_date = unique_dates[int(len(unique_dates) * 0.60)]
    train_m = valid['event_date'] <= split_date
    test_m = valid['event_date'] > split_date
    
    y_train_t = y_true[train_m]
    y_train_p = y_pred[train_m]
    y_test_t = y_true[test_m]
    y_test_p = y_pred[test_m]

    print(f"   TRAIN PARTITION (N={len(y_train_t):,}): MAE={mean_absolute_error(y_train_t, y_train_p):.4f}s | RMSE={np.sqrt(mean_squared_error(y_train_t, y_train_p)):.4f}s | R2={r2_score(y_train_t, y_train_p):+.4f}")
    print(f"   HELD-OUT TEST (N={len(y_test_t):,}):   MAE={mean_absolute_error(y_test_t, y_test_p):.4f}s | RMSE={np.sqrt(mean_squared_error(y_test_t, y_test_p)):.4f}s | R2={r2_score(y_test_t, y_test_p):+.4f}")

    print(f"\n6. Simple Baselines Comparison on Test Set:")
    # Baseline 1: Predict Mean of Train Target
    train_mean = np.mean(y_train_t)
    b1_preds = np.full_like(y_test_t, train_mean)
    print(f"   [Baseline 0: Global Mean ({train_mean:.3f}s)] Held-out MAE={mean_absolute_error(y_test_t, b1_preds):.4f}s | RMSE={np.sqrt(mean_squared_error(y_test_t, b1_preds)):.4f}s | R2={r2_score(y_test_t, b1_preds):+.4f}")

    # Baseline 2: Linear Tyre Age Model on Train
    age_train = valid.loc[train_m, 'tyre_age_calc'].values
    age_test = valid.loc[test_m, 'tyre_age_calc'].values
    poly_coefs = np.polyfit(age_train, y_train_t, 1)
    b2_preds = np.polyval(poly_coefs, age_test)
    print(f"   [Baseline 1: Linear Tyre Age (slope={poly_coefs[0]:.4f})] Held-out MAE={mean_absolute_error(y_test_t, b2_preds):.4f}s | RMSE={np.sqrt(mean_squared_error(y_test_t, b2_preds)):.4f}s | R2={r2_score(y_test_t, b2_preds):+.4f}")

    print(f"\n7. Residual Breakdown by Dimension:")
    valid['res'] = valid['actual_lap_time_loss'] - valid['predicted_lap_time_loss']
    
    print("\n   A. By Compound:")
    for comp, grp in valid.groupby('compound'):
        print(f"      {comp:<12} (N={len(grp):>5}): Mean Residual = {grp['res'].mean():+.4f}s | Std = {grp['res'].std():.4f}s | MAE = {grp['res'].abs().mean():.4f}s")

    print("\n   B. By Tyre Age Group:")
    valid['age_bin'] = pd.cut(valid['tyre_age_calc'], bins=[0, 5, 10, 20, 30, 100], labels=['1-5', '6-10', '11-20', '21-30', '31+'])
    for abin, grp in valid.groupby('age_bin', observed=False):
        print(f"      Laps {abin:<6} (N={len(grp):>5}): Mean Residual = {grp['res'].mean():+.4f}s | Std = {grp['res'].std():.4f}s | MAE = {grp['res'].abs().mean():.4f}s")

    print("\n   C. By Circuit (Top 8):")
    for trk, grp in valid.groupby('track_id'):
        if len(grp) >= 200:
            print(f"      {trk:<15} (N={len(grp):>5}): Mean Residual = {grp['res'].mean():+.4f}s | Std = {grp['res'].std():.4f}s | MAE = {grp['res'].abs().mean():.4f}s")

    print("\n   D. Largest Positive & Negative Residuals (Top Outliers):")
    top_pos = valid.nlargest(5, 'res')[['stint_id', 'lap_number', 'lap_time', 'actual_lap_time_loss', 'predicted_lap_time_loss', 'res']]
    top_neg = valid.nsmallest(5, 'res')[['stint_id', 'lap_number', 'lap_time', 'actual_lap_time_loss', 'predicted_lap_time_loss', 'res']]
    print("      Top 5 Slower-than-predicted (High positive residual):")
    for _, r in top_pos.iterrows():
        print(f"         {r['stint_id']} L{int(r['lap_number'])}: Time={r['lap_time']:.2f}s | Loss={r['actual_lap_time_loss']:.2f}s | Pred={r['predicted_lap_time_loss']:.2f}s | Res={r['res']:+.2f}s")
    print("      Top 5 Faster-than-predicted (Negative residual):")
    for _, r in top_neg.iterrows():
        print(f"         {r['stint_id']} L{int(r['lap_number'])}: Time={r['lap_time']:.2f}s | Loss={r['actual_lap_time_loss']:.2f}s | Pred={r['predicted_lap_time_loss']:.2f}s | Res={r['res']:+.2f}s")

    return data


if __name__ == "__main__":
    analyze_dataset()
