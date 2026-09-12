import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

TARGET_CIRCUITS = [
    "bahrain", "jeddah", "albert_park", "suzuka", "monaco",
    "silverstone", "hungaroring", "spa", "monza", "singapore",
    "cota", "interlagos", "abu_dhabi"
]

EXPECTED_COUNTRY_MAPPINGS = {
    "monza": {"country": "Italy", "country_code": "IT"},
    "spa": {"country": "Belgium", "country_code": "BE"},
    "silverstone": {"country": "Great Britain", "country_code": "GB"},
    "monaco": {"country": "Monaco", "country_code": "MC"},
    "hungaroring": {"country": "Hungary", "country_code": "HU"},
    "bahrain": {"country": "Bahrain", "country_code": "BH"},
    "jeddah": {"country": "Saudi Arabia", "country_code": "SA"},
    "abu_dhabi": {"country": "United Arab Emirates", "country_code": "AE"},
    "cota": {"country": "United States", "country_code": "US"},
    "interlagos": {"country": "Brazil", "country_code": "BR"},
    "suzuka": {"country": "Japan", "country_code": "JP"},
    "singapore": {"country": "Singapore", "country_code": "SG"},
    "albert_park": {"country": "Australia", "country_code": "AU"},
}

def test_circuits_geographic_coordinates_and_countries():
    res = client.get("/circuits")
    assert res.status_code == 200
    circuits = res.json()
    assert len(circuits) >= 13

    for c in circuits:
        cid = c["track_id"]
        assert "lat" in c
        assert "lon" in c
        assert isinstance(c["lat"], (int, float))
        assert isinstance(c["lon"], (int, float))
        assert -90 <= c["lat"] <= 90
        assert -180 <= c["lon"] <= 180

        # Country mapping verification
        if cid in EXPECTED_COUNTRY_MAPPINGS:
            expected = EXPECTED_COUNTRY_MAPPINGS[cid]
            assert c["country_code"] == expected["country_code"]
        assert "country" in c
        assert "country_code" in c

def test_circuit_detail_coordinates():
    res = client.get("/circuits/monza")
    assert res.status_code == 200
    data = res.json()
    assert data["track_id"] == "monza"
    assert round(data["lat"], 2) == 45.62
    assert round(data["lon"], 2) == 9.28
    assert data["country_code"] == "IT"
    assert data["country"] == "Italy"

def test_session_telemetry_abu_dhabi():
    res = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert data["circuit_id"] == "abu_dhabi"
    assert data["session_id"] == "2024_abu_dhabi_R"
    assert data["country_code"] == "AE"
    assert data["total_laps"] >= 20
    assert len(data["drivers"]) >= 2
    assert len(data["laps"]) >= 80
    assert "1" in data["leaderboards_by_lap"]
    assert "20" in data["leaderboards_by_lap"]
    
    # Leaderboard ordering check
    lb_lap1 = data["leaderboards_by_lap"]["1"]
    assert lb_lap1[0]["position"] == 1
    assert lb_lap1[0]["gap_to_leader"] == 0.0

