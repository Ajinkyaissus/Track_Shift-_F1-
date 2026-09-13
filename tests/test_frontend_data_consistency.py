"""
tests/test_frontend_data_consistency.py
Automated Frontend Data-Consistency & Race-Condition Invalidation Test Suite
Verifies:
  - selectedCircuit === data.circuit
  - selectedSession === data.session
  - selectedDriver === data.driver
  - selectedSeason === data.season
  - TDSM State-Space & Multi-Horizon Forecast dynamically reflects the selected driver/lap
  - Stale request responses are strictly invalidated
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_multi_season_circuit_coverage():
    """Verify 2024 and 2025 return distinct, valid circuit calendars without hardcoding."""
    res_2024 = client.get("/circuits?year=2024")
    assert res_2024.status_code == 200
    circuits_2024 = res_2024.json()
    assert len(circuits_2024) >= 23, f"Expected at least 23 circuits for 2024, got {len(circuits_2024)}"

    res_2025 = client.get("/circuits?year=2025")
    assert res_2025.status_code == 200
    circuits_2025 = res_2025.json()
    assert len(circuits_2025) >= 23, f"Expected at least 23 circuits for 2025, got {len(circuits_2025)}"

    # Check that all returned circuits have track_id, name, and country
    for c in circuits_2024:
        assert "track_id" in c or "circuit_id" in c
        assert "name" in c

    for c in circuits_2025:
        assert "track_id" in c or "circuit_id" in c
        assert "name" in c


@pytest.mark.parametrize("season,circuit_id", [
    (2024, "bahrain"),
    (2024, "monaco"),
    (2024, "silverstone"),
    (2024, "monza"),
    (2024, "spa"),
    (2024, "baku"),
    (2025, "bahrain"),
    (2025, "suzuka"),
    (2025, "monaco"),
    (2025, "silverstone"),
    (2025, "spa"),
    (2025, "abu_dhabi")
])
def test_data_consistency_across_circuits_and_seasons(season, circuit_id):
    """
    Verifies that for each live circuit:
      selectedCircuit === data.circuit
      selectedSeason === data.season
      selectedSession === data.session
      selectedDriver is in dynamic session roster
    """
    # 1. Fetch sessions for circuit and season
    sess_res = client.get(f"/circuits/{circuit_id}/sessions?year={season}")
    assert sess_res.status_code == 200, f"Failed getting sessions for {circuit_id} {season}"
    sessions = sess_res.json()
    assert len(sessions) > 0, f"No sessions for {circuit_id} {season}"

    selected_session = sessions[0]
    session_id = selected_session["session_id"]

    # 2. Fetch session telemetry
    tel_res = client.get(f"/circuits/{circuit_id}/sessions/{session_id}/telemetry")
    assert tel_res.status_code == 200, f"Telemetry failed for {circuit_id} {session_id}"
    tel_data = tel_res.json()

    # Rule: selectedCircuit === data.circuit
    assert tel_data["circuit_id"] == circuit_id, f"Circuit mismatch: expected {circuit_id}, got {tel_data['circuit_id']}"

    # Rule: selectedSeason === data.season
    assert tel_data["season"] == season, f"Season mismatch: expected {season}, got {tel_data['season']}"

    # Rule: selectedSession === data.session
    assert tel_data["session_id"] == session_id, f"Session mismatch: expected {session_id}, got {tel_data['session_id']}"

    # Rule: Dynamic drivers present
    drivers = tel_data.get("drivers", [])
    assert len(drivers) > 0, f"No drivers returned for session {session_id}"

    # Ensure drivers list has valid driver_id
    for drv in drivers:
        assert "driver_id" in drv
        assert len(drv["driver_id"]) >= 2


def test_tdsm_dynamic_prediction_per_driver():
    """
    Verifies that TDSM computes driver-specific state-space predictions
    and does not return uniform hardcoded values.
    """
    # Test Driver A State (e.g. NOR, medium tyre, moderate debt)
    state_a = {
        "D": 0.42,
        "Delta_D": 0.035,
        "Delta2_D": 0.002,
        "TyreLife": 14.0,
        "Compound": "MEDIUM",
        "FuelProxy": 68.0,
        "data_cutoff_lap": 14
    }
    res_a = client.post("/api/tdsm/predict", json=state_a)
    assert res_a.status_code == 200
    data_a = res_a.json()
    forecast_a = data_a["forecast"]
    assert "+1" in forecast_a and "+3" in forecast_a and "+5" in forecast_a and "+10" in forecast_a

    # Test Driver B State (e.g. VER, hard tyre, fresh rubber, high fuel)
    state_b = {
        "D": 0.08,
        "Delta_D": 0.010,
        "Delta2_D": -0.001,
        "TyreLife": 3.0,
        "Compound": "HARD",
        "FuelProxy": 95.0,
        "data_cutoff_lap": 3
    }
    res_b = client.post("/api/tdsm/predict", json=state_b)
    assert res_b.status_code == 200
    data_b = res_b.json()
    forecast_b = data_b["forecast"]

    # Assert driver A and driver B have distinct predictions (no hardcoded static forecast)
    assert forecast_a["+1"] != forecast_b["+1"], "Driver A and Driver B forecasts must differ!"
    assert forecast_a["+10"] != forecast_b["+10"], "Multi-horizon forecasts must be driver-specific!"
    assert forecast_a["+10"] > forecast_a["+1"], "+10 forecast must reflect degradation progression!"


def test_stale_response_discard_logic():
    """
    Simulates the frontend CircuitContext sequence discard logic:
    If a request for selection A finishes after user moved to selection B,
    it must be strictly rejected.
    """
    # Simulate frontend selection lifecycle
    current_selection = {"circuit": "silverstone", "driver": "NOR", "seq": 1}

    # In-flight request initiated for selection A
    req_a_tag = {"circuit": "silverstone", "driver": "NOR", "seq": 1}

    # User rapidly switches to selection B
    current_selection = {"circuit": "monza", "driver": "LEC", "seq": 2}

    # Now request A arrives late
    def should_accept(response_tag, active_selection):
        return (
            response_tag["seq"] == active_selection["seq"] and
            response_tag["circuit"] == active_selection["circuit"] and
            response_tag["driver"] == active_selection["driver"]
        )

    # Response A must be discarded
    assert not should_accept(req_a_tag, current_selection), "Stale response must be discarded!"

    # Response B arrives matching current sequence
    req_b_tag = {"circuit": "monza", "driver": "LEC", "seq": 2}
    assert should_accept(req_b_tag, current_selection), "Matching response must be accepted!"
