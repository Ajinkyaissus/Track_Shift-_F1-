"""
pipeline/uncertainty_bootstrap.py — Stint-Level Cluster Bootstrap for Statistical Uncertainty.

Implements:
1. Cluster/stint-level resampling with replacement (preserving intra-stint temporal correlation)
2. B = 1,000 bootstrap iterations
3. Empirical 2.5th, 50th, and 97.5th percentile interval construction
4. Precomputes uncertainty lookup tables for all stints and behavioral adjustments
5. Serializes to data/bootstrap_uncertainty.parquet and reports/uncertainty_validation.json
"""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
from typing import Dict, Any
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')
BOOTSTRAP_PARQUET = os.path.join(DATA_DIR, 'bootstrap_uncertainty.parquet')

BEHAVIORAL_FEATURES = [
    'braking_aggression',
    'throttle_transient_smoothness',
    'lateral_dynamics_proxy',
    'kerb_usage',
    'lockup_flag_rate'
]


def run_stint_bootstrap(n_bootstrap: int = 1000, seed: int = 42) -> Dict[str, Any]:
    np.random.seed(seed)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print("=" * 80)
    print(f" TRACKSHIFT STINT-LEVEL CLUSTER BOOTSTRAP (B={n_bootstrap} REPLICATES)")
    print("=" * 80)

    laps_df = pd.read_parquet(LAPS_PARQUET)
    ledger_df = pd.read_parquet(LEDGER_PARQUET)

    laps_df['target_lap'] = laps_df['lap_number'] + 1
    data = ledger_df.merge(
        laps_df,
        left_on=['stint_id', 'lap_number'],
        right_on=['stint_id', 'target_lap'],
        suffixes=('_ledger', '_feat'),
        how='inner'
    )
    valid_mask = (data['lap_number_ledger'] - data['lap_number_feat']) == 1
    data = data[valid_mask].dropna(subset=BEHAVIORAL_FEATURES + ['residual'])

    stints = data['stint_id'].unique()
    n_stints = len(stints)
    print(f"Sampling unit: Independent Stints (N={n_stints} distinct stints, {len(data)} total laps)")

    # Pre-extract numpy arrays per stint for lightning fast bootstrap resampling
    stint_groups = {s: data[data['stint_id'] == s] for s in stints}
    stint_numpy = {
        s: (stint_groups[s][BEHAVIORAL_FEATURES].values, stint_groups[s]['residual'].values)
        for s in stints
    }

    # Grid of delta percentages to precompute: -50% to +50% in 5% steps
    delta_grid = [float(d) for d in range(-50, 55, 5)]

    # Calculate stint feature means, degradation rates, and stint lengths
    stint_feature_means = laps_df.groupby('stint_id')[BEHAVIORAL_FEATURES].mean().to_dict(orient='index')
    
    conn = sqlite3.connect(DB_PATH)
    stint_lengths_df = pd.read_sql_query("SELECT stint_id, (end_lap - start_lap + 1) as stint_len FROM stints", conn)
    conn.close()
    stint_lengths = dict(zip(stint_lengths_df['stint_id'], stint_lengths_df['stint_len']))

    def calc_deg_rate(group):
        if len(group) < 2:
            return 0.1
        group = group.sort_values('lap_number')
        dn = group.iloc[-1]['lap_number'] - group.iloc[0]['lap_number']
        if dn == 0:
            return 0.1
        rate = (group.iloc[-1]['predicted_lap_time_loss'] - group.iloc[0]['predicted_lap_time_loss']) / dn
        return float(rate) if rate != 0 else 0.1
    
    stint_deg_rates = ledger_df.groupby('stint_id').apply(calc_deg_rate, include_groups=False).to_dict()

    # Bootstrap replicates of coefficients
    boot_coefs = {feat: [] for feat in BEHAVIORAL_FEATURES}

    print(f"Running {n_bootstrap} cluster bootstrap fits...")
    for b in range(n_bootstrap):
        # Resample stint IDs with replacement
        resampled_stint_ids = np.random.choice(stints, size=n_stints, replace=True)
        # Assemble bootstrap dataset using pre-extracted numpy arrays
        X_b = np.concatenate([stint_numpy[s][0] for s in resampled_stint_ids], axis=0)
        y_b = np.concatenate([stint_numpy[s][1] for s in resampled_stint_ids], axis=0)

        scaler_b = StandardScaler()
        X_b_scaled = scaler_b.fit_transform(X_b)

        model_b = Ridge(alpha=10.0)
        model_b.fit(X_b_scaled, y_b)

        # Unscale coefficients to match physical units (seconds debt per unit feature)
        unscaled_coefs = model_b.coef_ / np.where(scaler_b.scale_ == 0, 1.0, scaler_b.scale_)
        for i, feat in enumerate(BEHAVIORAL_FEATURES):
            boot_coefs[feat].append(float(unscaled_coefs[i]))

    # Analyze coefficient empirical bootstrap distributions
    coef_stats = {}
    for feat in BEHAVIORAL_FEATURES:
        arr = np.array(boot_coefs[feat])
        q025 = float(np.percentile(arr, 2.5))
        q50 = float(np.percentile(arr, 50.0))
        q975 = float(np.percentile(arr, 97.5))
        coef_stats[feat] = {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "p2_5": q025,
            "p50": q50,
            "p97_5": q975,
            "ci_95": [round(q025, 6), round(q975, 6)]
        }
        print(f"  {feat:<30} | Median: {q50:+.6f} | 95% Bootstrap CI: [{q025:+.6f}, {q975:+.6f}]")

    # Generate precomputed lookup table for all (stint_id, feature, delta_pct)
    print("\nPrecomputing empirical uncertainty lookup table across all stints and delta grid...")
    records = []
    
    deltas_arr = np.array(delta_grid)  # (n_deltas,)
    deltas_2d = deltas_arr[:, None] / 100.0  # (n_deltas, 1)

    for stint_id in stints:
        means = stint_feature_means.get(stint_id, {})
        stint_len = max(5, stint_lengths.get(stint_id, 20) or 20)
        deg_per_lap = max(0.01, stint_deg_rates.get(stint_id, 0.1))
        max_physical_laps = min(0.35 * stint_len, 7.5)

        for feat in BEHAVIORAL_FEATURES:
            avg_val = means.get(feat, 0.0)
            if np.isnan(avg_val):
                avg_val = 0.0

            feat_boot_coefs = np.array(boot_coefs[feat])  # shape (n_bootstrap,)
            
            # Vectorized across all deltas and bootstrap samples at once: shape (n_deltas, n_bootstrap)
            raw_recovered = -(feat_boot_coefs[None, :] * deltas_2d * avg_val) / deg_per_lap
            bounded_recovered = max_physical_laps * np.tanh(raw_recovered / max_physical_laps)

            q025_vec = np.percentile(bounded_recovered, 2.5, axis=1)
            q50_vec = np.percentile(bounded_recovered, 50.0, axis=1)
            q975_vec = np.percentile(bounded_recovered, 97.5, axis=1)

            for d_idx, delta in enumerate(delta_grid):
                q025 = float(q025_vec[d_idx])
                q50 = float(q50_vec[d_idx])
                q975 = float(q975_vec[d_idx])

                records.append({
                    "stint_id": stint_id,
                    "feature": feat,
                    "delta_pct": delta,
                    "recovered_p50": round(q50, 3),
                    "ci_lower": round(q025, 3),
                    "ci_upper": round(q975, 3),
                    "ci_margin": round((q975 - q025) / 2.0, 3),
                    "is_saturated": bool(abs(q50) > (max_physical_laps * 0.75)),
                    "max_physical_bound": round(max_physical_laps, 2)
                })

    uncertainty_df = pd.DataFrame(records)
    uncertainty_df.to_parquet(BOOTSTRAP_PARQUET, index=False)
    print(f"[OK] Saved {len(uncertainty_df)} precomputed uncertainty rows to {BOOTSTRAP_PARQUET}")

    # Save scientific validation report
    validation_payload = {
        "method": "stint_cluster_bootstrap",
        "resampling_unit": "stint_id",
        "n_bootstrap": n_bootstrap,
        "confidence_level": 0.95,
        "n_stints_sampled": int(n_stints),
        "total_laps": int(len(data)),
        "coefficients_bootstrap_summary": coef_stats,
        "scientific_interpretation": (
            "Stint-level cluster bootstrap resamples entire stints with replacement, correctly accounting "
            "for within-stint lap autocorrelation and lap time clustering. Percentile intervals (2.5%, 97.5%) "
            "provide non-parametric empirical uncertainty bounds for observational sensitivity estimates."
        )
    }

    report_path = os.path.join(REPORTS_DIR, "uncertainty_validation.json")
    with open(report_path, "w") as f:
        json.dump(validation_payload, f, indent=2)

    print(f"[OK] Saved uncertainty validation report to {report_path}")
    return validation_payload


if __name__ == "__main__":
    n_boot = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
    run_stint_bootstrap(n_bootstrap=n_boot)
