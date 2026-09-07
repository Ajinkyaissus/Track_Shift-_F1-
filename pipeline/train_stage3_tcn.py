"""
pipeline/train_stage3_tcn.py — Trainable Temporal Convolutional Network (TCN)
for TrackShift Stage 3 Behavioral Modeling.

Implements:
1. Multi-task learning: Next-lap residual prediction + Telemetry temporal reconstruction
2. Strict chronological group splitting (preventing temporal & stint leakage)
3. Training-only feature scaling
4. Boundary-safe sequence construction (never crosses stint, session, or driver boundaries)
5. Comprehensive artifact checkpointing (weights, config, preprocessing, metrics, manifest)
"""

import os
import sys
import json
import hashlib
import sqlite3
import random
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

DATA_DIR = os.path.join(BASE_DIR, 'data')
API_DIR = os.path.join(BASE_DIR, 'api')
DB_PATH = os.path.join(API_DIR, 'tyredebt.db')
MODELS_DIR = os.path.join(BASE_DIR, 'models', 'stage3')

LAPS_PARQUET = os.path.join(DATA_DIR, 'laps.parquet')
LEDGER_PARQUET = os.path.join(DATA_DIR, 'residual_ledger.parquet')

BEHAVIORAL_FEATURES = [
    'braking_aggression',
    'throttle_transient_smoothness',
    'lateral_dynamics_proxy',
    'kerb_usage',
    'lockup_flag_rate'
]

DEFAULT_EMBEDDING_DIM = 16


