import os
from typing import Optional
from fastapi import APIRouter

router = APIRouter(prefix="/circuits", tags=["circuits"])

# Injected by main.py
circuits_service = None

def set_circuits_service(service):
    global circuits_service
    circuits_service = service

def get_circuits_service():
    global circuits_service
    if circuits_service is None:
        from api.services.circuits_service import CircuitsService
        from api.main import app_data, DB_PATH
        circuits_service = CircuitsService(DB_PATH, app_data)
    return circuits_service

@router.get("")
async def get_circuits():
    return await get_circuits_service().get_circuits()

@router.get("/{circuit_id}")
async def get_circuit_detail(circuit_id: str):
    return await get_circuits_service().get_circuit_detail(circuit_id)

@router.get("/{circuit_id}/map")
async def get_circuit_map(circuit_id: str):
    return await get_circuits_service().get_circuit_map(circuit_id)

@router.get("/{circuit_id}/sessions")
async def get_circuit_sessions(circuit_id: str):
    return await get_circuits_service().get_circuit_sessions(circuit_id)

@router.get("/{circuit_id}/stints")
async def get_circuit_stints(
    circuit_id: str,
    driver_id: Optional[str] = None,
    compound: Optional[str] = None
):
    return await get_circuits_service().get_circuit_stints(circuit_id, driver_id, compound)

@router.get("/{circuit_id}/sessions/{session_id}/drivers")
async def get_session_drivers(circuit_id: str, session_id: str):
    return await get_circuits_service().get_session_drivers(circuit_id, session_id)

@router.get("/{circuit_id}/sessions/{session_id}/telemetry")
async def get_session_telemetry(circuit_id: str, session_id: str):
    return await get_circuits_service().get_session_telemetry(circuit_id, session_id)

@router.get("/{circuit_id}/sessions/{session_id}/leaderboard")
async def get_session_leaderboard(circuit_id: str, session_id: str, lap: Optional[int] = None):
    return await get_circuits_service().get_session_leaderboard(circuit_id, session_id, lap)

@router.get("/{circuit_id}/sessions/{session_id}/drivers/analytics")
async def get_session_drivers_analytics(circuit_id: str, session_id: str):
    return await get_circuits_service().get_session_drivers_analytics(circuit_id, session_id)

@router.get("/{circuit_id}/sessions/{session_id}/drivers/{driver_id}/analytics")
async def get_driver_analytics(circuit_id: str, session_id: str, driver_id: str):
    return await get_circuits_service().get_driver_analytics(circuit_id, session_id, driver_id)

@router.get("/{circuit_id}/sessions/{session_id}/drivers/{driver_id}/laps")
async def get_driver_laps(circuit_id: str, session_id: str, driver_id: str):
    return await get_circuits_service().get_driver_laps(circuit_id, session_id, driver_id)

@router.get("/{circuit_id}/sessions/{session_id}/drivers/{driver_id}/stints")
async def get_driver_stints(circuit_id: str, session_id: str, driver_id: str):
    return await get_circuits_service().get_driver_stints(circuit_id, session_id, driver_id)
