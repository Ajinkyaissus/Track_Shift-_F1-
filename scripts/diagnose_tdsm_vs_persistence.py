"""
scripts/diagnose_tdsm_vs_persistence.py

Tests one specific hypothesis: the noise floor increased the fraction of
"flat" horizon targets (actual_plus_h == D, i.e. no real change over the
window). Persistence trivially scores ~0 error on flat targets (it predicts
"no change"). TDSM, as a continuous regressor, essentially never outputs an
exact repeat of D, so it pays a small penalty on every flat lap. If flat laps
are now the majority, that alone could explain TDSM's higher MAE even while
it's better calibrated (lower bias, better RMSE) on the laps that actually
have real degradation.

This does NOT re-run the model -- it works entirely from the per-lap
predictions CSV that scripts/validate_2025.py already writes
(artifacts/validation_2025/tdsm_predictions_2025.csv), so it's fast and safe
to run repeatedly.

Usage:
    python scripts/diagnose_tdsm_vs_persistence.py

Adjust PREDICTIONS_CSV below if your v2 validation run wrote to a different
path (e.g. tdsm_predictions_2025_v2.csv).
"""

import os
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PREDICTIONS_CSV = os.path.join(BASE_DIR, "artifacts", "validation_2025", "tdsm_predictions_2025.csv")
HORIZONS = (1, 3, 5, 10)
FLAT_EPSILON = 1e-3  # treat |actual_plus_h - D| below this as "no real change"


def persistence_pred(df, h):
    return df["D"]  # persistence predicts "unchanged from now"


def trend_pred(df, h):
    # matches the standard trend baseline: extrapolate current Delta_D forward
    return df["D"] + df["Delta_D"] * h


def diagnose():
    if not os.path.exists(PREDICTIONS_CSV):
        raise FileNotFoundError(
            f"{PREDICTIONS_CSV} not found. Point PREDICTIONS_CSV at wherever "
            "your v2 validate_2025.py run wrote its per-lap predictions."
        )

    df = pd.read_csv(PREDICTIONS_CSV)
    print(f"Loaded {len(df):,} rows from {PREDICTIONS_CSV}\n")

    for h in HORIZONS:
        actual_col = f"actual_plus_{h}"
        pred_col = f"prediction_plus_{h}"
        if actual_col not in df.columns or pred_col not in df.columns:
            print(f"[horizon +{h}] columns not found, skipping")
            continue

        sub = df.dropna(subset=[actual_col, pred_col, "D", "Delta_D"]).copy()
        sub["is_flat"] = (sub[actual_col] - sub["D"]).abs() < FLAT_EPSILON

        n_total = len(sub)
        n_flat = sub["is_flat"].sum()
        n_changed = n_total - n_flat

        tdsm_err = (sub[pred_col] - sub[actual_col]).abs()
        pers_err = (persistence_pred(sub, h) - sub[actual_col]).abs()
        trend_err = (trend_pred(sub, h) - sub[actual_col]).abs()

        print(f"=== Horizon +{h} ===")
        print(f"  Total laps: {n_total:,}   Flat targets: {n_flat:,} ({n_flat/n_total*100:.1f}%)   "
              f"Changed targets: {n_changed:,} ({n_changed/n_total*100:.1f}%)")

        print(f"  {'':20s} {'Overall MAE':>12s} {'Flat-only MAE':>15s} {'Changed-only MAE':>18s}")
        for name, err in [("TDSM v2", tdsm_err), ("Persistence", pers_err), ("Trend", trend_err)]:
            overall = err.mean()
            flat_mae = err[sub["is_flat"]].mean() if n_flat > 0 else float("nan")
            changed_mae = err[~sub["is_flat"]].mean() if n_changed > 0 else float("nan")
            print(f"  {name:20s} {overall:12.4f} {flat_mae:15.4f} {changed_mae:18.4f}")

        # Bias specifically on changed (real degradation) laps -- this is where
        # persistence's systematic underestimation should show up as a large
        # negative number, and TDSM should look better calibrated.
        changed = sub[~sub["is_flat"]]
        if len(changed) > 0:
            tdsm_bias = (changed[pred_col] - changed[actual_col]).mean()
            pers_bias = (persistence_pred(changed, h) - changed[actual_col]).mean()
            print(f"  Bias on CHANGED laps only -- TDSM: {tdsm_bias:+.4f}s   Persistence: {pers_bias:+.4f}s")
        print()

    print("=" * 70)
    print("How to read this:")
    print("- If 'Flat-only MAE' for Persistence is near 0 and for TDSM is NOT near 0,")
    print("  the hypothesis is confirmed: TDSM's overall MAE loss is being driven by")
    print("  paying a small penalty on every flat lap, not by being bad at real")
    print("  degradation prediction.")
    print("- If 'Changed-only MAE' for TDSM is lower than Persistence's, and TDSM's")
    print("  bias on changed laps is much closer to zero than Persistence's, that's")
    print("  your evidence that TDSM is actually the better model WHERE IT MATTERS")
    print("  (real degradation events), and the honest fix is either (a) present the")
    print("  segmented result instead of the single blended MAE, or (b) add a small")
    print("  'predict zero when nothing suggests a change' inductive bias to the loss")
    print("  (e.g. an L1 penalty on the predicted delta when Delta_D and Delta2_D are")
    print("  both ~0) so TDSM stops paying tax on flat laps it should just skip.")


if __name__ == "__main__":
    diagnose()
