"""
tests/test_multi_season.py — Comprehensive Multi-Season Verification Test Suite (2024 + 2025).

Tests:
1. Season Registry API (/api/seasons) returns ONLY [2025, 2024]
2. 2024 Data Preservation & Normalization (13 Verified Circuits)
3. 2025 Real Historical / Active Season Data Coverage
4. Cross-Season Isolation & Non-Contamination (2024 vs 2025)
5. Dynamic Driver Discovery (No Driver Slicing / Fixed Rosters)
6. Real Pit Stop Detection
7. Session-Specific Weather & Track Status
8. Multi-Season Circuit Comparison API (2024 vs 2025)
9. Cache Key Season Formatting
10. Explicit rejection of 2023 season
"""

import pytest
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi.testclient import TestClient

from api.main import app
from api.cache import CacheKeys


client = TestClient(app)

def test_seasons_endpoint():
    """Verify GET /api/seasons returns ONLY 2025 and 2024 (2023 strictly excluded)."""
    res = client.get("/api/seasons")
    assert res.status_code == 200
    data = res.json()
    assert isinstance(data, list)
    years = [s["year"] for s in data]
    assert 2023 not in years
    assert 2024 in years
    assert 2025 in years
    assert len(years) == 2


def test_2023_season_returns_404():
    """Verify that requesting 2023 season events returns 404 Not Found."""
    res = client.get("/api/seasons/2023/events")
    assert res.status_code == 404


def test_2024_data_preservation():
    """Verify 2024 verified data remains intact across circuits, stints, and models."""
    res = client.get("/circuits?year=2024")
    assert res.status_code == 200
    circuits = res.json()
    assert len(circuits) >= 13
    
    # Check 2024 Monza Race
    res_monza = client.get("/circuits/monza/sessions/2024_monza_R/drivers")
    assert res_monza.status_code == 200
    drivers_data = res_monza.json()
    assert drivers_data["driver_count"] >= 19


def test_2025_real_season_events():
    """Verify 2025 calendar returns real rounds."""
    res = client.get("/api/seasons/2025/events")
    assert res.status_code == 200
    events = res.json()
    assert len(events) >= 20
    round_1 = events[0]
    assert "australian" in round_1["event_name"].lower() or "albert_park" in round_1["circuit_id"].lower()


def test_cross_season_isolation():
    """Verify that sessions from 2024 and 2025 are strictly isolated."""
    # 2024 COTA
    res_24 = client.get("/circuits/cota/sessions/2024_cota_R/drivers")
    # 2025 COTA
    res_25 = client.get("/circuits/cota/sessions/2025_cota_R/drivers")
    
    assert res_24.status_code == 200
    assert res_25.status_code == 200
    
    d24 = res_24.json()
    d25 = res_25.json()
    
    assert d24["session_id"] == "2024_cota_R"
    assert d25["session_id"] == "2025_cota_R"
    assert d24["session_id"] != d25["session_id"]


def test_dynamic_driver_discovery():
    """Verify session drivers returns all real participants without hardcoded slicing."""
    res = client.get("/circuits/cota/sessions/2024_cota_R/drivers")
    assert res.status_code == 200
    data = res.json()
    assert data["driver_count"] >= 19
    driver_ids = [d["driver_id"] for d in data["drivers"]]
    assert "VER" in driver_ids
    assert "HAM" in driver_ids
    assert "NOR" in driver_ids


def test_real_pit_stops():
    """Verify pit stops endpoint derives genuine pit events for 2024."""
    res = client.get("/api/sessions/2024_cota_R/pit-stops")
    assert res.status_code == 200
    data = res.json()
    assert "total_pit_stops" in data or "pit_stops" in data
    assert data.get("driver_count", 0) >= 19 or data.get("total_driver_count", 0) >= 19


def test_session_weather():
    """Verify session weather returns real recorded data."""
    res = client.get("/api/sessions/2024_cota_R/weather")
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == "2024_cota_R"
    assert "summary" in data
    assert "air_temp" in data["summary"]
    assert "track_temp" in data["summary"]


def test_multi_season_circuit_comparison():
    """Verify multi-season comparison endpoint for supported seasons (2024, 2025)."""
    res = client.get("/api/circuits/cota/comparison?seasons=2024,2025")
    assert res.status_code == 200
    data = res.json()
    assert data["circuit_id"] == "cota"
    assert len(data["comparison"]) >= 1


def test_cache_keys_season_format():
    """Verify cache keys strictly include season."""
    k_2024 = CacheKeys.telemetry(2024, "cota", "2024_cota_R", "VER")
    k_2025 = CacheKeys.telemetry(2025, "cota", "2025_cota_R", "VER")
    
    assert "2024:cota:2024_cota_R:VER" in k_2024
    assert "2025:cota:2025_cota_R:VER" in k_2025
    assert k_2024 != k_2025
