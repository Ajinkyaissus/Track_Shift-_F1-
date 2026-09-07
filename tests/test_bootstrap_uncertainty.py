"""
tests/test_bootstrap_uncertainty.py — Tests for:
1. Empirical cluster/stint bootstrap percentile intervals
2. Percentile ordering (q0.025 <= q0.50 <= q0.975)
3. Bootstrap reproducibility with fixed random seed
4. Precomputed uncertainty table validation
"""

import os
import json
import pytest
import numpy as np
import pandas as pd

from pipeline.uncertainty_bootstrap import run_stint_bootstrap

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
REPORTS_DIR = os.path.join(BASE_DIR, "reports")
BOOTSTRAP_PARQUET = os.path.join(DATA_DIR, "bootstrap_uncertainty.parquet")
UNCERTAINTY_JSON = os.path.join(REPORTS_DIR, "uncertainty_validation.json")


def test_bootstrap_uncertainty_parquet_exists():
    """Verify that bootstrap_uncertainty.parquet exists and has valid schema."""
    assert os.path.exists(BOOTSTRAP_PARQUET), "bootstrap_uncertainty.parquet must exist"
    df = pd.read_parquet(BOOTSTRAP_PARQUET)
    assert len(df) > 100
    for col in ["stint_id", "feature", "delta_pct", "recovered_p50", "ci_lower", "ci_upper", "ci_margin", "is_saturated"]:
        assert col in df.columns


def test_bootstrap_percentile_ordering():
    """Verify that empirical bootstrap confidence intervals satisfy lower <= median <= upper."""
    df = pd.read_parquet(BOOTSTRAP_PARQUET)
    
    # Check on all rows
    valid_order = (df["ci_lower"] <= df["recovered_p50"] + 1e-5) & (df["recovered_p50"] <= df["ci_upper"] + 1e-5)
    assert valid_order.all(), "All bootstrap intervals must satisfy lower <= median <= upper"


def test_bootstrap_reproducibility():
    """Verify that two bootstrap runs with the same seed generate identical percentile intervals."""
    res1 = run_stint_bootstrap(n_bootstrap=50, seed=123)
    res2 = run_stint_bootstrap(n_bootstrap=50, seed=123)

    for feat in ["braking_aggression", "throttle_transient_smoothness", "kerb_usage"]:
        ci1 = res1["coefficients_bootstrap_summary"][feat]["ci_95"]
        ci2 = res2["coefficients_bootstrap_summary"][feat]["ci_95"]
        np.testing.assert_allclose(ci1, ci2, rtol=1e-5, atol=1e-5)


def test_uncertainty_json_report():
    """Verify that uncertainty_validation.json contains documented scientific metadata."""
    assert os.path.exists(UNCERTAINTY_JSON), "reports/uncertainty_validation.json must exist"
    with open(UNCERTAINTY_JSON, "r") as f:
        data = json.load(f)
        assert data["method"] == "stint_cluster_bootstrap"
        assert data["confidence_level"] == 0.95
        assert data["n_bootstrap"] >= 50
        assert "coefficients_bootstrap_summary" in data
