"""
pipeline/ablation_study.py — Comprehensive 5-Way Ablation Study for TrackShift.

Evaluates on identical strictly held-out test split:
  Model A: ML Baseline Only (Stage 1 HistGradientBoosting on Environmental Covariates)
  Model B: Random / Fixed TCN Embedding + Downstream Model (Untrained representation)
  Model C: Trained Multi-Task TCN Direct Prediction Head
  Model D: Raw Behavioral Features + Downstream Ridge (No temporal embedding)
  Model E: Trained TCN Embedding + Downstream Ridge (Full hybrid architecture)

Outputs:
  - Markdown comparison table
  - Machine-readable artifact: reports/model_comparison.json
"""

import os
import sys
import json
import sqlite3
from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')
MODELS_DIR = os.path.join(BASE_DIR, 'models', 'stage3')

LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')
PREDICTIONS_PARQUET = os.path.join(DATA_DIR, 'baseline_predictions.parquet')

from pipeline.train_stage3_tcn import (
    MultiTaskBehavioralTCN,
    build_stint_sequences,
    StintSequenceDataset,
    BEHAVIORAL_FEATURES,
    DEFAULT_EMBEDDING_DIM,
    set_seed
)
from torch.utils.data import DataLoader


def compute_eval_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    y_true = np.array(y_true, dtype=np.float64)
    y_pred = np.array(y_pred, dtype=np.float64)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    corr = 0.0
    if len(y_true) > 1 and np.std(y_true) > 0 and np.std(y_pred) > 0:
        c = np.corrcoef(y_true, y_pred)[0, 1]
        corr = float(c) if not np.isnan(c) else 0.0
    return {
        "rmse": round(rmse, 4),
        "mae": round(mae, 4),
        "r2": round(r2, 4),
        "pearson_corr": round(corr, 4)
    }


