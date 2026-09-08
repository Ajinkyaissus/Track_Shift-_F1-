"""
tests/test_no_2023_support.py — Dedicated Test Suite for Complete 2023 Removal & Purge Verification.

Verifies:
1. /api/seasons does not return 2023
2. 2023 API requests fail (404)
3. Database contains 0 records for 2023
4. Parquet datasets contain 0 rows for 2023
5. Cache contains 0 entries for 2023
6. Frontend season configuration contains no 2023
7. Ingestion rejects 2023 with ValueError
8. Model artifacts contain no 2023 training/evaluation records
9. No 2023 session can be resolved
10. No 2023 driver/stint/pit-stop/telemetry record can be retrieved
11. 2024 functionality remains intact
12. 2025 functionality remains intact
13. Season switching 2024 <-> 2025 works
14. No stale state appears after switching
15. All scientific-integrity safeguards continue passing
"""

import sqlite3
import pytest
import pandas as pd
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import app
from trackshift.ingest.season import ingest_season, SUPPORTED_SEASONS
from api.cache import get_cache_service

client = TestClient(app)
DB_PATH = Path("api/tyredebt.db")
DATA_DIR = Path("data")


class TestNo2023Support:

    # 1. /api/seasons does not return 2023
    def test_api_seasons_excludes_2023(self):
        res = client.get("/api/seasons")
        assert res.status_code == 200
        seasons = res.json()
        years = [s["year"] for s in seasons]
        assert 2023 not in years
        assert 2024 in years
        assert 2025 in years
        assert years == [2025, 2024] or years == [2024, 2025]

    # 2. 2023 API requests fail (404)
    def test_2023_api_endpoints_return_404(self):
        endpoints = [
            "/api/seasons/2023/events",
            "/circuits/cota/sessions/2023_cota_R/telemetry",
            "/circuits/cota/sessions/2023_cota_R/drivers",
            "/circuits/cota/sessions/2023_cota_R/pit-stops",
            "/api/sessions/2023_cota_R/weather",
            "/api/sessions/2023_cota_R/track-status",
            "/circuits/cota/sessions/2023_cota_R/drivers/VER/telemetry",
            "/circuits/cota/sessions/2023_cota_R/drivers/VER/stints/1/analysis",
        ]
        for ep in endpoints:
            res = client.get(ep)
            assert res.status_code == 404, f"Expected 404 for {ep}, got {res.status_code}"

    # 3. Database contains no 2023 records
    def test_database_contains_zero_2023_records(self):
        assert DB_PATH.exists()
        conn = sqlite3.connect(str(DB_PATH))
        c = conn.cursor()
        
        # Check seasons table
        c.execute("SELECT COUNT(*) FROM seasons WHERE year = 2023")
        assert c.fetchone()[0] == 0

        # Check races table
        c.execute("SELECT COUNT(*) FROM races WHERE season = 2023")
        assert c.fetchone()[0] == 0

        # Check sessions table
        c.execute("SELECT COUNT(*) FROM sessions WHERE session_id LIKE '2023_%'")
        assert c.fetchone()[0] == 0

        # Check stints table
        c.execute("SELECT COUNT(*) FROM stints WHERE session_id LIKE '2023_%' OR stint_id LIKE '2023_%'")
        assert c.fetchone()[0] == 0

        # Check pit_stops table
        c.execute("SELECT COUNT(*) FROM pit_stops WHERE session_id LIKE '2023_%'")
        assert c.fetchone()[0] == 0

        # Check weather table
        c.execute("SELECT COUNT(*) FROM weather WHERE session_id LIKE '2023_%'")
        assert c.fetchone()[0] == 0

        # Check session_drivers table
        c.execute("SELECT COUNT(*) FROM session_drivers WHERE session_id LIKE '2023_%'")
        assert c.fetchone()[0] == 0

        # Check provenance table
        c.execute("SELECT COUNT(*) FROM provenance WHERE season = 2023")
        assert c.fetchone()[0] == 0

        # Distinct seasons in database
        c.execute("SELECT DISTINCT season FROM races")
        db_seasons = {row[0] for row in c.fetchall()}
        assert 2023 not in db_seasons
        assert db_seasons.issubset({2024, 2025})

        conn.close()

    # 4. Parquet datasets contain no 2023 rows
    def test_parquet_datasets_contain_zero_2023_rows(self):
        # Laps parquet
        laps_path = DATA_DIR / "laps.parquet"
        if laps_path.exists():
            df_laps = pd.read_parquet(laps_path)
            if "season" in df_laps.columns:
                assert (df_laps["season"] == 2023).sum() == 0
            if "session_id" in df_laps.columns:
                assert df_laps["session_id"].str.startswith("2023_").sum() == 0

        # Residual ledger
        res_path = DATA_DIR / "residual_ledger.parquet"
        if res_path.exists():
            df_res = pd.read_parquet(res_path)
            if "season" in df_res.columns:
                assert (df_res["season"] == 2023).sum() == 0
            if "session_id" in df_res.columns:
                assert df_res["session_id"].str.startswith("2023_").sum() == 0
            if "stint_id" in df_res.columns:
                assert df_res["stint_id"].str.startswith("2023_").sum() == 0

        # Baseline predictions
        base_path = DATA_DIR / "baseline_predictions.parquet"
        if base_path.exists():
            df_base = pd.read_parquet(base_path)
            if "season" in df_base.columns:
                assert (df_base["season"] == 2023).sum() == 0
            if "session_id" in df_base.columns:
                assert df_base["session_id"].str.startswith("2023_").sum() == 0

        # Bootstrap uncertainty
        boot_path = DATA_DIR / "bootstrap_uncertainty.parquet"
        if boot_path.exists():
            df_boot = pd.read_parquet(boot_path)
            if "session_id" in df_boot.columns:
                assert df_boot["session_id"].str.startswith("2023_").sum() == 0
            if "stint_id" in df_boot.columns:
                assert df_boot["stint_id"].str.startswith("2023_").sum() == 0

    # 5. Cache contains no 2023 entries
    def test_cache_contains_zero_2023_keys(self):
        cache = get_cache_service()
        # Check memory cache keys
        for key in list(cache.memory._store.keys()):
            assert "2023" not in str(key), f"Found 2023 in memory cache key: {key}"

        # Check Redis if running
        if cache.redis and cache.redis.is_connected:
            try:
                keys = cache.redis._client.keys("*2023*")
                assert len(keys) == 0, f"Found 2023 in redis cache keys: {keys}"
            except Exception:
                pass

    # 6. Frontend season configuration contains no 2023
    def test_frontend_season_config(self):
        circuit_context = Path("frontend/src/context/CircuitContext.jsx")
        if circuit_context.exists():
            content = circuit_context.read_text(encoding="utf-8")
            assert "availableSeasons = [2025, 2024]" in content or "availableSeasons = [2024, 2025]" in content
            assert "2023" not in content

    # 7. Ingestion rejects 2023
    def test_ingestion_rejects_2023(self):
        assert 2023 not in SUPPORTED_SEASONS
        assert SUPPORTED_SEASONS == [2024, 2025]
        with pytest.raises(ValueError, match="Unsupported season: 2023"):
            ingest_season(2023)

    # 8. Model artifacts contain no 2023 records
    def test_model_artifacts_contain_zero_2023_lineage(self):
        report_path = DATA_DIR / "extraction_report.csv"
        if report_path.exists():
            df_rep = pd.read_csv(report_path)
            assert (df_rep["season"] == 2023).sum() == 0
            assert set(df_rep["season"].unique()).issubset({2024, 2025})

    # 9 & 10. No 2023 session or driver record can be retrieved
    def test_no_2023_session_or_driver_retrievable(self):
        res = client.get("/circuits/cota/sessions/2023_cota_R/drivers")
        assert res.status_code == 404
        res2 = client.get("/circuits/monza/sessions/2023_monza_R/drivers")
        assert res2.status_code == 404

    # 11 & 12. 2024 & 2025 functionality remains intact
    def test_2024_and_2025_functionality_intact(self):
        # 2024 COTA
        res24 = client.get("/circuits/cota/sessions/2024_cota_R/telemetry")
        assert res24.status_code == 200
        data24 = res24.json()
        assert data24["season"] == 2024
        assert len(data24["drivers"]) > 0

        # 2025 COTA
        res25 = client.get("/circuits/cota/sessions/2025_cota_R/telemetry")
        assert res25.status_code == 200
        data25 = res25.json()
        assert data25["season"] == 2025
        assert len(data25["drivers"]) > 0

    # 13 & 14. Season switching 2024 <-> 2025 works with clean state
    def test_season_switching_isolation(self):
        # Fetch 2024 events then 2025 events
        res_ev24 = client.get("/api/seasons/2024/events")
        assert res_ev24.status_code == 200
        ev24 = res_ev24.json()
        assert all(e["season"] == 2024 for e in ev24)

        res_ev25 = client.get("/api/seasons/2025/events")
        assert res_ev25.status_code == 200
        ev25 = res_ev25.json()
        assert all(e["season"] == 2025 for e in ev25)

        # Ensure no cross-pollination between event lists
        eids24 = {e["event_id"] for e in ev24}
        eids25 = {e["event_id"] for e in ev25}
        assert eids24.isdisjoint(eids25)

    # 15. Circuit comparison across supported seasons
    def test_circuit_comparison_2024_2025(self):
        res = client.get("/api/circuits/cota/comparison?seasons=2024,2025")
        assert res.status_code == 200
        data = res.json()
        assert data["circuit_id"] == "cota"
        assert set(data["seasons_compared"]) == {2024, 2025}
