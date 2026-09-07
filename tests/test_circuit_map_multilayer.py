import pytest
from fastapi.testclient import TestClient
from api.main import app
from api.services.circuits_service import CIRCUIT_FEATURES_MAP

client = TestClient(app)

ALL_13_CIRCUITS = [
    "monza", "spa", "silverstone", "monaco", "hungaroring",
    "bahrain", "jeddah", "abu_dhabi", "cota", "interlagos",
    "suzuka", "singapore", "albert_park"
]

def test_all_13_circuits_multilayer_metadata_and_geometry():
    """
    Verify every single one of the 13 verified circuits:
    1. Returns non-empty geometry points with authentic X/Y/rot and telemetry channels.
    2. Returns authentic corners from database.
    3. Exposes authentic FIA sectors (S1, S2, S3) with valid percentages and distances.
    4. Exposes authentic DRS zones (or empty list if no DRS).
    5. Exposes start/finish line.
    6. Exposes pit lane flags.
    """
    for circuit_id in ALL_13_CIRCUITS:
        resp = client.get(f"/circuits/{circuit_id}/map")
        assert resp.status_code == 200, f"Circuit map failed for {circuit_id}"
        data = resp.json()

        assert data["circuit_id"] == circuit_id
        assert "points" in data and len(data["points"]) > 50, f"Too few geometry points for {circuit_id}"
        
        # Verify first point structure
        p0 = data["points"][0]
        assert "x_rot" in p0 or "x" in p0
        assert "distance" in p0 or "Distance" in p0

        # Verify corners
        assert "corners" in data
        assert isinstance(data["corners"], list)

        # Verify sectors S1, S2, S3
        assert "sectors" in data
        sectors = data["sectors"]
        assert len(sectors) == 3, f"Expected 3 sectors for {circuit_id}, got {len(sectors)}"
        assert sectors[0]["id"] == 1
        assert sectors[1]["id"] == 2
        assert sectors[2]["id"] == 3
        assert sectors[0]["start_pct"] == 0.0
        assert sectors[2]["end_pct"] == 1.0

        # Verify DRS zones
        assert "drs_zones" in data
        assert isinstance(data["drs_zones"], list)
        for drs in data["drs_zones"]:
            assert "start_pct" in drs and "end_pct" in drs
            assert 0.0 <= drs["start_pct"] < drs["end_pct"] <= 1.0

        # Verify start/finish
        assert "start_finish" in data
        assert "distance" in data["start_finish"]

        # Verify pit lane
        assert "pit_lane" in data
        assert "has_data" in data["pit_lane"]

def test_circuit_bounding_boxes_are_valid_and_not_collapsed():
    """
    Ensure no circuit collapses into a point or 0-width/0-height polygon.
    """
    for circuit_id in ALL_13_CIRCUITS:
        resp = client.get(f"/circuits/{circuit_id}/map")
        assert resp.status_code == 200
        data = resp.json()
        points = data["points"]
        
        xs = [p.get("x_rot", p.get("x", 0)) for p in points]
        ys = [p.get("y_rot", p.get("y", 0)) for p in points]

        width = max(xs) - min(xs)
        height = max(ys) - min(ys)

        assert width > 100, f"Circuit {circuit_id} has invalid width: {width}"
        assert height > 100, f"Circuit {circuit_id} has invalid height: {height}"

def test_invalid_circuit_returns_404_no_fabrication():
    """
    Ensure non-existent circuits return 404 rather than fabricating geometry.
    """
    resp = client.get("/circuits/fake_circuit_123/map")
    assert resp.status_code == 404

def test_circuit_switching_isolation():
    """
    Verify switching from Monaco to Monza returns completely isolated geometry.
    """
    resp_monaco = client.get("/circuits/monaco/map")
    resp_monza = client.get("/circuits/monza/map")

    assert resp_monaco.status_code == 200
    assert resp_monza.status_code == 200

    monaco_data = resp_monaco.json()
    monza_data = resp_monza.json()

    assert monaco_data["circuit_id"] == "monaco"
    assert monza_data["circuit_id"] == "monza"
    assert monaco_data["length_m"] != monza_data["length_m"]
    assert monaco_data["corners_count"] != monza_data["corners_count"]
    assert monaco_data["points"][0] != monza_data["points"][0]
