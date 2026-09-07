import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "models_loaded" in data
    assert data["stints_available"] >= 6

def test_get_races(client):
    response = client.get("/races")
    assert response.status_code == 200
    races = response.json()
    assert len(races) >= 2
    race_ids = [r["race_id"] for r in races]
    assert "2024_monza" in race_ids
    assert "2024_bahrain" in race_ids

def test_get_stints_for_race(client):
    response = client.get("/stints")
    assert response.status_code == 200
    stints = response.json()
    assert len(stints) >= 6
    drivers = {s["driver_id"] for s in stints}
    assert "VER" in drivers
    assert "LEC" in drivers
    assert "HAM" in drivers

def test_get_ledger(client):
    stint_id = "2024_monza_R_VER_1"
    response = client.get(f"/stints/{stint_id}/ledger")
    assert response.status_code == 200
    data = response.json()
    assert data["stint_id"] == stint_id
    assert "series" in data
    assert len(data["series"]) > 0
    assert "total_debt_seconds" in data
    first_lap = data["series"][0]
    assert "lap_number" in first_lap
    assert "residual" in first_lap
    assert "cumulative_debt" in first_lap

def test_get_attribution(client):
    stint_id = "2024_monza_R_VER_1"
    response = client.get(f"/stints/{stint_id}/attribution")
    assert response.status_code == 200
    data = response.json()
    assert "attribution" in data
    assert len(data["attribution"]) >= 4
    assert data["algorithm"] in ["ridge_linear_attribution", "hybrid_tcn_ridge_attribution", "observational_sensitivity_decomposition"]
    for item in data["attribution"]:
        assert "feature" in item
        assert "coefficient" in item
        assert "share_pct" in item
        assert isinstance(item["coefficient"], (int, float))

def test_counterfactual_valid(client):
    stint_id = "2024_monza_R_VER_1"
    payload = {
        "feature": "braking_aggression",
        "delta_pct": -25.0
    }
    response = client.post(f"/stints/{stint_id}/counterfactual", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "recovered_laps" in data
    assert "ci_95" in data
    ci = data["ci_95"]
    assert ci[0] <= data["recovered_laps"] <= ci[1]
    assert abs(data["recovered_laps"]) < 7.5

def test_counterfactual_extreme_bounds_rejection(client):
    stint_id = "2024_monza_R_VER_1"
    
    # -500% should be rejected with 400
    res_extreme_neg = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -500.0})
    assert res_extreme_neg.status_code == 400
    assert "supported domain" in res_extreme_neg.json()["detail"]

    # +1000% should be rejected with 400
    res_extreme_pos = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": 1000.0})
    assert res_extreme_pos.status_code == 400
    assert "supported domain" in res_extreme_pos.json()["detail"]

def test_counterfactual_invalid_feature(client):
    stint_id = "2024_monza_R_VER_1"
    response = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "non_existent_feature", "delta_pct": -10.0})
    assert response.status_code == 400
    assert "Invalid feature" in response.json()["detail"]

def test_counterfactual_nonexistent_stint(client):
    response = client.post("/stints/invalid_stint_999/counterfactual", json={"feature": "braking_aggression", "delta_pct": -10.0})
    assert response.status_code == 404

def test_get_signatures(client):
    response = client.get("/signatures")
    assert response.status_code == 200
    sigs = response.json()
    assert len(sigs) >= 3
    driver_ids = [s["driver_id"] for s in sigs]
    assert "VER" in driver_ids
    assert "LEC" in driver_ids
    assert "HAM" in driver_ids

def test_signature_transfer(client):
    stint_id = "2024_monza_R_VER_1"
    response = client.post(f"/stints/{stint_id}/signature_transfer", json={"target_driver": "LEC"})
    assert response.status_code == 200
    data = response.json()
    assert data["source_driver"] == "VER"
    assert data["target_driver"] == "LEC"
    assert "recovered_laps" in data
    assert "ci_95" in data
    assert len(data["feature_deltas"]) > 0

def test_compare_stints(client):
    stint_a = "2024_monza_R_VER_1"
    stint_b = "2024_monza_R_LEC_1"
    response = client.get(f"/stints/compare?stint_a={stint_a}&stint_b={stint_b}")
    assert response.status_code == 200
    data = response.json()
    assert data["stint_a"]["driver_id"] == "VER"
    assert data["stint_b"]["driver_id"] == "LEC"
    assert "total_debt_seconds" in data
    assert "feature_comparisons" in data
    assert len(data["feature_comparisons"]) >= 4
