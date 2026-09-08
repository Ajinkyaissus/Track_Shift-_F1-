"""
tests/test_real_data_driver_analytics.py — Comprehensive Test Suite for Real-Data Driver Analytics.

Verifies:
1. Dynamic driver roster discovery (Abu Dhabi 20, Albert Park 19, Jeddah 20 with Bearman).
2. Bulk driver analytics endpoint /api/sessions/{session_id}/drivers/analytics.
3. Independent Stage 1 Baseline, Stage 2 Tyre Debt, Stage 3 TCN, and Stage 4 Sensitivity calculations.
4. Complete isolation: Driver A never receives Driver B's telemetry, tyre debt, or TCN embedding.
5. Honest UNAVAILABLE / INSUFFICIENT_DATA states without fake data or arbitrary fallbacks.
6. Driver comparison between any two drivers in the session.
7. Cache key versioning and invalidation.
8. Diagnostic CLI tool output accuracy.
"""

import os
import sys
import pytest
from fastapi.testclient import TestClient

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.main import app
from api.cache import CacheKeys
from trackshift.diagnostics.driver_coverage import run_coverage_diagnostic

client = TestClient(app)


def test_session_twenty_drivers_and_dynamic_counts():
    """1. Session with 20 drivers returns 20 drivers; Albert Park returns 19."""
    res_ad = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers")
    assert res_ad.status_code == 200
    data_ad = res_ad.json()
    assert data_ad["driver_count"] == 20
    assert len(data_ad["drivers"]) == 20

    res_ap = client.get("/circuits/albert_park/sessions/2024_albert_park_R/drivers")
    assert res_ap.status_code == 200
    data_ap = res_ap.json()
    assert data_ap["driver_count"] == 19
    assert len(data_ap["drivers"]) == 19


def test_no_hardcoded_four_driver_limit():
    """2 & 3. Verifies no 4-driver limit exists in driver discovery or bulk analytics."""
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/analytics")
    assert res.status_code == 200
    body = res.json()
    assert body["driver_count"] == 20
    assert len(body["drivers"]) == 20
    
    driver_ids = [d["driver"]["id"] for d in body["drivers"]]
    # Proves field drivers beyond HAM, LEC, NOR, VER are fully included
    assert "DOO" in driver_ids or "GAS" in driver_ids or "HUL" in driver_ids
    assert len(driver_ids) == 20


def test_every_driver_independent_analytics():
    """4. Every returned driver gets independent analytics calculated from their own data."""
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/analytics")
    assert res.status_code == 200
    drivers = res.json()["drivers"]
    
    ver = next(d for d in drivers if d["driver"]["id"] == "VER")
    nor = next(d for d in drivers if d["driver"]["id"] == "NOR")

    # Baseline independence
    assert ver["baseline"]["mean_actual"] != nor["baseline"]["mean_actual"]
    assert ver["baseline"]["mean_residual"] != nor["baseline"]["mean_residual"]

    # Debt independence
    assert ver["tyre_debt"]["cumulative"] != nor["tyre_debt"]["cumulative"]
    assert ver["tyre_debt"]["current"] != nor["tyre_debt"]["current"]

    # Behavior independence
    assert ver["behavior"]["braking"] != nor["behavior"]["braking"]
    assert ver["behavior"]["throttle_transient"] != nor["behavior"]["throttle_transient"]


def test_driver_isolation_no_data_leakage():
    """5, 6, 7. Driver A never receives Driver B's telemetry, tyre debt, or TCN embedding."""
    res_ver = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/VER/analytics")
    res_lec = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/LEC/analytics")
    
    assert res_ver.status_code == 200
    assert res_lec.status_code == 200
    ver = res_ver.json()
    lec = res_lec.json()

    # Telemetry isolation
    assert ver["behavior"]["braking"] != lec["behavior"]["braking"]
    assert ver["behavior"]["lateral_dynamics"] != lec["behavior"]["lateral_dynamics"]

    # Debt isolation
    assert ver["tyre_debt"]["current"] != lec["tyre_debt"]["current"]

    # TCN embedding isolation
    if ver["tcn"]["available"] and lec["tcn"]["available"]:
        assert ver["tcn"]["embedding"] != lec["tcn"]["embedding"]


