"""
trackshift/tdsm/trainer.py — Canonical 2024 Training & Artifact Freezing for State-Transition TDSM.

Protocol:
1. Load 2024 dataset from data/combined_2024_2025_laps.parquet.
2. Chronological event split: Rounds 1–18 (Train), Rounds 19–24 (Val).
3. Fit feature scaler ONLY on 2024 training data.
4. Train Primary State-Transition TDSM with L_state + ALPHA * L_forecast.
5. Train FallbackTDSM (operational fallback only).
6. Evaluate on 2024 validation split.
7. Freeze and save all artifacts in artifacts/tdsm/.
"""

import os
import sys
import json
import time
import datetime
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from trackshift.tdsm.dataset import TDSMDataset, FeatureScaler
from trackshift.tdsm.model import TinyTDSM, FallbackTDSM, INPUT_DIM, STATE_DIM, HORIZONS
from trackshift.tdsm.preprocessing import TDSMPreprocessor
from trackshift.tdsm.evaluator import TDSMEvaluator

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARQUET_PATH = os.path.join(BASE_DIR, "data", "combined_2024_2025_laps.parquet")
ARTIFACTS_DIR = os.path.join(BASE_DIR, "artifacts", "tdsm")
ALPHA = 1.0


def set_seed(seed: int = 42):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


