"""
TrackShift — Universal Race Intelligence Router
================================================
Universal REST endpoints for:
- /api/sessions/{session_id}/race-intelligence
- /api/sessions/{session_id}/race-intelligence/drivers
- /api/sessions/{session_id}/race-intelligence/strategy
- /api/sessions/{session_id}/race-intelligence/validation
- /api/sessions/{session_id}/race-intelligence/{driver_id}
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from api.services.race_intelligence_service import RaceIntelligenceService

router = APIRouter(tags=["race_intelligence"])

race_intelligence_service: Optional[RaceIntelligenceService] = None


def set_race_intelligence_service(service: RaceIntelligenceService):
    global race_intelligence_service
    race_intelligence_service = service


def get_race_intelligence_service() -> RaceIntelligenceService:
    global race_intelligence_service
    if race_intelligence_service is None:
        from api.main import app_data, DB_PATH
        race_intelligence_service = RaceIntelligenceService(DB_PATH, app_data)
    return race_intelligence_service


@router.get("/sessions/{session_id}/race-intelligence")
@router.get("/api/sessions/{session_id}/race-intelligence")
async def get_session_race_intelligence(
    session_id: str,
    driver_id: Optional[str] = Query(None, description="Optional driver focus filter e.g. VER"),
    replay_lap: Optional[int] = Query(None, description="Current replay lap for in-race dynamic forecast"),
    temporal_mode: str = Query("AUTO", description="AUTO | PRE_RACE | IN_RACE | POST_RACE")
):
    """
    Returns full-field universal race intelligence payload for the session:
    - Winner & podium probabilities for all real drivers
    - Full-race lap projection and strategy options
    - Tyre outlook, degradation rate, tyre debt
    - Driving behaviour, braking and throttle metrics, TCN embeddings
    - Prediction explanation attribution
    - Post-race validation scorecard
    """
    svc = get_race_intelligence_service()
    return await svc.compute_universal_race_intelligence(
        session_id=session_id,
        driver_id=driver_id,
        replay_lap=replay_lap,
        temporal_mode=temporal_mode
    )


@router.get("/sessions/{session_id}/race-intelligence/drivers")
@router.get("/api/sessions/{session_id}/race-intelligence/drivers")
async def get_session_race_intelligence_drivers(session_id: str):
    """
    Returns the normalized driver contract roster and data availability status
    for all drivers registered in the session.
    """
    svc = get_race_intelligence_service()
    return svc.get_session_drivers_contract(session_id=session_id)


@router.get("/sessions/{session_id}/race-intelligence/strategy")
@router.get("/api/sessions/{session_id}/race-intelligence/strategy")
async def compare_race_intelligence_strategy(
    session_id: str,
    driver_a: str = Query(..., description="First driver code (e.g. VER)"),
    driver_b: str = Query(..., description="Second driver code (e.g. NOR)")
):
    """
    Compares strategy projections, pit stop windows, and tyre performance debt
    between any two drivers in the session.
    """
    svc = get_race_intelligence_service()
    return await svc.compare_multi_driver_strategies(
        session_id=session_id,
        driver_a=driver_a,
        driver_b=driver_b
    )


@router.get("/sessions/{session_id}/race-intelligence/validation")
@router.get("/api/sessions/{session_id}/race-intelligence/validation")
async def get_race_intelligence_validation(session_id: str):
    """
    Returns post-race validation metrics comparing predicted finish order vs actual classification.
    """
    svc = get_race_intelligence_service()
    res = await svc.compute_universal_race_intelligence(session_id=session_id, temporal_mode="POST_RACE")
    return {
        "session_id": session_id,
        "circuit_id": res.get("circuit_id"),
        "validation": res.get("post_race_validation"),
        "provenance": res.get("provenance")
    }


@router.get("/sessions/{session_id}/race-intelligence/{driver_id}")
@router.get("/api/sessions/{session_id}/race-intelligence/{driver_id}")
async def get_driver_race_intelligence(
    session_id: str,
    driver_id: str,
    replay_lap: Optional[int] = Query(None, description="Optional replay lap filter")
):
    """
    Returns deep-dive race intelligence payload for a single driver in the session.
    """
    svc = get_race_intelligence_service()
    res = await svc.compute_universal_race_intelligence(
        session_id=session_id,
        driver_id=driver_id,
        replay_lap=replay_lap
    )
    if not res.get("selected_driver"):
        raise HTTPException(status_code=404, detail=f"Driver '{driver_id}' not found in session '{session_id}'")
    return res["selected_driver"]
