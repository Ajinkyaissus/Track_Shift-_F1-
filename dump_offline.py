import os
import json
from fastapi.testclient import TestClient
from api.main import app

def dump_offline():
    out_dir = "frontend/public/demo_offline"
    os.makedirs(out_dir, exist_ok=True)
    
    with TestClient(app) as client:
        races_res = client.get("/races")
        with open(f"{out_dir}/races.json", "w") as f:
            json.dump(races_res.json(), f)
            
        races = races_res.json()
        
        for r in races:
            r_id = r["race_id"]
            stints_res = client.get(f"/sessions/{r_id}/stints")
            with open(f"{out_dir}/sessions_{r_id}_stints.json", "w") as f:
                json.dump(stints_res.json(), f)
            
            stints = stints_res.json()
            for st in stints:
                st_id = st["stint_id"]
                
                # Ledger
                ledger_res = client.get(f"/stints/{st_id}/ledger")
                with open(f"{out_dir}/stints_{st_id}_ledger.json", "w") as f:
                    json.dump(ledger_res.json(), f)
                
                # Attribution
                attr_res = client.get(f"/stints/{st_id}/attribution")
                with open(f"{out_dir}/stints_{st_id}_attribution.json", "w") as f:
                    json.dump(attr_res.json(), f)

if __name__ == "__main__":
    dump_offline()
    print("Offline demo data dumped successfully.")