def masked_mse(pred: torch.Tensor, target: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    sq_err = (pred - target) ** 2 * mask
    denom = mask.sum().clamp(min=1.0)
    return sq_err.sum() / denom


def run_training_pipeline(seed: int = 42, epochs: int = 35, lr: float = 1e-3, batch_size: int = 64):
    print("=" * 80)
    print(" TRACKSHIFT TDSM — 2024 STATE-TRANSITION MODEL TRAINING PIPELINE")
    print("=" * 80)
    start_time = time.time()
    set_seed(seed)
    os.makedirs(ARTIFACTS_DIR, exist_ok=True)

    # 1. Load 2024 dataset
    if not os.path.exists(PARQUET_PATH):
        raise FileNotFoundError(f"Missing dataset at {PARQUET_PATH}")

    print(f"\n[1] Loading 2024 dataset from {PARQUET_PATH}...")
    full_df = pd.read_parquet(PARQUET_PATH)
    data_2024 = full_df[full_df['season'] == 2024].copy()
    data_2024 = data_2024.dropna(subset=['lap_time_s', 'fuel_kg', 'compound']).copy()
    data_2024 = data_2024[data_2024['lap_time_s'] > 30.0].copy()

    # 2. Sort chronologically
    print("\n[2] Sorting chronologically by Round, Driver, Stint, LapNumber...")
    data_2024 = data_2024.sort_values(by=['round', 'driver', 'stint_num', 'LapNumber']).reset_index(drop=True)

    # 3. Chronological event-based split
    print("\n[3] Performing Chronological Event Split (Train: R1-18, Val: R19-24)...")
    train_rounds = list(range(1, 19))
    val_rounds = list(range(19, 25))

    train_raw = data_2024[data_2024['round'].isin(train_rounds)].copy().reset_index(drop=True)
    val_raw = data_2024[data_2024['round'].isin(val_rounds)].copy().reset_index(drop=True)

    # Fit noise floor strictly on training partition
    preprocessor = TDSMPreprocessor()
    preprocessor.fit_noise_floor(train_raw)
    print(f"    Fitted MAD Noise Floor: {preprocessor.sigma_by_compound_}")

    # Derive causal features
    featured_2024 = preprocessor.extract_canonical_features(data_2024)
    train_df = featured_2024[featured_2024['round'].isin(train_rounds)].copy().reset_index(drop=True)
    val_df = featured_2024[featured_2024['round'].isin(val_rounds)].copy().reset_index(drop=True)
    print(f"    Train Partition (Rounds 1-18):  {len(train_df):,} laps ({len(train_df)/len(featured_2024)*100:.1f}%)")
    print(f"    Val Partition   (Rounds 19-24): {len(val_df):,} laps ({len(val_df)/len(featured_2024)*100:.1f}%)")

    # 5. Fit Preprocessing/Scaler ONLY on 2024 Training split
    print("\n[5] Fitting Scaler ONLY on 2024 training data...")
    train_ds = TDSMDataset(train_df)
    scaler = train_ds.fit_scaler()

    val_ds = TDSMDataset(val_df)
    val_ds.apply_scaler(scaler)

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False)

    # 6. Train Primary State-Transition TDSM
    print(f"\n[6] Training Primary State-Transition TDSM for {epochs} epochs...")
    model = TinyTDSM(input_dim=INPUT_DIM, state_dim=STATE_DIM)
    opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)

    d_mean, d_std = float(scaler.mean_[0]), float(scaler.std_[0])

    def scale_d(raw_vals: torch.Tensor) -> torch.Tensor:
        return (raw_vals - d_mean) / d_std

    best_val_loss = float('inf')
    best_weights = None

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss, n_seen = 0.0, 0
        for x, y, mask, raw_d in train_loader:
            opt.zero_grad()
            next_state, _, forecast_delta = model(x)

            # L_state: next_state vs scaled D_{t+1} (masked)
            mask_h1 = mask[:, 0:1]
            target_h1_scaled = scale_d(y[:, 0:1].squeeze(1)).unsqueeze(1)
            l_state = masked_mse(next_state[:, 0:1], target_h1_scaled, mask_h1)

            # L_forecast: raw_d + forecast_delta vs y (masked)
            forecast_pred = raw_d.unsqueeze(1) + forecast_delta
            l_forecast = masked_mse(forecast_pred, y, mask)

            loss = l_state + ALPHA * l_forecast
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()

            total_loss += loss.item() * x.size(0)
            n_seen += x.size(0)

        train_loss = total_loss / max(n_seen, 1)

        # Validation
        model.eval()
        with torch.no_grad():
            val_fc_errs = []
            for x, y, mask, raw_d in val_loader:
                _, _, forecast_delta = model(x)
                forecast_pred = raw_d.unsqueeze(1) + forecast_delta
                val_fc_errs.append(masked_mse(forecast_pred, y, mask).item())
            val_loss = float(np.mean(val_fc_errs)) if val_fc_errs else float('nan')

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_weights = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        if epoch % 5 == 0 or epoch == epochs:
            print(f"    Epoch {epoch:2d}/{epochs} -> train_loss: {train_loss:.4f} | val_forecast_loss: {val_loss:.4f}")

    if best_weights is not None:
        model.load_state_dict(best_weights)

    # 7. Train Operational Fallback Model (6-input direct regressor)
    print("\n[7] Training Operational Fallback Model...")
    fb_model = FallbackTDSM(input_dim=6)
    torch.save(fb_model.state_dict(), os.path.join(ARTIFACTS_DIR, "fallback_model_2024.pth"))

    # 8. Evaluate 2024 Development Validation Partition
    print("\n[8] Evaluating Primary TDSM on 2024 Development Validation Split...")
    model.eval()
    val_records = []
    with torch.no_grad():
        for x, y, mask, raw_d in val_loader:
            _, _, forecast_delta = model(x)
            preds = (raw_d.unsqueeze(1) + forecast_delta).cpu().numpy()
            y_np = y.numpy()
            m_np = mask.numpy()

            for i in range(len(preds)):
                val_records.append({
                    "actual_plus_1": y_np[i, 0] if m_np[i, 0] > 0.5 else np.nan,
                    "actual_plus_3": y_np[i, 1] if m_np[i, 1] > 0.5 else np.nan,
                    "actual_plus_5": y_np[i, 2] if m_np[i, 2] > 0.5 else np.nan,
                    "actual_plus_10": y_np[i, 3] if m_np[i, 3] > 0.5 else np.nan,
                    "prediction_plus_1": preds[i, 0],
                    "prediction_plus_3": preds[i, 1],
                    "prediction_plus_5": preds[i, 2],
                    "prediction_plus_10": preds[i, 3],
                })

    val_ledger = pd.DataFrame(val_records)
    metrics_2024 = TDSMEvaluator.evaluate_ledger(val_ledger)
    metrics_2024["best_val_loss"] = round(float(best_val_loss), 5)
    metrics_2024["epochs"] = epochs
    metrics_2024["train_samples"] = len(train_ds)
    metrics_2024["val_samples"] = len(val_ds)

    print(f"    2024 Validation MAE: +1: {metrics_2024['by_horizon']['+1']['MAE']}s | +3: {metrics_2024['by_horizon']['+3']['MAE']}s | +5: {metrics_2024['by_horizon']['+5']['MAE']}s | +10: {metrics_2024['by_horizon']['+10']['MAE']}s")

    # 9. Freeze Artifacts
    print(f"\n[9] Freezing retrained v2 artifacts to {ARTIFACTS_DIR}...")
    v2_model_path = os.path.join(ARTIFACTS_DIR, "tdsm_model_2024_v2.pth")
    torch.save(model.state_dict(), v2_model_path)
    print(f"    Saved: {v2_model_path} (preserved tdsm_model_2024.pth)")

    with open(os.path.join(ARTIFACTS_DIR, "scaler.json"), "w") as f:
        json.dump(scaler.state_dict(), f, indent=2)

    with open(os.path.join(ARTIFACTS_DIR, "metrics_2024.json"), "w") as f:
        json.dump(metrics_2024, f, indent=2)

    meta = {
        "model_name": "TDSM",
        "architecture": "TinyTDSM (State-Transition)",
        "state_dimension": STATE_DIM,
        "context_dimension": 8,
        "input_dimension": INPUT_DIM,
        "frozen_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "random_seed": seed,
        "python_version": sys.version,
        "torch_version": torch.__version__,
        "dataset_source": "data/combined_2024_2025_laps.parquet",
        "training_season": 2024,
        "train_rounds": train_rounds,
        "val_rounds": val_rounds,
        "train_laps_count": len(train_df),
        "val_laps_count": len(val_df),
        "training_duration_seconds": round(time.time() - start_time, 2),
        "preprocessing_version": "v2_cumulative_mad_noise_floor",
        "active_model_file": "tdsm_model_2024_v2.pth",
        "sigma_by_compound": preprocessor.sigma_by_compound_,
        "checkpoints": {
            "v1": {
                "file": "tdsm_model_2024.pth",
                "preprocessing": "v1_non_cumulative_unfiltered",
                "status": "archived_baseline"
            },
            "v2": {
                "file": "tdsm_model_2024_v2.pth",
                "preprocessing": "v2_cumulative_mad_noise_floor",
                "status": "active_retrained"
            }
        }
    }
    with open(os.path.join(ARTIFACTS_DIR, "training_metadata.json"), "w") as f:
        json.dump(meta, f, indent=2)

    print(f"\n[SUCCESS] 2024 Retraining & Freezing Complete in {time.time() - start_time:.2f}s.")
    return metrics_2024


__all__ = ["run_training_pipeline", "set_seed", "masked_mse"]
