"""
trackshift/tdsm/dataset.py — TDSM Dataset, Compound One-Hot Encoding, Continuous Scaler, and DataLoader.
Canonical implementation for State-Transition TDSM.
"""

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader
from typing import List, Tuple, Dict, Any, Optional

COMPOUNDS = ['SOFT', 'MEDIUM', 'HARD', 'INTERMEDIATE', 'WET', 'UNKNOWN']
COMPOUND_MAP = {c: i for i, c in enumerate(COMPOUNDS)}


def one_hot_compound(compound_str: str) -> np.ndarray:
    """Converts a compound string into a 6-dimensional one-hot vector."""
    c_clean = str(compound_str).upper()
    idx = COMPOUND_MAP.get(c_clean, 5)
    vec = np.zeros(len(COMPOUNDS), dtype=np.float32)
    vec[idx] = 1.0
    return vec


class FeatureScaler:
    """StandardScaler fitted strictly on training data."""
    def __init__(self):
        self.mean_ = None
        self.std_ = None

    def fit(self, x: np.ndarray):
        self.mean_ = np.mean(x, axis=0)
        std = np.std(x, axis=0)
        # Avoid division by zero
        self.std_ = np.where(std < 1e-6, 1.0, std)

    def transform(self, x: np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.std_ is None:
            return x
        return (x - self.mean_) / self.std_

    def state_dict(self) -> Dict[str, List[float]]:
        return {
            "mean": self.mean_.tolist() if self.mean_ is not None else [],
            "std": self.std_.tolist() if self.std_ is not None else []
        }

    def load_state_dict(self, d: Dict[str, Any]):
        self.mean_ = np.array(d["mean"], dtype=np.float32)
        self.std_ = np.array(d["std"], dtype=np.float32)


class TDSMDataset(Dataset):
    """
    Masked Multi-Horizon Dataset for State-Transition TDSM.
    
    Inputs (11):
      S_t: [D, Delta_D, Delta2_D] (scaled)
      Context: [TyreLife, FuelProxy] (scaled) + CompoundOneHot(6)
      
    Targets:
      y: [D_{t+1}, D_{t+3}, D_{t+5}, D_{t+10}] (raw debt)
      mask: [m_1, m_3, m_5, m_10]
      raw_d: D_t (unscaled debt for residual addition)
    """
    def __init__(
        self,
        df: pd.DataFrame,
        group_cols: Optional[List[str]] = None,
        horizons: Tuple[int, ...] = (1, 3, 5, 10)
    ):
        self.horizons = list(horizons)
        self.data = df.copy()

        # Identify driver, stint, and lap columns
        driver_col = 'driver' if 'driver' in self.data.columns else ('DriverNumber' if 'DriverNumber' in self.data.columns else 'driver_id')
        stint_col = 'stint_num' if 'stint_num' in self.data.columns else ('Stint' if 'Stint' in self.data.columns else 'stint_id')
        lap_col = 'LapNumber' if 'LapNumber' in self.data.columns else 'lap_number'
        comp_col = 'compound' if 'compound' in self.data.columns else 'Compound'
        event_col = 'round' if 'round' in self.data.columns else ('event_name' if 'event_name' in self.data.columns else 'EventName')

        if group_cols is None:
            group_cols = [c for c in [event_col, driver_col, stint_col] if c in self.data.columns]
        self.group_cols = group_cols

        self.continuous_samples = []  # [D, Delta_D, Delta2_D, TyreLife, FuelProxy]
        self.compound_samples = []    # one-hot (6)
        self.raw_d_samples = []        # raw D
        self.targets = []              # [D_+1, D_+3, D_+5, D_+10]
        self.masks = []                # [m_1, m_3, m_5, m_10]

        # Group by stint to preserve chronological boundaries
        for _, group in self.data.groupby(self.group_cols, sort=False):
            group = group.sort_values(lap_col).reset_index(drop=True)
            num_laps = len(group)

            for i in range(num_laps):
                row = group.iloc[i]
                d_val = float(row['D'])
                delta_d = float(row['Delta_D'])
                delta2_d = float(row['Delta2_D'])
                tyre_life = float(row['TyreLife'])
                fuel_proxy = float(row['FuelProxy'])
                comp_str = str(row[comp_col])

                cont = [d_val, delta_d, delta2_d, tyre_life, fuel_proxy]
                comp_oh = one_hot_compound(comp_str)

                # Future targets with genuine masking
                t_list = []
                m_list = []
                for h in self.horizons:
                    if i + h < num_laps:
                        t_list.append(float(group.iloc[i + h]['D']))
                        m_list.append(1.0)
                    else:
                        t_list.append(0.0)  # masked out
                        m_list.append(0.0)

                self.continuous_samples.append(cont)
                self.compound_samples.append(comp_oh)
                self.raw_d_samples.append(d_val)
                self.targets.append(t_list)
                self.masks.append(m_list)

        self.continuous_array = np.array(self.continuous_samples, dtype=np.float32)
        self.compound_array = np.array(self.compound_samples, dtype=np.float32)
        self.raw_d_array = np.array(self.raw_d_samples, dtype=np.float32)
        self.targets_array = np.array(self.targets, dtype=np.float32)
        self.masks_array = np.array(self.masks, dtype=np.float32)

        self.scaled_continuous = self.continuous_array.copy()

    def fit_scaler(self) -> FeatureScaler:
        """Fits scaler on continuous features (ONLY on training split)."""
        scaler = FeatureScaler()
        scaler.fit(self.continuous_array)
        self.scaled_continuous = scaler.transform(self.continuous_array)
        return scaler

    def apply_scaler(self, scaler: FeatureScaler):
        """Applies an existing scaler (e.g. from training split to validation split)."""
        self.scaled_continuous = scaler.transform(self.continuous_array)

    def __len__(self):
        return len(self.raw_d_samples)

    def __getitem__(self, idx):
        # Concatenate scaled continuous (5) + compound one-hot (6) -> 11 inputs
        x = np.concatenate([self.scaled_continuous[idx], self.compound_array[idx]], axis=0)
        y = self.targets_array[idx]
        mask = self.masks_array[idx]
        raw_d = self.raw_d_array[idx]

        return (
            torch.tensor(x, dtype=torch.float32),
            torch.tensor(y, dtype=torch.float32),
            torch.tensor(mask, dtype=torch.float32),
            torch.tensor(raw_d, dtype=torch.float32)
        )


def create_tdsm_dataloader(
    df_or_csv,
    horizons=(1, 3, 5, 10),
    batch_size: int = 64,
    shuffle: bool = True,
    num_workers: int = 0
) -> Tuple[TDSMDataset, DataLoader]:
    """Creates a masked multi-horizon TDSMDataset and corresponding DataLoader."""
    if isinstance(df_or_csv, str):
        df = pd.read_parquet(df_or_csv) if df_or_csv.endswith('.parquet') else pd.read_csv(df_or_csv)
    else:
        df = df_or_csv

    dataset = TDSMDataset(df, horizons=horizons)
    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        drop_last=False
    )
    return dataset, dataloader
