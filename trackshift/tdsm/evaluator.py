"""
trackshift/tdsm/evaluator.py — Scientific Evaluation & Metrics Generator for TDSM.
"""

import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score


class TDSMEvaluator:
    """
    Computes rigorous holdout evaluation metrics across horizons, tyre compounds, and tyre age buckets.
    """
    @staticmethod
    def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
        """
        Computes MAE, RMSE, MedianAE, Bias, R2, and N.
        """
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        valid_true = y_true[mask]
        valid_pred = y_pred[mask]
        n = len(valid_true)

        if n == 0:
            return {
                "MAE": None,
                "RMSE": None,
                "MedianAE": None,
                "Bias": None,
                "R2": None,
                "N": 0
            }

        mae = float(mean_absolute_error(valid_true, valid_pred))
        rmse = float(np.sqrt(mean_squared_error(valid_true, valid_pred)))
        med_ae = float(np.median(np.abs(valid_true - valid_pred)))
        bias = float(np.mean(valid_pred - valid_true))

        # R2 score (if variance > 0 and n >= 10)
        var_true = float(np.var(valid_true))
        if var_true > 1e-6 and n >= 10:
            r2 = float(r2_score(valid_true, valid_pred))
        else:
            r2 = None

        return {
            "MAE": round(mae, 4),
            "RMSE": round(rmse, 4),
            "MedianAE": round(med_ae, 4),
            "Bias": round(bias, 4),
            "R2": round(r2, 4) if r2 is not None else None,
            "N": int(n)
        }

    @classmethod
    def evaluate_ledger(cls, ledger_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Evaluates prediction ledger containing actuals and predictions for +1, +3, +5, +10.
        """
        metrics = {
            "overall": {},
            "by_horizon": {},
            "by_compound": {},
            "by_tyre_age": {},
            "dataset_summary": {
                "total_rows": int(len(ledger_df)),
                "num_events": int(ledger_df['event'].nunique()) if 'event' in ledger_df.columns else 0,
                "num_sessions": int(ledger_df['session'].nunique()) if 'session' in ledger_df.columns else 0,
                "num_drivers": int(ledger_df['driver'].nunique()) if 'driver' in ledger_df.columns else 0,
                "num_stints": int(ledger_df.groupby(['event', 'driver', 'stint']).ngroups) if all(c in ledger_df.columns for c in ['event', 'driver', 'stint']) else 0
            }
        }

        horizons = [1, 3, 5, 10]

        # 1. Per Horizon Metrics
        for h in horizons:
            act_col = f"actual_plus_{h}"
            pred_col = f"prediction_plus_{h}"
            if act_col in ledger_df.columns and pred_col in ledger_df.columns:
                h_metrics = cls.compute_metrics(
                    ledger_df[act_col].values,
                    ledger_df[pred_col].values
                )
                metrics["by_horizon"][f"+{h}"] = h_metrics

        # 2. Per Compound Metrics
        comp_col = 'tyre_compound' if 'tyre_compound' in ledger_df.columns else ('compound' if 'compound' in ledger_df.columns else None)
        if comp_col:
            for comp in ledger_df[comp_col].dropna().unique():
                comp_str = str(comp).upper()
                metrics["by_compound"][comp_str] = {}
                sub_df = ledger_df[ledger_df[comp_col] == comp]
                for h in horizons:
                    act_col = f"actual_plus_{h}"
                    pred_col = f"prediction_plus_{h}"
                    if act_col in sub_df.columns and pred_col in sub_df.columns:
                        metrics["by_compound"][comp_str][f"+{h}"] = cls.compute_metrics(
                            sub_df[act_col].values,
                            sub_df[pred_col].values
                        )

        # 3. Per Tyre Age Bucket Metrics
        age_col = 'tyre_life' if 'tyre_life' in ledger_df.columns else ('tyre_age' if 'tyre_age' in ledger_df.columns else None)
        if age_col:
            bins = [0, 5, 10, 15, 20, 100]
            labels = ["0-5", "6-10", "11-15", "16-20", "21+"]
            ledger_df['age_bucket'] = pd.cut(ledger_df[age_col], bins=bins, labels=labels, right=True)

            for bucket in labels:
                sub_df = ledger_df[ledger_df['age_bucket'] == bucket]
                if not sub_df.empty:
                    metrics["by_tyre_age"][bucket] = {}
                    for h in horizons:
                        act_col = f"actual_plus_{h}"
                        pred_col = f"prediction_plus_{h}"
                        if act_col in sub_df.columns and pred_col in sub_df.columns:
                            metrics["by_tyre_age"][bucket][f"+{h}"] = cls.compute_metrics(
                                sub_df[act_col].values,
                                sub_df[pred_col].values
                            )

        return metrics
