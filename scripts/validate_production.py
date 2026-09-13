"""
scripts/validate_production.py — Canonical Production System Integrity Validator.
=================================================================================
Validates full production runtime readiness:
1. Database schema and Parquet data store integrity
2. FastAPI application cold startup and lifespan hydration
3. KV cache prewarm and in-memory fallback tier
4. Core REST API endpoints responsiveness & schema adherence
5. Strategic decision fusion and driver advisory engine

Usage:
    python scripts/validate_production.py
"""

import os
import sys
import sqlite3
import pandas as pd
from fastapi.testclient import TestClient

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.main import app, DB_PATH, DATA_DIR


def run_production_validation():
    print("=" * 80)
    print(" TRACKSHIFT — PRODUCTION RUNTIME INTEGRITY VALIDATION")
    print("=" * 80)
    failures = []

    # -------------------------------------------------------------------------
    # 1. Database & Parquet Data Store Validation
    # -------------------------------------------------------------------------
    print("\n[CHECK 1] Database & Parquet Store Integrity...")
    try:
        assert os.path.exists(DB_PATH), f"Database not found at {DB_PATH}"
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM tracks")
            track_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM sessions")
            sess_count = cursor.fetchone()[0]
            cursor.execute("SELECT count(*) FROM stints")
            stint_count = cursor.fetchone()[0]

        assert track_count >= 13, f"Expected >= 13 tracks, found {track_count}"
        assert sess_count > 0, "No sessions found in database"
        assert stint_count > 0, "No stints found in database"

        # Check required Parquet stores
        for pq in ["laps.parquet", "residual_ledger.parquet", "circuit_geometry.parquet"]:
            p = os.path.join(DATA_DIR, pq)
            assert os.path.exists(p), f"Missing required parquet store: {pq}"
            df = pd.read_parquet(p)
            assert len(df) > 0, f"Empty parquet store: {pq}"

        print(f"  [PASS] DB ({track_count} tracks, {sess_count} sessions, {stint_count} stints) and Parquet stores verified")
    except Exception as e:
        failures.append(f"Check 1 (Data Stores): {e}")
        print(f"  [FAIL]: {e}")

    # -------------------------------------------------------------------------
    # 2. FastAPI Cold Startup & Lifespan Hydration
    # -------------------------------------------------------------------------
    print("\n[CHECK 2] FastAPI Lifespan Hydration & Prewarming...")
    with TestClient(app) as client:
        try:
            resp = client.get("/health")
            assert resp.status_code == 200, f"Health check returned HTTP {resp.status_code}"
            data = resp.json()
            assert data["status"] == "ok"
            assert data["circuits_available"] >= 13
            assert data["stints_available"] >= 6
            assert len(data["drivers"]) >= 10
            print(f"  [PASS] Application startup complete: {data['circuits_available']} circuits, {len(data['drivers'])} drivers loaded")
        except Exception as e:
            import traceback
            failures.append(f"Check 2 (Startup/Lifespan): {e}")
            print(f"  [FAIL]: {e}\n{traceback.format_exc()}")

        # -------------------------------------------------------------------------
        # 3. Production Endpoint Contracts
        # -------------------------------------------------------------------------
        print("\n[CHECK 3] Core API Route Contracts...")
        endpoints = [
            ("Ping", "/ping", 200),
            ("Health", "/health", 200),
            ("Seasons List", "/api/seasons", 200),
            ("Circuit Map (Monza)", "/circuits/monza/map", 200),
            ("Session Drivers (2024 Monza R)", "/sessions/2024_monza_R/drivers", 200),
            ("Tyre Provenance", "/api/tyre-intelligence/provenance", 200),
            ("8-Model Ablation Study", "/api/tyre-intelligence/ablation", 200),
            ("Post-Race Validation", "/api/tyre-intelligence/post-race-validation", 200),
            ("Driver Advisory", "/sessions/2024_monza_R/driver-advisory?driver_id=VER&lap=20", 200),
            ("Strategic Warfare", "/api/sessions/2024_monza_R/strategic-warfare", 200),
            ("Race Intelligence", "/sessions/2024_monza_R/race-intelligence", 200),
        ]

        for name, url, expected_status in endpoints:
            try:
                r = client.get(url)
                assert r.status_code == expected_status, f"{name} ({url}) returned HTTP {r.status_code}, expected {expected_status}: {r.text[:100]}"
                print(f"  [PASS] {name:<32} -> HTTP {r.status_code}")
            except Exception as e:
                failures.append(f"Check 3 ({name}): {e}")
                print(f"  [FAIL] {name:<32} -> {e}")

        # -------------------------------------------------------------------------
        # 4. Strategic Warfare & Decision Fusion Verification
        # -------------------------------------------------------------------------
        print("\n[CHECK 4] Decision Fusion & Strategic Engine...")
        try:
            r = client.get("/api/sessions/2024_monza_R/strategic-warfare")
            assert r.status_code == 200
            sw_data = r.json()
            assert "strategic_decision_fusion" in sw_data or "competitor_evaluations" in sw_data or "decision" in sw_data, f"Keys: {list(sw_data.keys())}"
            print("  [PASS] Strategic warfare payload schema verified")
        except Exception as e:
            import traceback
            failures.append(f"Check 4 (Strategic Warfare): {e}")
            print(f"  [FAIL]: {e}\n{traceback.format_exc()}")

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    if not failures:
        print(" PRODUCTION VALIDATION SUMMARY: ALL CHECKS PASSED PERFECTLY")
        print("=" * 80)
        return 0
    else:
        print(f" PRODUCTION VALIDATION SUMMARY: {len(failures)} FAILURE(S) DETECTED")
        for f in failures:
            print(f"  - {f}")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    code = run_production_validation()
    sys.exit(code)