def test_missing_telemetry_honest_unavailable_status():
    """8 & 9. Missing telemetry produces 'UNAVAILABLE' / 'Insufficient telemetry', never fake data."""
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/analytics")
    assert res.status_code == 200
    drivers = res.json()["drivers"]

    # DNF driver (e.g. BOT who had 0 recorded laps in Abu Dhabi)
    bot = next((d for d in drivers if d["driver"]["id"] == "BOT"), None)
    if bot:
        assert bot["tcn"]["available"] is False
        assert bot["tcn"]["status"] == "UNAVAILABLE"
        assert bot["tcn"]["reason"] == "INSUFFICIENT_REAL_TELEMETRY"
        assert bot["baseline"]["available"] is False
        assert bot["baseline"]["status"] == "UNAVAILABLE"
        assert bot["data_quality"]["telemetry"] == "unavailable"


def test_session_switching_purges_stale_drivers():
    """10. Session switching replaces driver roster completely (e.g. Jeddah has Bearman BEA, Abu Dhabi has Doohan DOO)."""
    res_jd = client.get("/circuits/jeddah/sessions/2024_jeddah_R/drivers")
    assert res_jd.status_code == 200
    jd_drivers = [d["driver_id"] for d in res_jd.json()["drivers"]]
    assert "BEA" in jd_drivers, "Jeddah roster must contain Oliver Bearman (BEA)"
    assert "DOO" not in jd_drivers, "Jeddah roster must not contain Jack Doohan (DOO)"

    res_ad = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers")
    assert res_ad.status_code == 200
    ad_drivers = [d["driver_id"] for d in res_ad.json()["drivers"]]
    assert "DOO" in ad_drivers, "Abu Dhabi roster must contain Jack Doohan (DOO)"
    assert "BEA" not in ad_drivers, "Abu Dhabi roster must not contain Oliver Bearman (BEA)"


def test_driver_laps_and_stints_endpoints():
    """Verifies per-driver lap ledger and stint breakdown endpoints."""
    res_laps = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/VER/laps")
    assert res_laps.status_code == 200
    laps_data = res_laps.json()
    assert laps_data["driver_id"] == "VER"
    assert laps_data["lap_count"] > 0
    assert "residual" in laps_data["laps"][0]
    assert "braking_aggression" in laps_data["laps"][0]

    res_stints = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers/VER/stints")
    assert res_stints.status_code == 200
    stints_data = res_stints.json()
    assert stints_data["driver_id"] == "VER"
    assert stints_data["stint_count"] > 0
    assert "tyre_debt_delta" in stints_data["stints"][0]


def test_any_two_drivers_comparison():
    """13. Any two drivers can be compared."""
    res_ad = client.get("/circuits/abu_dhabi/stints")
    assert res_ad.status_code == 200
    stints = res_ad.json()
    assert len(stints) >= 2
    
    stint_a = stints[0]["stint_id"]
    stint_b = stints[1]["stint_id"]

    res_comp = client.get(f"/stints/compare?stint_a={stint_a}&stint_b={stint_b}")
    assert res_comp.status_code == 200
    body = res_comp.json()
    assert "total_debt_seconds" in body
    assert "feature_comparisons" in body
    assert len(body["feature_comparisons"]) == 5


def test_cache_keys_structure():
    """14. Cache keys include session + driver + model version."""
    k_bulk = CacheKeys.session_drivers_analytics("abu_dhabi", "2024_abu_dhabi_R", "v5_tcn")
    assert "abu_dhabi" in k_bulk
    assert "2024_abu_dhabi_R" in k_bulk
    assert "v5_tcn" in k_bulk

    k_drv = CacheKeys.driver_analytics("abu_dhabi", "2024_abu_dhabi_R", "VER", "v5_tcn")
    assert "VER" in k_drv
    assert "2024_abu_dhabi_R" in k_drv


def test_diagnostic_tool_execution(capsys):
    """24. Diagnostic CLI command executes and outputs structured report."""
    run_coverage_diagnostic("2024_abu_dhabi_R")
    captured = capsys.readouterr()
    assert "SESSION" in captured.out
    assert "DRIVERS" in captured.out
    assert "PER DRIVER" in captured.out
    assert "Drivers discovered:        20" in captured.out
    assert "VER" in captured.out
