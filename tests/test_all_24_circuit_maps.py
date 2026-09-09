"""
tests/test_all_24_circuit_maps.py — Universal Map Verification for all 24 Formula 1 Circuits
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

ALL_24_CIRCUITS = [
    "bahrain", "jeddah", "albert_park", "suzuka", "shanghai", "miami",
    "imola", "monaco", "montreal", "catalunya", "red_bull_ring", "silverstone",
    "hungaroring", "spa", "zandvoort", "monza", "baku", "singapore",
    "cota", "rodriguez", "interlagos", "las_vegas", "losail", "abu_dhabi"
]

def test_all_24_circuits_exist_in_circuits_list():
    resp = client.get("/circuits")
    assert resp.status_code == 200
    circuits = resp.json()
    assert len(circuits) >= 24
    found_ids = {c["circuit_id"] for c in circuits}
    for cid in ALL_24_CIRCUITS:
        assert cid in found_ids, f"Circuit {cid} missing from /circuits"

@pytest.mark.parametrize("circuit_id", ALL_24_CIRCUITS)
def test_each_of_24_circuits_returns_valid_geometry_map(circuit_id):
    resp = client.get(f"/circuits/{circuit_id}/map")
    assert resp.status_code == 200, f"Map for {circuit_id} returned status {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["circuit_id"] == circuit_id
    assert "points" in data
    assert len(data["points"]) > 100, f"Circuit {circuit_id} should have > 100 points, got {len(data['points'])}"
    assert "corners" in data
    assert len(data["corners"]) >= 10, f"Circuit {circuit_id} should have >= 10 corners, got {len(data['corners'])}"
    assert "sectors" in data and len(data["sectors"]) >= 3
    assert "drs_zones" in data
    assert "pit_lane" in data
    
    # Verify coordinate attributes
    first_pt = data["points"][0]
    assert "x" in first_pt or "x_rot" in first_pt
    assert "y" in first_pt or "y_rot" in first_pt
    assert "speed" in first_pt
