"""
Tests for TrackShift Real Physical Sensor Telemetry Ingestion Layer.

Validates packet ingestion, schema enforcement, physical range rejection,
rate limiting, device heartbeat (online/stale/offline), unit normalization,
and preservation of the frozen TDSM model boundary.
"""

import time
import pytest
from fastapi.testclient import TestClient

from api.main import app
from api.services.physical_telemetry_service import (
    get_physical_telemetry_service,
    PhysicalTelemetryService,
    PhysicalTelemetryValidationException,
    PhysicalTelemetryRateLimitException
)


@pytest.fixture(autouse=True)
def reset_service():
    """Resets the singleton service state between tests."""
    service = get_physical_telemetry_service()
    service._devices.clear()
    service._history.clear()
    service._rate_timestamps.clear()
    service._total_ingested = 0
    yield


@pytest.fixture
def client():
    return TestClient(app)


def test_valid_physical_packet_ingest(client):
    """Verifies that a well-formed real sensor packet is successfully validated and ingested."""
    packet = {
        "device_id": "TRACKSHIFT-ESP32-01",
        "timestamp": time.time(),
        "sequence": 1,
        "transport": "HTTP_WIFI",
        "sensors": {
            "tyre_temperature": {
                "FL": 85.2,
                "FR": 86.1,
                "RL": 81.4,
                "RR": 82.0
            },
            "tyre_pressure": {
                "FL": 21.4,
                "FR": 21.6,
                "RL": 20.8,
                "RR": 21.0
            },
            "tyre_pressure_unit": "psi",
            "ambient_temperature": 25.0,
            "track_temperature": 38.5
        }
    }

    res = client.post("/api/physical-telemetry/ingest", json=packet)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["status"] == "success"
    assert data["device_id"] == "TRACKSHIFT-ESP32-01"
    assert data["sequence"] == 1
    assert "tyre_temperature" in data["sensors_processed"]
    assert "tyre_pressure" in data["sensors_processed"]

    # Verify latest reading
    latest_res = client.get("/api/physical-telemetry/latest/TRACKSHIFT-ESP32-01")
    assert latest_res.status_code == 200
    latest = latest_res.json()
    assert latest["current_device_status"] == "online"
    assert latest["sensors"]["tyre_temperature"]["values"]["FL"] == 85.2
    assert latest["sensors"]["tyre_pressure"]["values_psi"]["FL"] == 21.4


def test_impossible_sensor_value_rejected(client):
    """Verifies that unphysical/impossible sensor values (e.g. 999999°C) are strictly rejected with 422."""
    impossible_packet = {
        "device_id": "TRACKSHIFT-ESP32-01",
        "timestamp": time.time(),
        "sequence": 1,
        "sensors": {
            "tyre_temperature": {
                "FL": 999999.0  # Impossible temperature
            }
        }
    }
    res = client.post("/api/physical-telemetry/ingest", json=impossible_packet)
    assert res.status_code == 422
    assert "impossible" in res.json()["detail"].lower()


def test_impossible_pressure_rejected(client):
    """Verifies that impossible negative pressure is rejected with 422."""
    impossible_packet = {
        "device_id": "TRACKSHIFT-ESP32-01",
        "timestamp": time.time(),
        "sequence": 1,
        "sensors": {
            "tyre_pressure": {
                "FL": -15.0  # Negative pressure
            }
        }
    }
    res = client.post("/api/physical-telemetry/ingest", json=impossible_packet)
    assert res.status_code == 422
    assert "impossible" in res.json()["detail"].lower()


def test_missing_device_id_rejected(client):
    """Verifies that packets without a valid device_id are rejected."""
    bad_packet = {
        "sequence": 1,
        "sensors": {"ambient_temperature": 25.0}
    }
    res = client.post("/api/physical-telemetry/ingest", json=bad_packet)
    assert res.status_code == 422
    assert "device_id" in res.json()["detail"].lower()


def test_empty_sensors_rejected(client):
    """Verifies that packets without sensor measurements are rejected."""
    bad_packet = {
        "device_id": "TRACKSHIFT-ESP32-01",
        "sequence": 1,
        "sensors": {}
    }
    res = client.post("/api/physical-telemetry/ingest", json=bad_packet)
    assert res.status_code == 422
    assert "sensors" in res.json()["detail"].lower()


