import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_pit_stops_monza_all_drivers():
    """Verify Monza 2024 race returns all real drivers with pit stop analytics and correct structure."""
    response = client.get("/api/sessions/2024_monza_R/pit-stops")
    assert response.status_code == 200
    data = response.json()
    
    assert data["session_id"] == "2024_monza_R"
    assert data["circuit_id"] == "monza"
    assert "drivers" in data
    assert "all_pit_stops" in data
    assert "summary" in data
    assert "fastest_observed_pit_stops" in data
    
    # Monza 2024 had 20 drivers
    assert len(data["drivers"]) == 20
    assert data["summary"]["total_drivers"] == 20
    assert data["summary"]["drivers_with_pit_stops"] == 20
    assert data["summary"]["total_pit_stops"] >= 30  # 31 stops recorded
    
    # Check driver object schema
    for driver in data["drivers"]:
        assert "driver_id" in driver
        assert "driver_name" in driver
        assert "team" in driver
        assert "team_color" in driver
        assert "pit_stop_count" in driver
        assert "pit_stops" in driver
        assert "data_status" in driver
        assert driver["data_status"] in ["AVAILABLE", "INSUFFICIENT"]
        
        for stop in driver["pit_stops"]:
            assert "stop_number" in stop
            assert "lap_number" in stop
            assert "duration" in stop
            assert "pit_lane_duration" in stop
            assert "is_estimated" in stop
            assert "tyre_compound_in" in stop
            assert "tyre_compound_out" in stop
            assert "lap_time" in stop
            assert "position_in" in stop
            assert "position_out" in stop
            assert "position_change" in stop
            assert "timestamp" in stop
            assert "track_position" in stop
            assert "x" in stop["track_position"]
            assert "y" in stop["track_position"]

def test_pit_stops_monaco_zero_stops():
    """Verify Monaco 2024 race properly discovers zero-stop drivers and flags them as AVAILABLE."""
    response = client.get("/api/sessions/2024_monaco_R/pit-stops")
    assert response.status_code == 200
    data = response.json()
    
    assert data["circuit_id"] == "monaco"
    assert len(data["drivers"]) == 20
    
    zero_stop_drivers = [d for d in data["drivers"] if d["pit_stop_count"] == 0]
    assert len(zero_stop_drivers) > 0, "Monaco red flag led to drivers not making pit stops under green"
    
    for zd in zero_stop_drivers:
        assert zd["data_status"] == "AVAILABLE"
        assert len(zd["pit_stops"]) == 0
        assert zd["total_pit_duration"] == 0.0

def test_pit_stops_fastest_observed_ranking():
    """Verify fastest observed ranking is sorted in ascending order of duration."""
    response = client.get("/api/sessions/2024_monza_R/pit-stops")
    assert response.status_code == 200
    data = response.json()
    
    fastest = data["fastest_observed_pit_stops"]
    assert len(fastest) > 0
    
    for i in range(len(fastest) - 1):
        assert fastest[i]["duration"] <= fastest[i+1]["duration"]
        assert "rank" in fastest[i]
        assert fastest[i]["rank"] == i + 1

def test_telemetry_includes_pit_data():
    """Verify circuit session telemetry payload includes multi-driver pit stops and lap pit flags."""
    response = client.get("/circuits/monza/sessions/2024_monza_R/telemetry")
    assert response.status_code == 200
    data = response.json()
    
    assert "pit_stops" in data
    assert len(data["pit_stops"]["drivers"]) == 20
    
    # Check session laps list has is_in_pit boolean
    laps_list = data.get("laps", [])
    assert len(laps_list) > 0
    
    # Verify lap objects contain is_in_pit and pit_status
    sample_lap = laps_list[0]
    assert "is_in_pit" in sample_lap
    assert "pit_status" in sample_lap
    
    # Check leaderboards_by_lap also contains is_in_pit
    leaderboards = data.get("leaderboards_by_lap", {})
    assert len(leaderboards) > 0
    first_lb = next(iter(leaderboards.values()))
    assert len(first_lb) > 0
    for driver_entry in first_lb:
        assert "is_in_pit" in driver_entry
        assert "pit_status" in driver_entry