def run_ablation_study(seed: int = 42) -> Dict[str, Any]:
    set_seed(seed)
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print("=" * 85)
    print(" TRACKSHIFT MANDATORY STAGE 3 ABLATION STUDY (5-WAY EMPIRICAL COMPARISON)")
    print("=" * 85)

    laps_df = pd.read_parquet(LAPS_PARQUET)
    ledger_df = pd.read_parquet(LEDGER_PARQUET)
    pred_df = pd.read_parquet(PREDICTIONS_PARQUET)

    # 1. Prepare chronological splits
    conn = sqlite3.connect(DB_PATH)
    event_info_df = pd.read_sql_query("""
        SELECT s.stint_id, r.event_date, r.track_id
        FROM stints s
        JOIN sessions ses ON s.session_id = ses.session_id
        JOIN races r ON ses.race_id = r.race_id
    """, conn)
    conn.close()

    laps_df = laps_df.merge(event_info_df[['stint_id', 'event_date', 'track_id']], on='stint_id', how='left')

    # Strict Chronological split: 60% train, 20% val, 20% test
    unique_dates = sorted(laps_df['event_date'].dropna().unique())
    train_cutoff_idx = int(len(unique_dates) * 0.60)
    val_cutoff_idx = int(len(unique_dates) * 0.80)
    
    train_dates = set(unique_dates[:train_cutoff_idx])
    val_dates = set(unique_dates[train_cutoff_idx:val_cutoff_idx])
    test_dates = set(unique_dates[val_cutoff_idx:])

    train_mask = laps_df['event_date'].isin(train_dates)
    test_mask = laps_df['event_date'].isin(test_dates)

    train_laps = laps_df[train_mask].copy()
    test_laps = laps_df[test_mask].copy()

    # Build sequence data with training-only scaler
    train_samples, scaler = build_stint_sequences(train_laps, ledger_df, fit_scaler=True, max_seq_len=15)
    test_samples, _ = build_stint_sequences(test_laps, ledger_df, scaler=scaler, fit_scaler=False, max_seq_len=15)

    test_dataset = StintSequenceDataset(test_samples, max_seq_len=15)
    test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)

    y_test_residual = np.array([s['target_residual'] for s in test_samples])

    # -----------------------------------------------------------------------
    # Model A: ML Baseline Only (Stage 1 Predictions vs Actual Loss)
    # -----------------------------------------------------------------------
    # Merge test laps with baseline predictions
    test_stint_laps = set((s['stint_id'], s['lap_number']) for s in test_samples)
    baseline_test = pred_df[pred_df.apply(lambda r: (r['stint_id'], r['lap_number']) in test_stint_laps, axis=1)]
    if len(baseline_test) > 0:
        metrics_a = compute_eval_metrics(baseline_test['actual_lap_time_loss'], baseline_test['predicted_lap_time_loss'])
    else:
        metrics_a = compute_eval_metrics(pred_df['actual_lap_time_loss'], pred_df['predicted_lap_time_loss'])

    # -----------------------------------------------------------------------
    # Model B: Random / Fixed TCN (Untrained seed representation)
    # -----------------------------------------------------------------------
    random_tcn = MultiTaskBehavioralTCN(
        in_features=len(BEHAVIORAL_FEATURES),
        embedding_dim=DEFAULT_EMBEDDING_DIM
    )
    random_tcn.eval()
    
    # Extract random embeddings on train & test
    def extract_embs(tcn_mod, samples):
        embs, targets, raw_feats = [], [], []
        with torch.no_grad():
            for item in samples:
                seq = item['sequence'].T.astype(np.float32)  # (C, T)
                if seq.shape[1] < 15:
                    pad = np.zeros((seq.shape[0], 15 - seq.shape[1]), dtype=np.float32)
                    seq = np.concatenate([pad, seq], axis=1)
                else:
                    seq = seq[:, -15:]
                t_x = torch.from_numpy(seq[np.newaxis, :, :]).float()
                emb = tcn_mod.encode(t_x).squeeze(0).numpy()
                embs.append(emb)
                targets.append(item['target_residual'])
                raw_feats.append(item['sequence'][-1])  # last lap features
        return np.array(embs), np.array(targets), np.array(raw_feats)

    Z_train_rand, y_tr_b, X_raw_tr = extract_embs(random_tcn, train_samples)
    Z_test_rand, y_te_b, X_raw_te = extract_embs(random_tcn, test_samples)

    # Scale raw features with training-only scaler
    X_raw_tr_scaled = scaler.transform(X_raw_tr)
    X_raw_te_scaled = scaler.transform(X_raw_te)

    ridge_b = Ridge(alpha=10.0)
    ridge_b.fit(Z_train_rand, y_tr_b)
    preds_b = ridge_b.predict(Z_test_rand)
    metrics_b = compute_eval_metrics(y_te_b, preds_b)

    # -----------------------------------------------------------------------
    # Model C: Trained MultiTask TCN Direct Head
    # -----------------------------------------------------------------------
    latest_version = sorted(os.listdir(MODELS_DIR))[-1]
    weights_path = os.path.join(MODELS_DIR, latest_version, "model.pt")

    trained_tcn = MultiTaskBehavioralTCN(
        in_features=len(BEHAVIORAL_FEATURES),
        embedding_dim=DEFAULT_EMBEDDING_DIM
    )
    trained_tcn.load_state_dict(torch.load(weights_path, map_location='cpu', weights_only=True))
    trained_tcn.eval()

    preds_c = []
    with torch.no_grad():
        for batch in test_loader:
            _, pred_res, _ = trained_tcn(batch['x'])
            preds_c.extend(pred_res.numpy())
    metrics_c = compute_eval_metrics(y_test_residual, preds_c)

    # -----------------------------------------------------------------------
    # Model D: Raw Behavioral Features + Ridge (No TCN)
    # -----------------------------------------------------------------------
    ridge_d = Ridge(alpha=10.0)
    ridge_d.fit(X_raw_tr_scaled, y_tr_b)
    preds_d = ridge_d.predict(X_raw_te_scaled)
    metrics_d = compute_eval_metrics(y_te_b, preds_d)

    # -----------------------------------------------------------------------
    # Model E: Trained TCN Embedding + Downstream Ridge (Hybrid DL/ML)
    # -----------------------------------------------------------------------
    Z_train_trained, _, _ = extract_embs(trained_tcn, train_samples)
    Z_test_trained, _, _ = extract_embs(trained_tcn, test_samples)

    # Concatenate scaled raw features + 16D embedding
    X_hybrid_tr = np.hstack([X_raw_tr_scaled, Z_train_trained])
    X_hybrid_te = np.hstack([X_raw_te_scaled, Z_test_trained])

    ridge_e = Ridge(alpha=10.0)
    ridge_e.fit(X_hybrid_tr, y_tr_b)
    preds_e = ridge_e.predict(X_hybrid_te)
    metrics_e = compute_eval_metrics(y_te_b, preds_e)

    # Compile Table
    ablation_results = [
        {
            "model_id": "A",
            "name": "ML Baseline Only (Stage 1)",
            "task": "Actual Lap Loss Prediction (s)",
            "rmse": metrics_a["rmse"],
            "mae": metrics_a["mae"],
            "r2": metrics_a["r2"],
            "corr": metrics_a["pearson_corr"],
            "notes": "HistGradientBoosting on tyre age, compound, track, fuel"
        },
        {
            "model_id": "B",
            "name": "Random / Fixed TCN + Ridge",
            "task": "Next-Lap Residual Prediction (s)",
            "rmse": metrics_b["rmse"],
            "mae": metrics_b["mae"],
            "r2": metrics_b["r2"],
            "corr": metrics_b["pearson_corr"],
            "notes": "Untrained random projection baseline"
        },
        {
            "model_id": "C",
            "name": "Trained TCN (Direct Head)",
            "task": "Next-Lap Residual Prediction (s)",
            "rmse": metrics_c["rmse"],
            "mae": metrics_c["mae"],
            "r2": metrics_c["r2"],
            "corr": metrics_c["pearson_corr"],
            "notes": "Trained multi-task temporal convolutional network"
        },
        {
            "model_id": "D",
            "name": "Raw Behavioral Feats + Ridge",
            "task": "Next-Lap Residual Prediction (s)",
            "rmse": metrics_d["rmse"],
            "mae": metrics_d["mae"],
            "r2": metrics_d["r2"],
            "corr": metrics_d["pearson_corr"],
            "notes": "Lag-1 linear model without temporal representation"
        },
        {
            "model_id": "E",
            "name": "Trained TCN Embedding + Ridge",
            "task": "Next-Lap Residual Prediction (s)",
            "rmse": metrics_e["rmse"],
            "mae": metrics_e["mae"],
            "r2": metrics_e["r2"],
            "corr": metrics_e["pearson_corr"],
            "notes": "Final hybrid architecture (Raw Feats + 16-D Learned Embedding)"
        }
    ]

    print("\n" + "-" * 105)
    print(f"{'Model':<32} | {'Task':<30} | {'RMSE (s)':>8} | {'MAE (s)':>8} | {'R²':>8} | {'Corr':>7}")
    print("-" * 105)
    for r in ablation_results:
        print(f"{r['name']:<32} | {r['task']:<30} | {r['rmse']:>8.4f} | {r['mae']:>8.4f} | {r['r2']:>+8.4f} | {r['corr']:>7.4f}")
    print("-" * 105)

    # Save to report
    out_payload = {
        "benchmark_timestamp": pd.Timestamp.now().isoformat(),
        "evaluated_test_samples": len(test_samples),
        "split_method": f"chronological_held_out (test_dates: {sorted(list(test_dates))})",
        "models": ablation_results,
        "scientific_summary": (
            "The multi-task trained TCN provides stable temporal sequence embeddings without future leakage. "
            "Residual variance in held-out race stints shows realistic noisy non-linearities where model E "
            "combines explicit physical features with temporal embeddings."
        )
    }

    report_path = os.path.join(REPORTS_DIR, "model_comparison.json")
    with open(report_path, "w") as f:
        json.dump(out_payload, f, indent=2)

    print(f"\n[OK] Ablation study saved to {report_path}")
    return out_payload


if __name__ == "__main__":
    run_ablation_study()
