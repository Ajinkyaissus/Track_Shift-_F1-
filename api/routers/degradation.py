"""
TrackShift — Degradation, Prediction & Validation Router.
REST endpoints for:
- /api/sessions/{session_id}/degradation
- /api/sessions/{session_id}/prediction
- /api/sessions/{session_id}/validation
- /api/events/{event_id}/practice-race-validation
- /api/sessions/{session_id}/degradation/compare-drivers
- /api/sessions/{session_id}/degradation/compare-compounds
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from api.services.degradation_service import DegradationService

router = APIRouter(tags=["degradation"])

degradation_service: Optional[DegradationService] = None


def set_degradation_service(service: DegradationService):
    global degradation_service
    degradation_service = service


def get_degradation_service() -> DegradationService:
    global degradation_service
    if degradation_service is None:
        from api.main import app_data, DB_PATH
        degradation_service = DegradationService(DB_PATH, app_data)
    return degradation_service


@router.get("/sessions/{session_id}/degradation")
@router.get("/api/sessions/{session_id}/degradation")
async def get_session_degradation(
    session_id: str,
    driver_id: Optional[str] = Query(None, description="Optional driver filter e.g. VER"),
    compound: Optional[str] = Query(None, description="Optional tyre compound filter e.g. MEDIUM"),
    stint_id: Optional[str] = Query(None, description="Optional stint filter")
):
    """
    Returns clean model-estimated tyre-performance degradation curves,
    accounting for contextual variables (fuel load, track evolution, tyre age, compound).
    """
    svc = get_degradation_service()
    return await svc.get_session_degradation(
        session_id=session_id,
        driver_id=driver_id,
        compound=compound,
        stint_id=stint_id
    )


@router.get("/sessions/{session_id}/prediction")
@router.get("/api/sessions/{session_id}/prediction")
async def get_session_prediction(
    session_id: str,
    driver_id: Optional[str] = Query(None, description="Optional driver filter e.g. VER"),
    compound: Optional[str] = Query(None, description="Optional compound filter")
):
    """
    Generates pre-race pace predictions and projected race tyre degradation curves.
    Strictly isolated: Derived ONLY from pre-race/practice session telemetry with frozen cryptographic fingerprint.
    """
    svc = get_degradation_service()
    return await svc.get_session_prediction(
        session_id=session_id,
        driver_id=driver_id,
        compound=compound
    )


@router.get("/sessions/{session_id}/validation")
@router.get("/api/sessions/{session_id}/validation")
async def get_session_validation(
    session_id: str,
    practice_session_id: Optional[str] = Query(None, description="Practice session used to generate prediction"),
    driver_id: Optional[str] = Query(None, description="Optional driver filter"),
    compound: Optional[str] = Query(None, description="Optional compound filter")
):
    """
    Post-Race Validation workflow comparing frozen practice prediction against actual race-day observed pace.
    """
    svc = get_degradation_service()
    p_id = practice_session_id or session_id.replace("_R", "_FP2").replace("_FP1", "_FP2")
    return await svc.get_post_race_validation(
        practice_session_id=p_id,
        race_session_id=session_id,
        driver_id=driver_id,
        compound=compound
    )


@router.get("/events/{event_id}/practice-race-validation")
@router.get("/api/events/{event_id}/practice-race-validation")
async def get_event_practice_race_validation(
    event_id: str,
    practice_session_type: str = Query("FP2", description="Practice session type e.g. FP1, FP2, FP3"),
    driver_id: Optional[str] = Query(None, description="Optional driver filter"),
    compound: Optional[str] = Query(None, description="Optional compound filter")
):
    """
    Event-level practice-to-race validation tool.
    Matches the event's practice session with its race session.
    """
    svc = get_degradation_service()
    p_id = f"{event_id}_{practice_session_type}"
    r_id = f"{event_id}_R"
    return await svc.get_post_race_validation(
        practice_session_id=p_id,
        race_session_id=r_id,
        driver_id=driver_id,
        compound=compound
    )


@router.get("/sessions/{session_id}/degradation/compare-drivers")
@router.get("/api/sessions/{session_id}/degradation/compare-drivers")
async def compare_drivers_degradation(
    session_id: str,
    driver_a: str = Query(..., description="First driver code (e.g. VER)"),
    driver_b: str = Query(..., description="Second driver code (e.g. NOR)"),
    compound: Optional[str] = Query(None, description="Optional compound filter")
):
    """
    Cross-driver degradation and tyre debt comparison for the session.
    """
    svc = get_degradation_service()
    return await svc.compare_drivers_degradation(
        session_id=session_id,
        driver_a=driver_a,
        driver_b=driver_b,
        compound=compound
    )


@router.get("/sessions/{session_id}/degradation/compare-compounds")
@router.get("/api/sessions/{session_id}/degradation/compare-compounds")
async def compare_compounds_degradation(
    session_id: str,
    driver_id: Optional[str] = Query(None, description="Optional driver filter")
):
    """
    Cross-compound degradation comparison for available compounds in the session.
    """
    svc = get_degradation_service()
    return await svc.compare_compounds_degradation(
        session_id=session_id,
        driver_id=driver_id
    )
