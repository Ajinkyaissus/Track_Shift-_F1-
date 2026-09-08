import os
import json
from fastapi.testclient import TestClient
from api.main import app

def dump_offline():
    out_dir = "frontend/public/demo_offline"
    os.makedirs(out_dir, exist_ok=True)
    
    with TestClient(app) as client:
        # Circuits list
        circ_res = client.get("/circuits")
        if circ_res.status_code == 200:
            with open(f"{out_dir}/circuits.json", "w") as f:
                json.dump(circ_res.json(), f)
            circuits = circ_res.json()
            for c in circuits:
                cid = c.get("circuit_id") or c.get("track_id")
                # Detail
                cd_res = client.get(f"/circuits/{cid}")
                if cd_res.status_code == 200:
                    with open(f"{out_dir}/circuit_{cid}.json", "w") as f:
                        json.dump(cd_res.json(), f)
                # Map
                cm_res = client.get(f"/circuits/{cid}/map")
                if cm_res.status_code == 200:
                    with open(f"{out_dir}/circuit_{cid}_map.json", "w") as f:
                        json.dump(cm_res.json(), f)
                # Sessions
                cs_res = client.get(f"/circuits/{cid}/sessions")
                if cs_res.status_code == 200:
                    with open(f"{out_dir}/circuit_{cid}_sessions.json", "w") as f:
                        json.dump(cs_res.json(), f)
                    for sess in cs_res.json():
                        s_id = sess.get("session_id")
                        # Telemetry
                        tel_res = client.get(f"/circuits/{cid}/sessions/{s_id}/telemetry")
                        if tel_res.status_code == 200:
                            with open(f"{out_dir}/session_{s_id}_telemetry.json", "w") as f:
                                json.dump(tel_res.json(), f)
                        # Pit Stops
                        pit_res = client.get(f"/api/sessions/{s_id}/pit-stops")
                        if pit_res.status_code == 200:
                            with open(f"{out_dir}/session_{s_id}_pit_stops.json", "w") as f:
                                json.dump(pit_res.json(), f)

        # Legacy stints / races
        races_res = client.get("/races")
        if races_res.status_code == 200:
            with open(f"{out_dir}/races.json", "w") as f:
                json.dump(races_res.json(), f)
            
            races = races_res.json()
            for r in races:
                r_id = r["race_id"]
                stints_res = client.get(f"/sessions/{r_id}/stints")
                if stints_res.status_code == 200:
                    with open(f"{out_dir}/sessions_{r_id}_stints.json", "w") as f:
                        json.dump(stints_res.json(), f)
                
                    stints = stints_res.json()
                    for st in stints:
                        st_id = st["stint_id"]
                        
                        # Ledger
                        ledger_res = client.get(f"/stints/{st_id}/ledger")
                        if ledger_res.status_code == 200:
                            with open(f"{out_dir}/stints_{st_id}_ledger.json", "w") as f:
                                json.dump(ledger_res.json(), f)
                        
                        # Attribution
                        attr_res = client.get(f"/stints/{st_id}/attribution")
                        if attr_res.status_code == 200:
                            with open(f"{out_dir}/stints_{st_id}_attribution.json", "w") as f:
                                json.dump(attr_res.json(), f)

if __name__ == "__main__":
    dump_offline()
    print("Offline demo data dumped successfully.")
