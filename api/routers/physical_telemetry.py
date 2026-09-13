"""
TrackShift Physical Telemetry Router.

Endpoints for physical sensor packet ingestion, device heartbeat status,
health auditing, historical time-series queries, and live WebSocket streaming.
"""

import os
from fastapi import APIRouter, Header, HTTPException, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Any, Optional, List

from api.services.physical_telemetry_service import (
    get_physical_telemetry_service,
    PhysicalTelemetryValidationException,
    PhysicalTelemetryRateLimitException
)

router = APIRouter(prefix="/api/physical-telemetry", tags=["Physical Telemetry"])

# Device security key (configurable via env var, defaults to standard dev key)
EXPECTED_DEVICE_KEY = os.environ.get("PHYSICAL_DEVICE_KEY", "trackshift_dev_key_2025")
ENFORCE_DEVICE_KEY = os.environ.get("ENFORCE_DEVICE_KEY", "false").lower() in ("true", "1", "yes")


def verify_device_key(x_device_key: Optional[str] = Header(None, alias="X-Device-Key")):
    """Validates device authentication key if enforcement is active."""
    if ENFORCE_DEVICE_KEY:
        if not x_device_key or x_device_key.strip() != EXPECTED_DEVICE_KEY:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized: Invalid or missing X-Device-Key header"
            )
    return True


@router.post("/ingest")
async def ingest_sensor_packet(
    packet: Dict[str, Any],
    x_device_key: Optional[str] = Header(None, alias="X-Device-Key")
):
    """
    Ingests a real physical sensor packet from an ESP32, Arduino, Raspberry Pi,
    or USB Serial Gateway.

    Validates schema, physical ranges, units, and enforces rate limits.
    Fans out normalized event to all connected frontends via WebSocket.
    """
    if ENFORCE_DEVICE_KEY and x_device_key != EXPECTED_DEVICE_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Invalid or missing X-Device-Key header"
        )

    service = get_physical_telemetry_service()
    try:
        result = await service.ingest_packet(packet)
        return result
    except PhysicalTelemetryValidationException as ve:
        raise HTTPException(status_code=422, detail=f"Physical Validation Error: {str(ve)}")
    except PhysicalTelemetryRateLimitException as rle:
        raise HTTPException(status_code=429, detail=f"Rate Limit Exceeded: {str(rle)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion processing error: {str(e)}")


@router.get("/status")
async def get_system_status():
    """
    Returns the authoritative real-time heartbeat and connection status
    of the physical telemetry ingestion subsystem.
    """
    service = get_physical_telemetry_service()
    return service.get_global_status()


@router.get("/devices")
async def get_registered_devices():
    """
    Lists all known physical devices with their connection status (online/stale/offline),
    packet rates, transport types, and individual sensor health.
    """
    service = get_physical_telemetry_service()
    return service.get_devices()


@router.get("/latest/{device_id}")
async def get_latest_telemetry(device_id: str):
    """
    Returns the latest normalized telemetry packet for a specific physical device.
    """
    service = get_physical_telemetry_service()
    data = service.get_latest(device_id)
    if data is None:
        raise HTTPException(
            status_code=404,
            detail=f"Device '{device_id}' has not transmitted any telemetry or is unknown."
        )
    return data


@router.get("/history/{device_id}")
async def get_device_history(device_id: str, limit: int = Query(200, ge=1, le=1000)):
    """
    Returns historical physical telemetry packets for charting with true gaps.
    """
    service = get_physical_telemetry_service()
    return service.get_history(device_id, limit=limit)


@router.websocket("/ws")
async def physical_telemetry_websocket(websocket: WebSocket):
    """
    Dedicated WebSocket endpoint for streaming real physical sensor telemetry
    to frontend clients.
    """
    service = get_physical_telemetry_service()
    await service.register_websocket(websocket)
    try:
        while True:
            # Keep-alive loop
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        service.unregister_websocket(websocket)
    except Exception:
        service.unregister_websocket(websocket)
