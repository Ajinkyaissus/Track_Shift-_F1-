import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

TARGET_CIRCUITS = [
    "bahrain", "jeddah", "albert_park", "suzuka", "monaco",
    "silverstone", "hungaroring", "spa", "monza", "singapore",
    "cota", "interlagos", "abu_dhabi"
]

def test_get_circuits_list():
    response = client.get("/circuits")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 13
    
    circuit_ids = [c["track_id"] for c in data]
    for cid in TARGET_CIRCUITS:
        assert cid in circuit_ids
        
    for c in data:
        assert "name" in c
        assert "country_code" in c
        assert "location" in c
        assert c["map_available"] is True
        assert c["telemetry_available"] is True

def test_get_circuit_detail_valid():
    response = client.get("/circuits/monza")
    assert response.status_code == 200
    data = response.json()
    assert data["track_id"] == "monza"
    assert "Monza" in data["name"]
    assert data["country_code"] in ["IT", "ITA"]
    assert data["map_available"] is True
    assert data["telemetry_available"] is True
    assert data["corners_count"] > 0
    assert data["total_laps_recorded"] > 0
    assert data["total_stints_recorded"] > 0

def test_get_circuit_detail_invalid():
    response = client.get("/circuits/invalid_circuit_99")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

def test_get_circuit_map():
    response = client.get("/circuits/spa/map")
    assert response.status_code == 200
    data = response.json()
    assert data["track_id"] == "spa"
    assert "points" in data
    assert len(data["points"]) > 100
    assert "x" in data["points"][0]
    assert "y" in data["points"][0]
    assert "distance" in data["points"][0]
    assert "corners" in data
    assert "corner_number" in data["corners"][0] or "number" in data["corners"][0]
    assert "x" in data["corners"][0]
    assert "y" in data["corners"][0]

def test_get_circuit_map_invalid():
    response = client.get("/circuits/unknown_gp/map")
    assert response.status_code == 404

def test_get_circuit_sessions():
    response = client.get("/circuits/silverstone/sessions")
    assert response.status_code == 200
    data = response.json()
    assert any(s["year"] == 2024 for s in data)

def test_get_circuit_stints():
    response = client.get("/circuits/bahrain/stints")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "driver" in data[0]
    assert "compound" in data[0]
    assert "lap_count" in data[0]
