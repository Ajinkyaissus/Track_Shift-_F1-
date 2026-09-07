from fastapi.testclient import TestClient
import sys
import os
import time
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from api.main import app

def test_counterfactual_flow():
    with TestClient(app) as client:
        # 1. Test GET /races
        res = client.get("/races")
        assert res.status_code == 200
        races = res.json()
        assert len(races) > 0, "No races found! Ensure database is seeded."
        race_id = races[0]['race_id']
        
        # 2. Test GET /sessions/{id}/stints
        res = client.get(f"/sessions/{race_id}/stints")
        assert res.status_code == 200
        stints = res.json()
        assert len(stints) > 0, "No stints found for race!"
        stint_id = stints[0]['stint_id']
            
        # 3. Test GET /stints/{id}/ledger
        res = client.get(f"/stints/{stint_id}/ledger")
        assert res.status_code == 200
        ledger = res.json()
        assert len(ledger['series']) > 0
        
        # 4. Test GET /stints/{id}/attribution
        res = client.get(f"/stints/{stint_id}/attribution")
        assert res.status_code == 200
        attr = res.json()
        assert len(attr['attribution']) > 0
            
        # 5. Physics check: -50% braking aggression must NOT produce 122.55 laps (unphysical)
        # Should be smoothly saturated <= 7.5 laps max for a 20-lap stint
        res = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -50.0})
        assert res.status_code == 200
        body = res.json()
        recovered = body["recovered_laps"]
        assert abs(recovered) <= 7.5, f"Expected bounded recovered laps in [-7.5, 7.5], got {recovered}"
        assert body["is_saturated"] is True, "Expected is_saturated to be True for extreme -50% delta"
        assert "ci_95" in body
        ci = body["ci_95"]
        assert ci[0] <= recovered <= ci[1], f"Expected CI [lower, upper] to bracket {recovered}, got {ci}"
        
        # 6. Normal counterfactuals (-10%, +10%)
        res = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -10.0})
        assert res.status_code == 200
        res_normal = res.json()
        assert abs(res_normal["recovered_laps"]) <= 7.5
        assert res_normal["ci_95"][0] <= res_normal["recovered_laps"] <= res_normal["ci_95"][1]

        # 7. Boundary counterfactuals (-100%, +100%)
        res_neg100 = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -100.0})
        assert res_neg100.status_code == 200
        assert abs(res_neg100.json()["recovered_laps"]) <= 7.5

        res_pos100 = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": 100.0})
        assert res_pos100.status_code == 200
        assert abs(res_pos100.json()["recovered_laps"]) <= 7.5

        # 8. Test Driver Signatures & Signature Transfer
        res_sigs = client.get("/signatures")
        assert res_sigs.status_code == 200
        sigs = res_sigs.json()
        assert len(sigs) >= 2, "Expected at least 2 driver signatures"
        
        target_driver = [s['driver_id'] for s in sigs if s['driver_id'] != stints[0]['driver_id']][0]
        res_transfer = client.post(f"/stints/{stint_id}/signature_transfer", json={"target_driver_id": target_driver})
        assert res_transfer.status_code == 200
        transfer_body = res_transfer.json()
        assert "net_recovered_laps" in transfer_body
        assert "ci_95" in transfer_body
        assert abs(transfer_body["net_recovered_laps"]) <= 7.5

        # 9. Test Driver Stint Comparison
        if len(stints) >= 2:
            stint_b = stints[1]['stint_id']
            res_comp = client.get(f"/stints/compare?stint_a={stint_id}&stint_b={stint_b}")
            assert res_comp.status_code == 200
            comp_body = res_comp.json()
            assert "total_debt_seconds" in comp_body
            assert "feature_comparisons" in comp_body

        # 8. Out-of-domain counterfactuals (> 100% or < -100%) -> should return HTTP 400 with helpful message
        res_extreme_neg = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -500.0})
        assert res_extreme_neg.status_code == 400
        assert "exceeds supported domain" in res_extreme_neg.json()["detail"].lower()

        res_extreme_pos = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": 1000.0})
        assert res_extreme_pos.status_code == 400

        # 9. Invalid feature name -> should return HTTP 400
        res_invalid_feature = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "flux_capacitor", "delta_pct": -10.0})
        assert res_invalid_feature.status_code == 400

        # 10. Invalid stint ID -> should return HTTP 404
        res_invalid_stint = client.post("/stints/non_existent_stint_999/counterfactual", json={"feature": "braking_aggression", "delta_pct": -10.0})
        assert res_invalid_stint.status_code == 404

        # 11. Empty body / missing fields -> should return HTTP 422
        res_empty = client.post(f"/stints/{stint_id}/counterfactual", json={})
        assert res_empty.status_code == 422

        # 12. Measure latency for N=200 calls
        latencies = []
        for _ in range(200):
            t0 = time.perf_counter()
            res = client.post(f"/stints/{stint_id}/counterfactual", json={"feature": "braking_aggression", "delta_pct": -10.0})
            t1 = time.perf_counter()
            assert res.status_code == 200
            latencies.append((t1 - t0) * 1000)
            
        p95 = np.percentile(latencies, 95)
        print(f"TestClient p95 latency: {p95:.3f} ms (N=200)")

if __name__ == "__main__":
    test_counterfactual_flow()
