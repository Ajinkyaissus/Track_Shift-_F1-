"""
Tests for API Cache Serving, Observability Metrics, Invalidation Endpoints, and Concurrency.
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_metrics_endpoint(client):
    res = client.get("/metrics")
    assert res.status_code == 200
    data = res.json()
    assert "cache_hits_total" in data
    assert "cache_misses_total" in data
    assert "cache_hit_rate" in data
    assert "tier" in data


def test_api_map_caching_and_latency(client):
    # First request: cold or cached
    res1 = client.get("/circuits/monza/map")
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["track_id"] == "monza"
    assert len(data1["points"]) > 0

    # Second request: warm cache hit
    res2 = client.get("/circuits/monza/map")
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["track_id"] == "monza"
    assert len(data2["points"]) == len(data1["points"])


def test_stint_attribution_hybrid_dl(client):
    stint_id = "2024_monza_R_VER_1"
    res = client.get(f"/stints/{stint_id}/attribution")
    assert res.status_code == 200
    data = res.json()
    assert data["stint_id"] == stint_id
    assert "behavioral_embedding_dim" in data
    assert data["behavioral_embedding_dim"] == 16
    assert len(data["attribution"]) >= 4


def test_cache_invalidation_endpoint(client):
    stint_id = "2024_monza_R_VER_1"
    # Ensure populated
    client.get(f"/stints/{stint_id}/attribution")
    
    # Invalidate
    res = client.post(f"/admin/cache/invalidate/stint/{stint_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["stint_id"] == stint_id
    assert "invalidated_keys_count" in data


def test_concurrent_api_requests(client):
    import concurrent.futures
    stint_id = "2024_monza_R_VER_1"
    payload = {"feature": "braking_aggression", "delta_pct": -15.0}

    def _call():
        return client.post(f"/stints/{stint_id}/counterfactual", json=payload)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_call) for _ in range(16)]
        results = [f.result() for f in futures]

    for r in results:
        assert r.status_code == 200
        data = r.json()
        assert data["recovered_laps"] > 0
        assert "ci_95" in data