def test_session_telemetry_monza():
    res = client.get("/circuits/monza/sessions/2024_monza_R/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert data["circuit_id"] == "monza"
    assert data["session_id"] == "2024_monza_R"
    assert data["country_code"] == "IT"
    assert data["country"] == "Italy"
    assert data["total_laps"] >= 14
    assert len(data["laps"]) >= 56

def test_circuit_state_isolation_monza_to_suzuka():
    """
    Critical Test:
    1. Select Italy -> Monza. Verify only Monza data loads.
    2. Switch to Japan -> Suzuka. Verify Monza data is purged and Suzuka geometry,
       sessions, drivers, telemetry, country codes, and TrackShift calculations load.
    """
    # Step 1: Monza (Italy 🇮🇹)
    res_mz_map = client.get("/circuits/monza/map")
    assert res_mz_map.status_code == 200
    assert res_mz_map.json()["track_id"] == "monza"

    res_mz_tel = client.get("/circuits/monza/sessions/2024_monza_R/telemetry")
    assert res_mz_tel.status_code == 200
    data_mz = res_mz_tel.json()
    assert data_mz["circuit_id"] == "monza"
    assert data_mz["country_code"] == "IT"
    assert "Italian" in data_mz["event_name"]
    assert data_mz["total_laps"] > 0

    # Step 2: Suzuka (Japan 🇯🇵)
    res_sz_map = client.get("/circuits/suzuka/map")
    assert res_sz_map.status_code == 200
    assert res_sz_map.json()["track_id"] == "suzuka"
    assert res_sz_map.json()["track_id"] != res_mz_map.json()["track_id"]

    res_sz_tel = client.get("/circuits/suzuka/sessions/2024_suzuka_R/telemetry")
    assert res_sz_tel.status_code == 200
    data_sz = res_sz_tel.json()
    assert data_sz["circuit_id"] == "suzuka"
    assert data_sz["country_code"] == "JP"
    assert data_sz["country_code"] != data_mz["country_code"]
    assert "Japanese" in data_sz["event_name"]
    assert data_sz["total_laps"] > 0

    # Verify TrackShift calculations for Suzuka stint
    valid_driver = next((d for d in data_sz["drivers"] if d.get("tyre_analysis_available")), data_sz["drivers"][0])
    stint_id = valid_driver["stint_id"]
    assert "suzuka" in stint_id
    res_attr = client.get(f"/stints/{stint_id}/attribution")
    assert res_attr.status_code == 200
    attr_data = res_attr.json()
    assert attr_data["stint_id"] == stint_id
    assert len(attr_data["attribution"]) == 5

def test_session_leaderboard_endpoint():
    res = client.get("/circuits/monza/sessions/2024_monza_R/leaderboard?lap=5")
    assert res.status_code == 200
    data = res.json()
    assert data["circuit_id"] == "monza"
    assert data["lap"] == 5
    assert len(data["leaderboard"]) >= 2
    assert data["leaderboard"][0]["position"] == 1

def test_invalid_circuit_and_session_error_handling():
    res = client.get("/circuits/invalid_circuit_404/sessions/2024_invalid_R/telemetry")
    assert res.status_code == 404

    res2 = client.get("/circuits/monza/sessions/nonexistent_session_999/telemetry")
    assert res2.status_code == 404

def test_all_13_circuits_have_sessions_and_telemetry():
    circuits_res = client.get("/circuits")
    assert circuits_res.status_code == 200
    circuits = circuits_res.json()
    assert len(circuits) >= 13

    for c in circuits:
        cid = c["track_id"]
        # Map geometry
        map_res = client.get(f"/circuits/{cid}/map")
        assert map_res.status_code == 200
        assert len(map_res.json()["points"]) > 50

        # Sessions
        sess_res = client.get(f"/circuits/{cid}/sessions")
        assert sess_res.status_code == 200
        sessions = sess_res.json()
        assert len(sessions) >= 1
        sid = sessions[0]["session_id"]
        
        # Telemetry
        tel_res = client.get(f"/circuits/{cid}/sessions/{sid}/telemetry")
        assert tel_res.status_code == 200
        tdata = tel_res.json()
        assert tdata["circuit_id"] == cid
        assert tdata["session_id"] == sid
        assert tdata["total_laps"] > 0
        assert tdata["country_code"] == c["country_code"]
        assert "weather" in tdata
        assert "air_temp" in tdata["weather"]
        assert "track_temp" in tdata["weather"]
        assert "humidity" in tdata["weather"]
        assert "wind_speed" in tdata["weather"]


def test_circuits_have_distinct_weather_conditions():
    """Verify distinct circuit climates (Singapore tropical humidity vs Abu Dhabi desert vs Spa cool forest)."""
    res_ad = client.get("/circuits/abu_dhabi/sessions/2024_abu_dhabi_R/telemetry")
    res_sg = client.get("/circuits/singapore/sessions/2024_singapore_R/telemetry")
    res_spa = client.get("/circuits/spa/sessions/2024_spa_R/telemetry")
    res_sil = client.get("/circuits/silverstone/sessions/2024_silverstone_R/telemetry")
    res_hun = client.get("/circuits/hungaroring/sessions/2024_hungaroring_R/telemetry")

    w_ad = res_ad.json()["weather"]
    w_sg = res_sg.json()["weather"]
    w_spa = res_spa.json()["weather"]
    w_sil = res_sil.json()["weather"]
    w_hun = res_hun.json()["weather"]

    # Singapore has higher tropical humidity than Abu Dhabi desert
    assert w_sg["humidity"] > w_ad["humidity"]
    # Spa in the Ardennes is cooler than Hungaroring summer heat
    assert w_spa["air_temp"] < w_hun["air_temp"]
    assert w_hun["track_temp"] > w_spa["track_temp"]
    # Silverstone is windier than Singapore
    assert w_sil["wind_speed"] > w_sg["wind_speed"]

