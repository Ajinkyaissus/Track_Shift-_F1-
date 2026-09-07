import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_session_drivers_abu_dhabi_twenty_drivers():
    """
    Test Abu Dhabi Grand Prix Race returns all 20 drivers from FastF1 session data.
    Verifies no hardcoded 4-driver limit.
    """
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers")
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == "2024_abu_dhabi_R"
    assert data["circuit_id"] == "abu_dhabi"
    assert data["driver_count"] == 20
    assert len(data["drivers"]) == 20

    # Ensure authentic drivers are present across teams
    driver_ids = [d["driver_id"] for d in data["drivers"]]
    for expected_drv in ["VER", "NOR", "LEC", "HAM", "RUS", "SAI", "PIA", "PER", "ALO", "STR", "TSU", "GAS", "DOO", "ALB", "BOT", "ZHO", "MAG", "HUL", "COL"]:
        assert expected_drv in driver_ids

    # Check driver metadata structure
    nor = next(d for d in data["drivers"] if d["driver_id"] == "NOR")
    assert nor["driver_number"] == 4
    assert nor["full_name"] == "Lando NORRIS"
    assert nor["team"] == "McLaren"
    assert nor["country_code"] == "GBR"
    assert nor["telemetry_available"] is True
    assert nor["stint_data_available"] is True

def test_session_drivers_albert_park_nineteen_drivers():
    """
    Test Australian Grand Prix Race returns exactly 19 drivers (authentic FastF1 roster after Sargeant withdrawal).
    Ensures frontend and backend dynamically accept non-20 driver counts.
    """
    res = client.get("/circuits/albert_park/sessions/2024_albert_park_R/drivers")
    assert res.status_code == 200
    data = res.json()
    assert data["session_id"] == "2024_albert_park_R"
    assert data["driver_count"] == 19
    assert len(data["drivers"]) == 19

def test_global_session_drivers_endpoint():
    """
    Test GET /sessions/{session_id}/drivers and GET /api/sessions/{session_id}/drivers.
    """
    res1 = client.get("/sessions/2024_monza_R/drivers")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["driver_count"] == 20
    assert len(data1["drivers"]) == 20

    res2 = client.get("/api/sessions/2024_monza_R/drivers")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["driver_count"] == 20

def test_session_telemetry_contains_all_drivers_and_leaderboards():
    """
    Test GET /circuits/{circuit_id}/sessions/{session_id}/telemetry returns all 20 drivers
    and that all 20 drivers appear in the leaderboards_by_lap.
    """
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert data["driver_count"] == 20
    assert len(data["drivers"]) == 20

    # Leaderboard on lap 1 must contain all 20 drivers
    lb_lap1 = data["leaderboards_by_lap"]["1"]
    assert len(lb_lap1) == 20

    # Positions must be 1 to 20
    positions = [row["position"] for row in lb_lap1]
    assert positions == list(range(1, 21))

    # Real telemetry drivers have telemetry_available True, others have honest False
    telemetry_drivers = [row for row in lb_lap1 if row["telemetry_available"]]
    non_telemetry_drivers = [row for row in lb_lap1 if not row["telemetry_available"]]
    assert len(telemetry_drivers) >= 2
    assert len(non_telemetry_drivers) > 0
    assert non_telemetry_drivers[0]["status"] == "Insufficient telemetry for this analysis"

def test_driver_data_availability_diagnostic():
    """
    Diagnostic test reporting:
    - Drivers count
    - Drivers with lap data
    - Drivers with telemetry
    - Drivers with stint data
    - Drivers with tyre analysis
    """
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers")
    assert res.status_code == 200
    drivers = res.json()["drivers"]

    total_drivers = len(drivers)
    lap_drivers = sum(1 for d in drivers if d["lap_data_available"])
    tel_drivers = sum(1 for d in drivers if d["telemetry_available"])
    stint_drivers = sum(1 for d in drivers if d["stint_data_available"])
    tyre_analysis_drivers = sum(1 for d in drivers if d["tyre_analysis_available"])

    assert total_drivers == 20
    assert tel_drivers >= 2
    assert lap_drivers >= 2
    assert stint_drivers >= 2
    assert tyre_analysis_drivers >= 2

def test_session_switch_driver_isolation():
    """
    Test switching sessions:
    1. Abu Dhabi returns Abu Dhabi drivers
    2. Albert Park returns 19 drivers (without stale Abu Dhabi drivers)
    """
    res_ad = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/drivers")
    assert res_ad.status_code == 200
    assert res_ad.json()["driver_count"] == 20

    res_ap = client.get("/circuits/albert_park/sessions/2024_albert_park_R/drivers")
    assert res_ap.status_code == 200
    assert res_ap.json()["driver_count"] == 19
    assert res_ap.json()["session_id"] == "2024_albert_park_R"
