"""
trackshift/tdsm/preprocessing.py — Causal Preprocessing & Feature Engineering for TDSM.
"""

import os
import json
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, Optional

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "configs", "feature_config.json")
if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        _CFG = json.load(f)
    DEFAULT_COMPOUND_MAP = _CFG.get("compound_mapping", {})
else:
    DEFAULT_COMPOUND_MAP = {
        'SOFT': 0, 'MEDIUM': 1, 'HARD': 2, 'INTERMEDIATE': 3, 'WET': 4, 'UNKNOWN': 5
    }

from trackshift.domain_constants import FUEL_EFFECT_COEFFICIENT

# Empirical MAD-based noise floor defaults per compound (fitted on 2024 R1-18)
DEFAULT_SIGMA_BY_COMPOUND: Dict[str, float] = {
    'SOFT': 0.3996,
    'HARD': 0.3536,
    'MEDIUM': 0.3700,
    'INTERMEDIATE': 0.3800,
    'WET': 0.3800,
    'UNKNOWN': 0.3800,
}


class TDSMPreprocessor:
    """
    Causal Feature Engineering and Normalization Pipeline for TDSM.
    
    Guarantees:
    - Never uses future rows to compute current features.
    - Never computes deltas across drivers, stints, sessions, or events.
    - Fits scaling / normalization statistics STRICTLY on 2024 training data.
    - Computes a MAD-based noise floor per compound to filter lap time jitter.
    - D is monotonically non-decreasing within every stint (diff() >= -1e-6).
    """
    def __init__(
        self,
        compound_map: Optional[Dict[str, int]] = None,
        sigma_by_compound: Optional[Dict[str, float]] = None
    ):
        self.compound_map = compound_map or DEFAULT_COMPOUND_MAP
        self.sigma_by_compound_ = dict(sigma_by_compound or DEFAULT_SIGMA_BY_COMPOUND)
        self.fitted = False
        self.feature_means = {}
        self.feature_stds = {}
        self.feature_names = ["D", "Delta_D", "Delta2_D", "TyreLife", "CompoundIdx", "FuelProxy"]

    def fit_noise_floor(self, train_df: pd.DataFrame) -> Dict[str, float]:
        """
        Fits MAD-based lap time noise floor per compound strictly on training green-flag laps.
        sigma = 1.4826 * median(|x - median(x)|) of within-stint lap-to-lap fuel-corrected deltas.
        """
        df = train_df.copy()
        driver_col = 'driver' if 'driver' in df.columns else ('DriverNumber' if 'DriverNumber' in df.columns else 'driver_id')
        stint_col = 'stint_num' if 'stint_num' in df.columns else ('Stint' if 'Stint' in df.columns else 'stint_id')
        lap_col = 'LapNumber' if 'LapNumber' in df.columns else 'lap_number'
        comp_col = 'compound' if 'compound' in df.columns else ('Compound' if 'Compound' in df.columns else 'CompoundIdx')
        event_col = 'round' if 'round' in df.columns else ('event_name' if 'event_name' in df.columns else 'event')
        season_col = 'season' if 'season' in df.columns else ('year' if 'year' in df.columns else None)

        group_keys = [c for c in [season_col, event_col, driver_col, stint_col] if c is not None and c in df.columns]
        if not group_keys:
            return self.sigma_by_compound_

        # Ensure fuel_corrected_lap_time
        if 'fuel_corrected_lap_time' not in df.columns:
            lap_time_col = 'lap_time_s' if 'lap_time_s' in df.columns else 'lap_time'
            fuel_col = 'fuel_kg' if 'fuel_kg' in df.columns else ('fuel_load_est' if 'fuel_load_est' in df.columns else 'FuelProxy')
            fuel_vals = df[fuel_col] if fuel_col in df.columns else 50.0
            df['fuel_corrected_lap_time'] = df[lap_time_col] - FUEL_EFFECT_COEFFICIENT * fuel_vals

        sort_keys = group_keys + ([lap_col] if lap_col in df.columns else [])
        df = df.sort_values(sort_keys).reset_index(drop=True)
        df['fc_delta'] = df.groupby(group_keys)['fuel_corrected_lap_time'].diff()

        if comp_col in df.columns:
            for comp in df[comp_col].dropna().unique():
                comp_str = str(comp).strip().upper()
                c_deltas = df[df[comp_col] == comp]['fc_delta'].dropna()
                # Clean green-flag racing deltas (exclude pit stops / SC jumps)
                clean_deltas = c_deltas[c_deltas.abs() < 5.0]
                if len(clean_deltas) >= 20:
                    med = clean_deltas.median()
                    mad = 1.4826 * (clean_deltas - med).abs().median()
                    # Sanity bounds: 0.1s to 1.5s
                    sigma_val = float(np.clip(mad, 0.10, 1.50))
                    self.sigma_by_compound_[comp_str] = round(sigma_val, 4)

        return self.sigma_by_compound_

    def extract_canonical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Derives D, Delta_D, Delta2_D, TyreLife, CompoundIdx, FuelProxy strictly causally.
        Computes MAD-based noise floor filtered cumulative D (monotonically non-decreasing).
        """
        data = df.copy()

        # Identify standard columns
        driver_col = 'driver' if 'driver' in data.columns else ('DriverNumber' if 'DriverNumber' in data.columns else 'driver_id')
        stint_col = 'stint_num' if 'stint_num' in data.columns else ('Stint' if 'Stint' in data.columns else 'stint_id')
        lap_col = 'LapNumber' if 'LapNumber' in data.columns else 'lap_number'
        comp_col = 'compound' if 'compound' in data.columns else ('Compound' if 'Compound' in data.columns else 'CompoundIdx')
        event_col = 'round' if 'round' in data.columns else ('event_name' if 'event_name' in data.columns else 'event')
        season_col = 'season' if 'season' in data.columns else ('year' if 'year' in data.columns else None)

        sort_cols = [c for c in [season_col, event_col, driver_col, stint_col, lap_col] if c is not None and c in data.columns]
        data = data.sort_values(sort_cols).reset_index(drop=True)

        # Standardize Compound
        if comp_col in data.columns and data[comp_col].dtype == object:
            data['CompoundIdx'] = data[comp_col].map(lambda x: self.compound_map.get(str(x).upper(), 5)).astype(int)
        elif 'CompoundIdx' not in data.columns:
            data['CompoundIdx'] = 5

        # Standardize FuelProxy
        if 'FuelProxy' not in data.columns:
            if 'fuel_kg' in data.columns:
                data['FuelProxy'] = data['fuel_kg'].astype(float)
            elif 'fuel_load_est' in data.columns:
                data['FuelProxy'] = data['fuel_load_est'].astype(float)
            else:
                data['FuelProxy'] = 50.0

        # Standardize TyreLife
        if 'TyreLife' not in data.columns:
            if 'tyre_age' in data.columns:
                data['TyreLife'] = data['tyre_age'].astype(float)
            elif 'tyre_life' in data.columns:
                data['TyreLife'] = data['tyre_life'].astype(float)
            else:
                data['TyreLife'] = 1.0

        # Compute fuel-corrected lap time if not present
        if 'fuel_corrected_lap_time' not in data.columns:
            lap_time_col = 'lap_time_s' if 'lap_time_s' in data.columns else 'lap_time'
            if lap_time_col in data.columns:
                data['fuel_corrected_lap_time'] = data[lap_time_col] - FUEL_EFFECT_COEFFICIENT * data['FuelProxy']
            else:
                data['fuel_corrected_lap_time'] = 90.0

        # Compute D, Delta_D, Delta2_D chronologically per driver and stint
        group_keys = [c for c in [season_col, event_col, driver_col, stint_col] if c is not None and c in data.columns]

        all_d = []
        all_delta_d = []
        all_delta2_d = []

        for _, group in data.groupby(group_keys, sort=False):
            fc_times = group['fuel_corrected_lap_time'].values
            n_laps = len(fc_times)
            
            # Determine stint compound and its MAD noise floor
            if comp_col in group.columns:
                c_str = str(group[comp_col].iloc[0]).strip().upper()
                sigma = self.sigma_by_compound_.get(c_str, self.sigma_by_compound_.get('UNKNOWN', 0.38))
            else:
                sigma = 0.38

            # Causal base pace: running minimum of first 3 laps, fixed afterwards
            d_vals = np.zeros(n_laps, dtype=np.float32)
            running_base = fc_times[0]
            running_d = 0.0
            
            for i in range(n_laps):
                if i < 3:
                    running_base = min(running_base, fc_times[i])
                # Non-negative degradation relative to stint initial clean baseline
                raw_loss = max(0.0, float(fc_times[i] - running_base))
                # MAD-based noise floor: only degradation exceeding stochastic noise contributes
                floored_loss = max(0.0, float(raw_loss - sigma))
                # Genuinely cumulative & monotonic: irreversible tyre performance degradation
                running_d = max(running_d, floored_loss)
                d_vals[i] = running_d
            
            delta_d_vals = np.zeros(n_laps, dtype=np.float32)
            delta2_d_vals = np.zeros(n_laps, dtype=np.float32)
            
            for i in range(1, n_laps):
                delta_d_vals[i] = d_vals[i] - d_vals[i - 1]
            for i in range(2, n_laps):
                delta2_d_vals[i] = delta_d_vals[i] - delta_d_vals[i - 1]

            all_d.extend(d_vals)
            all_delta_d.extend(delta_d_vals)
            all_delta2_d.extend(delta2_d_vals)

        data['D'] = all_d
        data['Delta_D'] = all_delta_d
        data['Delta2_D'] = all_delta2_d

        return data

    def fit(self, train_df: pd.DataFrame):
        """
        Fits noise floor and feature summary statistics strictly on 2024 training data.
        """
        self.fit_noise_floor(train_df)
        feat_df = self.extract_canonical_features(train_df)
        for col in self.feature_names:
            self.feature_means[col] = float(feat_df[col].mean())
            self.feature_stds[col] = float(feat_df[col].std()) if feat_df[col].std() > 1e-6 else 1.0
        self.fitted = True

    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extracts canonical features.
        """
        return self.extract_canonical_features(df)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fitted": self.fitted,
            "feature_names": self.feature_names,
            "feature_means": self.feature_means,
            "feature_stds": self.feature_stds,
            "compound_map": self.compound_map,
            "sigma_by_compound_": self.sigma_by_compound_,
            "fuel_coefficient": FUEL_EFFECT_COEFFICIENT
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TDSMPreprocessor":
        prep = cls(
            compound_map=d.get("compound_map"),
            sigma_by_compound=d.get("sigma_by_compound_")
        )
        prep.fitted = d.get("fitted", False)
        prep.feature_names = d.get("feature_names", ["D", "Delta_D", "Delta2_D", "TyreLife", "CompoundIdx", "FuelProxy"])
        prep.feature_means = d.get("feature_means", {})
        prep.feature_stds = d.get("feature_stds", {})
        return prep
