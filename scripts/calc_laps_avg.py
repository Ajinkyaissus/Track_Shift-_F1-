import os
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
parquet_path = os.path.join(BASE_DIR, 'data', 'combined_2024_2025_laps.parquet')

df = pd.read_parquet(parquet_path)

# Filter genuine racing laps (exclude in-laps/out-laps/SC extreme outliers)
time_col = 'lap_time_s' if 'lap_time_s' in df.columns else 'lap_time'
age_col = 'tyre_age' if 'tyre_age' in df.columns else 'tyre_life'

racing_laps = df[
    df[time_col].notna() & 
    (df[time_col] > 55.0) & 
    (df[time_col] < 140.0)
].copy()

print("==================================================")
print(f" TOTAL DATASET: {len(df):,} laps across 2024 & 2025")
print(f" CLEAN RACING LAPS: {len(racing_laps):,} laps")
overall_avg = racing_laps[time_col].mean()
print(f" OVERALL AVERAGE LAP TIME: {int(overall_avg // 60)}:{overall_avg % 60:06.3f} ({overall_avg:.3f} s)")
print("==================================================")

# 1. Average Lap Time per Circuit
print("\n--- 1. AVERAGE LAP TIME PER CIRCUIT (ALL 24 CIRCUITS) ---")
c_stats = racing_laps.groupby('circuit_id')[time_col].agg(['mean', 'min', 'max', 'count']).sort_values('mean')
for c_id, row in c_stats.iterrows():
    avg_m = int(row['mean'] // 60)
    avg_s = row['mean'] % 60
    min_m = int(row['min'] // 60)
    min_s = row['min'] % 60
    print(f"{c_id:<16} | Avg Lap: {avg_m}:{avg_s:06.3f} ({row['mean']:7.3f}s) | Fastest: {min_m}:{min_s:06.3f} | Laps: {int(row['count']):,}")

# 2. Average Degradation Loss per Lap by Compound
print("\n--- 2. AVERAGE PACE & LIFE BY TYRE COMPOUND ---")
if 'compound' in racing_laps.columns:
    comp_groups = racing_laps.groupby('compound')
    for comp in ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET']:
        if comp in comp_groups.groups:
            c_df = comp_groups.get_group(comp)
            avg_lt = c_df[time_col].mean()
            avg_age = c_df[age_col].mean() if age_col in c_df.columns else None
            max_age = c_df[age_col].max() if age_col in c_df.columns else None
            print(f"{comp:<12} | Avg Pace: {int(avg_lt//60)}:{avg_lt%60:06.3f} ({avg_lt:.3f}s) | Avg Stint: {avg_age:.1f} laps (Max: {int(max_age)} laps) | Count: {len(c_df):,}")

# 3. Average Lap Debt Accumulation across Stints
if 'D' in racing_laps.columns:
    print("\n--- 3. AVERAGE CUMULATIVE TYRE DEBT BY LAP NUMBER IN STINT ---")
    stint_laps = racing_laps[racing_laps['tyre_life'] <= 35].groupby('tyre_life')['D'].mean()
    for lap_age in [1, 5, 10, 15, 20, 25, 30]:
        if lap_age in stint_laps:
            print(f"Stint Lap {lap_age:2d} | Avg Tyre Debt (D): +{stint_laps[lap_age]:.3f} seconds pace loss")