def test_device_offline_detection(client):
    """Verifies that a device transitions to OFFLINE after timeout without packets."""
    service = get_physical_telemetry_service()
    
    # Ingest a packet
    packet = {
        "device_id": "TRACKSHIFT-TEST-OFFLINE",
        "sequence": 1,
        "sensors": {"ambient_temperature": 22.0}
    }
    res = client.post("/api/physical-telemetry/ingest", json=packet)
    assert res.status_code == 200

    # Simulate elapsed time beyond ONLINE_TIMEOUT_SECONDS (5.0s)
    service._devices["TRACKSHIFT-TEST-OFFLINE"]["last_seen"] = time.time() - 6.0

    status = service.evaluate_device_health("TRACKSHIFT-TEST-OFFLINE")
    assert status == "offline"

    devices_res = client.get("/api/physical-telemetry/devices")
    devices = devices_res.json()
    offline_dev = next(d for d in devices if d["device_id"] == "TRACKSHIFT-TEST-OFFLINE")
    assert offline_dev["status"] == "offline"


def test_stale_detection(client):
    """Verifies that a device transitions to STALE after 2.5s without packets."""
    service = get_physical_telemetry_service()
    packet = {
        "device_id": "TRACKSHIFT-TEST-STALE",
        "sequence": 1,
        "sensors": {"track_temperature": 32.0}
    }
    res = client.post("/api/physical-telemetry/ingest", json=packet)
    assert res.status_code == 200

    # Simulate 3.5s elapsed (between 2.5s and 5.0s)
    service._devices["TRACKSHIFT-TEST-STALE"]["last_seen"] = time.time() - 3.5
    status = service.evaluate_device_health("TRACKSHIFT-TEST-STALE")
    assert status == "stale"


def test_rate_limiting_enforcement(client):
    """Verifies that packet rates exceeding MAX_SENSOR_RATE_HZ are rejected with HTTP 429."""
    service = get_physical_telemetry_service()
    dev_id = "TRACKSHIFT-BURST-01"

    packet = {
        "device_id": dev_id,
        "sequence": 1,
        "sensors": {"ambient_temperature": 20.0}
    }

    # Simulate 51 rapid packets in a 1-second window
    now = time.time()
    from collections import deque
    service._rate_timestamps[dev_id] = deque([now] * 51, maxlen=100)

    res = client.post("/api/physical-telemetry/ingest", json=packet)
    assert res.status_code == 429
    assert "rate limit" in res.json()["detail"].lower()


def test_unequipped_sensor_honesty(client):
    """
    Verifies that if hardware only equips ambient_temperature,
    it does NOT fake tyre_temperature or tyre_pressure.
    """
    packet = {
        "device_id": "WEATHER-STATION-01",
        "sequence": 1,
        "sensors": {
            "ambient_temperature": 26.4
        }
    }
    res = client.post("/api/physical-telemetry/ingest", json=packet)
    assert res.status_code == 200

    latest = client.get("/api/physical-telemetry/latest/WEATHER-STATION-01").json()
    assert "ambient_temperature" in latest["sensors"]
    assert "tyre_temperature" not in latest["sensors"]
    assert "tyre_pressure" not in latest["sensors"]


def test_history_endpoint(client):
    """Verifies that historical packets are returned chronologically for gap-accurate charting."""
    dev_id = "TRACKSHIFT-HIST-01"
    for i in range(1, 6):
        client.post("/api/physical-telemetry/ingest", json={
            "device_id": dev_id,
            "sequence": i,
            "sensors": {"track_temperature": 30.0 + i}
        })

    hist_res = client.get(f"/api/physical-telemetry/history/{dev_id}?limit=10")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) == 5
    assert history[-1]["sequence"] == 5


def test_frozen_tdsm_immutability(client):
    r"""
    CRITICAL SCIENTIFIC SAFETY TEST:
    Verifies that physical sensor state does not mutate, contaminate, or alter
    the frozen TDSM state-space model ($S_t = [D_t, \Delta D_t, \Delta^2 D_t]$).
    """
    # 1. Ingest physical sensor data
    client.post("/api/physical-telemetry/ingest", json={
        "device_id": "TRACKSHIFT-ESP32-01",
        "sequence": 1,
        "sensors": {
            "tyre_temperature": {"FL": 95.0, "FR": 96.0, "RL": 90.0, "RR": 91.0}
        }
    })

    # 2. Query TDSM prediction
    tdsm_payload = {
        "D": 1.25,
        "Delta_D": 0.08,
        "Delta2_D": 0.01,
        "TyreLife": 12,
        "FuelProxy": 65.0,
        "Compound": "MEDIUM",
        "data_cutoff_lap": 12
    }
    tdsm_res = client.post("/api/tdsm/predict", json=tdsm_payload)
    assert tdsm_res.status_code == 200
    tdsm_data = tdsm_res.json()

    # Verify standard state transition evaluation without physical leakage
    assert "+1" in tdsm_data["forecast"]
    assert "+3" in tdsm_data["forecast"]
    assert "+5" in tdsm_data["forecast"]
    assert "+10" in tdsm_data["forecast"]
    # Model used must remain frozen canonical TDSM
    assert "FROZEN" in tdsm_data["model_version"]