def set_seed(seed: int = 42):
    """Sets seeds for reproducibility across Python, NumPy, and PyTorch."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


# ---------------------------------------------------------------------------
# Architecture: Causal 1D Convolution & Residual Temporal Blocks
# ---------------------------------------------------------------------------

class CausalConv1d(nn.Module):
    """
    1D Causal Convolution ensuring no future-to-past information leakage.
    Output at step t depends only on steps <= t.
    """
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, dilation: int = 1):
        super().__init__()
        self.padding = (kernel_size - 1) * dilation
        self.conv = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size=kernel_size,
            padding=self.padding,
            dilation=dilation
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv(x)
        if self.padding > 0:
            out = out[:, :, :-self.padding]
        return out


class TemporalBlock(nn.Module):
    """
    Residual Temporal Dilated Convolution Block with normalization and GELU.
    """
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, dilation: int = 1, dropout: float = 0.1):
        super().__init__()
        self.conv1 = CausalConv1d(in_channels, out_channels, kernel_size, dilation)
        self.norm1 = nn.BatchNorm1d(out_channels)
        self.act1 = nn.GELU()
        self.drop1 = nn.Dropout(dropout)

        self.conv2 = CausalConv1d(out_channels, out_channels, kernel_size, dilation)
        self.norm2 = nn.BatchNorm1d(out_channels)
        self.act2 = nn.GELU()
        self.drop2 = nn.Dropout(dropout)

        self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        res = x if self.downsample is None else self.downsample(x)
        out = self.conv1(x)
        out = self.norm1(out)
        out = self.act1(out)
        out = self.drop1(out)

        out = self.conv2(out)
        out = self.norm2(out)
        out = self.act2(out)
        out = self.drop2(out)

        return out + res


class MultiTaskBehavioralTCN(nn.Module):
    """
    Multi-Task Temporal Convolutional Network for Driving Behavior Representation.
    
    Inputs: Sequential telemetry features (B, C, T) up to lap n
    Outputs:
      1. embedding: 16-D behavioral representation z_behavior
      2. predicted_residual: Scalar prediction of next-lap residual r_{n+1}
      3. reconstructed_seq: Reconstruction of input telemetry sequence (B, C, T)
    """
    def __init__(
        self,
        in_features: int = len(BEHAVIORAL_FEATURES),
        embedding_dim: int = DEFAULT_EMBEDDING_DIM,
        hidden_channels: Tuple[int, int, int] = (32, 48, 64),
        kernel_size: int = 3,
        dropout: float = 0.1
    ):
        super().__init__()
        self.in_features = in_features
        self.embedding_dim = embedding_dim
        c1, c2, c3 = hidden_channels

        self.input_proj = nn.Conv1d(in_features, c1, kernel_size=1)
        self.layer1 = TemporalBlock(c1, c1, kernel_size=kernel_size, dilation=1, dropout=dropout)
        self.layer2 = TemporalBlock(c1, c2, kernel_size=kernel_size, dilation=2, dropout=dropout)
        self.layer3 = TemporalBlock(c2, c3, kernel_size=kernel_size, dilation=4, dropout=dropout)

        # Embedding projection head
        self.embedding_head = nn.Sequential(
            nn.Linear(c3, 32),
            nn.GELU(),
            nn.LayerNorm(32),
            nn.Linear(32, embedding_dim),
            nn.LayerNorm(embedding_dim)
        )

        # Task A: Next-lap residual prediction head
        self.residual_head = nn.Sequential(
            nn.Linear(embedding_dim, 16),
            nn.GELU(),
            nn.Linear(16, 1)
        )

        # Task B: Telemetry temporal reconstruction decoder
        self.decoder_proj = nn.Linear(embedding_dim, c3)
        self.decoder_conv = nn.Sequential(
            nn.Conv1d(c3, c2, kernel_size=1),
            nn.GELU(),
            nn.Conv1d(c2, in_features, kernel_size=1)
        )

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Extracts 16-D embedding z_behavior from input sequence (B, C, T)."""
        h = self.input_proj(x)
        h = self.layer1(h)
        h = self.layer2(h)
        h = self.layer3(h)

        avg_pool = h.mean(dim=-1)
        max_pool, _ = h.max(dim=-1)
        pooled = 0.5 * (avg_pool + max_pool)
        embedding = self.embedding_head(pooled)
        return embedding

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        x: (batch_size, num_features, seq_len)
        Returns: (embedding, predicted_residual, reconstructed_seq)
        """
        seq_len = x.shape[-1]
        embedding = self.encode(x)

        # Task A: Residual prediction
        pred_residual = self.residual_head(embedding).squeeze(-1)

        # Task B: Reconstruction expanded across temporal dimension
        dec_h = self.decoder_proj(embedding).unsqueeze(-1).repeat(1, 1, seq_len)
        recon_seq = self.decoder_conv(dec_h)

        return embedding, pred_residual, recon_seq


# ---------------------------------------------------------------------------
# Boundary-Safe Sequence Construction
# ---------------------------------------------------------------------------

class StintSequenceDataset(Dataset):
    """
    Constructs causal sequences within strict stint boundaries.
    For lap n in a stint, the input sequence is laps max(1, n-max_len+1) .. n,
    and target is the residual of lap n+1 in the same stint.
    """
    def __init__(
        self,
        samples: List[Dict[str, Any]],
        max_seq_len: int = 15
    ):
        self.samples = samples
        self.max_seq_len = max_seq_len

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        item = self.samples[idx]
        seq = item['sequence']  # shape: (T, num_features)
        target = item['target_residual']  # scalar float
        stint_id = item['stint_id']
        lap_num = item['lap_number']

        # Transpose to (num_features, T)
        seq_t = seq.T.astype(np.float32)
        T = seq_t.shape[1]

        # Causal left-padding if sequence length < max_seq_len
        if T < self.max_seq_len:
            pad = np.zeros((seq_t.shape[0], self.max_seq_len - T), dtype=np.float32)
            seq_t = np.concatenate([pad, seq_t], axis=1)
        elif T > self.max_seq_len:
            seq_t = seq_t[:, -self.max_seq_len:]

        return {
            'x': torch.from_numpy(seq_t),
            'target': torch.tensor(target, dtype=torch.float32),
            'stint_id': stint_id,
            'lap_number': lap_num
        }


def build_stint_sequences(
    laps_df: pd.DataFrame,
    ledger_df: pd.DataFrame,
    scaler: Optional[StandardScaler] = None,
    fit_scaler: bool = False,
    max_seq_len: int = 15
) -> Tuple[List[Dict[str, Any]], StandardScaler]:
    """
    Builds causal temporal sequences strictly respecting stint boundaries.
    Never crosses stint or session boundaries.
    """
    laps = laps_df.sort_values(['stint_id', 'lap_number']).copy()
    ledger = ledger_df.sort_values(['stint_id', 'lap_number']).copy()

    # Fit or transform features
    if fit_scaler:
        scaler = StandardScaler()
        scaled_features = scaler.fit_transform(laps[BEHAVIORAL_FEATURES].values)
    else:
        if scaler is None:
            raise ValueError("Scaler must be provided when fit_scaler=False.")
        scaled_features = scaler.transform(laps[BEHAVIORAL_FEATURES].values)

    for i, col in enumerate(BEHAVIORAL_FEATURES):
        laps[f"{col}_scaled"] = scaled_features[:, i]

    scaled_cols = [f"{col}_scaled" for col in BEHAVIORAL_FEATURES]

    # Map residuals from ledger: target is residual at lap n+1
    # Create residual lookup: (stint_id, lap_number) -> residual
    residual_map = dict(zip(zip(ledger['stint_id'], ledger['lap_number']), ledger['residual']))

    samples = []
    # Group by stint to enforce strict boundary isolation
    for stint_id, group in laps.groupby('stint_id', sort=False):
        group_laps = group.sort_values('lap_number').reset_index(drop=True)
        feat_matrix = group_laps[scaled_cols].values  # (N, num_features)
        lap_numbers = group_laps['lap_number'].values

        for idx in range(len(group_laps)):
            lap_n = lap_numbers[idx]
            target_lap = lap_n + 1

            # Check if next lap exists in ledger for this stint
            if (stint_id, target_lap) in residual_map:
                target_residual = float(residual_map[(stint_id, target_lap)])
                # Causal window of past laps in this stint up to lap n
                seq = feat_matrix[:idx + 1]  # shape (t, num_features)
                samples.append({
                    'stint_id': stint_id,
                    'lap_number': int(lap_n),
                    'target_lap': int(target_lap),
                    'sequence': seq,
                    'target_residual': target_residual
                })

    return samples, scaler


# ---------------------------------------------------------------------------
# Training Pipeline & Model Checkpointing
# ---------------------------------------------------------------------------

def train_tcn_model(
    seed: int = 42,
    epochs: int = 60,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    lambda_residual: float = 1.0,
    lambda_recon: float = 0.5,
    max_seq_len: int = 15,
    patience: int = 12
) -> Dict[str, Any]:
    """
    Trains the MultiTaskBehavioralTCN on real FastF1-derived telemetry with
    chronological group splits, leakage-free scaling, and early stopping.
    """
    set_seed(seed)

    if not os.path.exists(LAPS_PARQUET) or not os.path.exists(LEDGER_PARQUET):
        raise FileNotFoundError("Missing required parquet files. Run dataset ingestion first.")

    laps_df = pd.read_parquet(LAPS_PARQUET)
    ledger_df = pd.read_parquet(LEDGER_PARQUET)

    # Clean data
    laps_df = laps_df.dropna(subset=BEHAVIORAL_FEATURES + ['lap_number', 'stint_id']).copy()
    ledger_df = ledger_df.dropna(subset=['residual', 'lap_number', 'stint_id']).copy()

    # Query event dates from SQLite for chronological splitting
    conn = sqlite3.connect(DB_PATH)
    event_info_df = pd.read_sql_query("""
        SELECT s.stint_id, r.event_date, r.track_id, r.race_id
        FROM stints s
        JOIN sessions ses ON s.session_id = ses.session_id
        JOIN races r ON ses.race_id = r.race_id
    """, conn)
    conn.close()

    laps_df = laps_df.merge(event_info_df[['stint_id', 'event_date', 'track_id']], on='stint_id', how='left')

    # Strict Chronological Event Split: Train (earlier ~60%), Val (~20%), Test (~20%)
    unique_dates = sorted(laps_df['event_date'].dropna().unique())
    if len(unique_dates) >= 3:
        train_cutoff_idx = int(len(unique_dates) * 0.60)
        val_cutoff_idx = int(len(unique_dates) * 0.80)
        
        train_dates = set(unique_dates[:train_cutoff_idx])
        val_dates = set(unique_dates[train_cutoff_idx:val_cutoff_idx])
        test_dates = set(unique_dates[val_cutoff_idx:])
        
        train_mask = laps_df['event_date'].isin(train_dates)
        val_mask = laps_df['event_date'].isin(val_dates)
        test_mask = laps_df['event_date'].isin(test_dates)
        
        split_method = f"chronological_events (train_dates: {len(train_dates)}, val_dates: {len(val_dates)}, test_dates: {len(test_dates)})"
    else:
        # Fallback to stint-level chronological split
        stints = laps_df['stint_id'].unique()
        n_stints = len(stints)
        n_train = int(n_stints * 0.60)
        n_val = int(n_stints * 0.80)
        train_stints = set(stints[:n_train])
        val_stints = set(stints[n_train:n_val])
        test_stints = set(stints[n_val:])

        train_mask = laps_df['stint_id'].isin(train_stints)
        val_mask = laps_df['stint_id'].isin(val_stints)
        test_mask = laps_df['stint_id'].isin(test_stints)
        split_method = "chronological_stints"

    train_laps = laps_df[train_mask].copy()
    val_laps = laps_df[val_mask].copy()
    test_laps = laps_df[test_mask].copy()

    # Build sequences with TRAINING-ONLY Scaler fitting
    train_samples, scaler = build_stint_sequences(train_laps, ledger_df, fit_scaler=True, max_seq_len=max_seq_len)
    val_samples, _ = build_stint_sequences(val_laps, ledger_df, scaler=scaler, fit_scaler=False, max_seq_len=max_seq_len)
    test_samples, _ = build_stint_sequences(test_laps, ledger_df, scaler=scaler, fit_scaler=False, max_seq_len=max_seq_len)

    print(f"Dataset split: {len(train_samples)} train sequences, {len(val_samples)} val sequences, {len(test_samples)} test sequences.")

    train_dataset = StintSequenceDataset(train_samples, max_seq_len=max_seq_len)
    val_dataset = StintSequenceDataset(val_samples, max_seq_len=max_seq_len)
    test_dataset = StintSequenceDataset(test_samples, max_seq_len=max_seq_len)

    train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=16, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=16, shuffle=False)

    # Initialize model
    model = MultiTaskBehavioralTCN(
        in_features=len(BEHAVIORAL_FEATURES),
        embedding_dim=DEFAULT_EMBEDDING_DIM,
        hidden_channels=(32, 48, 64),
        kernel_size=3,
        dropout=0.1
    )

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)
    mse_loss_fn = nn.MSELoss()

    best_val_loss = float('inf')
    best_state_dict = None
    early_stop_counter = 0

    history = {
        'train_loss': [],
        'val_loss': [],
        'val_pred_rmse': [],
        'val_recon_mse': []
    }

    for epoch in range(1, epochs + 1):
        model.train()
        train_total_loss = 0.0
        train_batches = 0

        for batch in train_loader:
            x = batch['x']
            target = batch['target']

            optimizer.zero_grad()
            emb, pred_res, recon_x = model(x)

            loss_pred = mse_loss_fn(pred_res, target)
            loss_recon = mse_loss_fn(recon_x, x)
            loss_total = lambda_residual * loss_pred + lambda_recon * loss_recon

            loss_total.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()

            train_total_loss += loss_total.item()
            train_batches += 1

        avg_train_loss = train_total_loss / max(1, train_batches)

        # Validation
        model.eval()
        val_total_loss = 0.0
        val_pred_sq_errs = []
        val_recon_errs = []
        val_batches = 0

        with torch.no_grad():
            for batch in val_loader:
                x = batch['x']
                target = batch['target']

                emb, pred_res, recon_x = model(x)
                loss_p = mse_loss_fn(pred_res, target)
                loss_r = mse_loss_fn(recon_x, x)
                loss_tot = lambda_residual * loss_p + lambda_recon * loss_r

                val_total_loss += loss_tot.item()
                val_pred_sq_errs.extend((pred_res - target).cpu().numpy() ** 2)
                val_recon_errs.append(loss_r.item())
                val_batches += 1

        avg_val_loss = val_total_loss / max(1, val_batches) if val_batches > 0 else avg_train_loss
        val_rmse = float(np.sqrt(np.mean(val_pred_sq_errs))) if val_pred_sq_errs else 0.0
        avg_recon_mse = float(np.mean(val_recon_errs)) if val_recon_errs else 0.0

        scheduler.step(avg_val_loss)

        history['train_loss'].append(avg_train_loss)
        history['val_loss'].append(avg_val_loss)
        history['val_pred_rmse'].append(val_rmse)
        history['val_recon_mse'].append(avg_recon_mse)

        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_state_dict = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            early_stop_counter = 0
        else:
            early_stop_counter += 1
            if early_stop_counter >= patience:
                print(f"Early stopping triggered at epoch {epoch} (best val loss: {best_val_loss:.4f})")
                break

    if best_state_dict is not None:
        model.load_state_dict(best_state_dict)

    # Evaluate on held-out test set
    model.eval()
    test_y_true, test_y_pred = [], []
    with torch.no_grad():
        for batch in test_loader:
            x = batch['x']
            target = batch['target']
            _, pred_res, _ = model(x)
            test_y_true.extend(target.cpu().numpy())
            test_y_pred.extend(pred_res.cpu().numpy())

    test_y_true = np.array(test_y_true)
    test_y_pred = np.array(test_y_pred)

    if len(test_y_true) > 1:
        test_rmse = float(np.sqrt(mean_squared_error(test_y_true, test_y_pred)))
        test_mae = float(mean_absolute_error(test_y_true, test_y_pred))
        test_r2 = float(r2_score(test_y_true, test_y_pred))
        corr_matrix = np.corrcoef(test_y_true, test_y_pred)
        test_corr = float(corr_matrix[0, 1]) if not np.isnan(corr_matrix[0, 1]) else 0.0
    else:
        test_rmse, test_mae, test_r2, test_corr = 0.0, 0.0, 0.0, 0.0

    print(f"Stage 3 Trained TCN Test Results -> RMSE: {test_rmse:.4f} | MAE: {test_mae:.4f} | R²: {test_r2:+.4f} | Corr: {test_corr:.4f}")

    # Checkpoint Artifacts
    date_str = datetime.now().strftime('%Y-%m-%d')
    version_id = f"v5_tcn_stage3_{date_str}"
    version_dir = os.path.join(MODELS_DIR, version_id)
    os.makedirs(version_dir, exist_ok=True)

    # 1. Weights
    weights_path = os.path.join(version_dir, "model.pt")
    torch.save(model.state_dict(), weights_path)

    # 2. Config
    config = {
        "model_version": version_id,
        "architecture": "MultiTaskBehavioralTCN",
        "in_features": len(BEHAVIORAL_FEATURES),
        "embedding_dim": DEFAULT_EMBEDDING_DIM,
        "hidden_channels": [32, 48, 64],
        "kernel_size": 3,
        "dropout": 0.1,
        "max_seq_len": max_seq_len,
        "feature_names": BEHAVIORAL_FEATURES,
        "loss_weights": {
            "lambda_residual": lambda_residual,
            "lambda_recon": lambda_recon
        },
        "training_params": {
            "seed": seed,
            "lr": lr,
            "weight_decay": weight_decay,
            "epochs_run": len(history['train_loss'])
        }
    }
    with open(os.path.join(version_dir, "config.json"), "w") as f:
        json.dump(config, f, indent=2)

    # 3. Preprocessing
    preprocessing = {
        "scaler_type": "StandardScaler",
        "features": BEHAVIORAL_FEATURES,
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "fit_on": f"train_split (N={len(train_laps)} laps)"
    }
    with open(os.path.join(version_dir, "preprocessing.json"), "w") as f:
        json.dump(preprocessing, f, indent=2)

    # 4. Metrics
    metrics = {
        "held_out_test_rmse": test_rmse,
        "held_out_test_mae": test_mae,
        "held_out_test_r2": test_r2,
        "held_out_test_corr": test_corr,
        "best_val_loss": float(best_val_loss),
        "train_samples_count": len(train_samples),
        "val_samples_count": len(val_samples),
        "test_samples_count": len(test_samples),
        "history": history
    }
    with open(os.path.join(version_dir, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    # 5. Manifest with SHA-256
    with open(weights_path, "rb") as f:
        model_hash = hashlib.sha256(f.read()).hexdigest()

    manifest = {
        "model_version": version_id,
        "stage": 3,
        "model_hash_sha256": model_hash,
        "created_at": datetime.now().isoformat(),
        "split_method": split_method,
        "dataset_laps_total": len(laps_df),
        "dataset_ledger_total": len(ledger_df)
    }
    with open(os.path.join(version_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[OK] Checkpointed {version_id} to {version_dir} (SHA-256: {model_hash[:12]}...)")

    return {
        "model": model,
        "scaler": scaler,
        "version": version_id,
        "version_dir": version_dir,
        "metrics": metrics,
        "manifest": manifest,
        "config": config,
        "train_samples": train_samples,
        "val_samples": val_samples,
        "test_samples": test_samples
    }


if __name__ == "__main__":
    train_tcn_model()
