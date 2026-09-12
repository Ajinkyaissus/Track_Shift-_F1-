"""
TrackShift — Strategic Warfare Router
====================================
Exposes the 5 modules, decision fusion, and checkpoint series via REST endpoints:
- GET /api/sessions/{session_id}/strategic-warfare
- GET /api/sessions/{session_id}/strategic-warfare/decision
- GET /api/sessions/{session_id}/strategic-warfare/competitor-radar
- GET /api/sessions/{session_id}/strategic-warfare/ghost-car-roi
- GET /api/sessions/{session_id}/strategic-warfare/checkpoints
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from api.services.strategic_warfare_service import StrategicWarfareService

router = APIRouter(prefix="/api/sessions", tags=["strategic-warfare"])

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tyredebt.db")


def get_service(request: Request) -> StrategicWarfareService:
    app_data = getattr(request.app.state, "app_data", {})
    return StrategicWarfareService(db_path=DB_PATH, app_data=app_data)


@router.get("/{session_id}/strategic-warfare")
async def get_strategic_warfare(
    session_id: str,
    driver_id: Optional[str] = Query(None, description="Driver identifier (e.g. ALB, VER, NOR)"),
    lap: Optional[int] = Query(None, description="Current race lap for strategic checkpoint evaluation"),
    service: StrategicWarfareService = Depends(get_service)
):
    """
    Returns full Strategic Warfare bundle combining all 5 modules, decision fusion,
    and candidate strategy simulations.
    """
    try:
        data = service.get_strategic_warfare_analysis(
            session_id=session_id,
            driver_id=driver_id,
            lap=lap
        )
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Strategic Warfare analysis failed: {str(e)}")


@router.get("/{session_id}/strategic-warfare/decision")
async def get_strategic_decision(
    session_id: str,
    driver_id: Optional[str] = Query(None),
    lap: Optional[int] = Query(None),
    service: StrategicWarfareService = Depends(get_service)
):
    """
    Returns Decision Fusion recommendations (BEST ACTION, WHY, RISK, ALTERNATIVE, BATTLE MATRIX).
    """
    try:
        data = service.get_strategic_warfare_analysis(session_id=session_id, driver_id=driver_id, lap=lap)
        return JSONResponse(content=data.get("strategic_decision_fusion", {}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/strategic-warfare/competitor-radar")
async def get_competitor_radar(
    session_id: str,
    driver_id: Optional[str] = Query(None),
    lap: Optional[int] = Query(None),
    service: StrategicWarfareService = Depends(get_service)
):
    """
    Returns Competitor Undercut Vulnerability radar and attack windows.
    """
    try:
        data = service.get_strategic_warfare_analysis(session_id=session_id, driver_id=driver_id, lap=lap)
        return JSONResponse(content=data.get("undercut_vulnerability", {}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/strategic-warfare/ghost-car-roi")
async def get_ghost_car_roi(
    session_id: str,
    driver_id: Optional[str] = Query(None),
    lap: Optional[int] = Query(None),
    service: StrategicWarfareService = Depends(get_service)
):
    """
    Returns Ghost-Car Pit ROI Multi-Lap simulation curve.
    """
    try:
        data = service.get_strategic_warfare_analysis(session_id=session_id, driver_id=driver_id, lap=lap)
        return JSONResponse(content=data.get("ghost_car_roi", {}))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{session_id}/strategic-warfare/checkpoints")
async def get_checkpoint_series(
    session_id: str,
    driver_id: str = Query(..., description="Driver identifier"),
    service: StrategicWarfareService = Depends(get_service)
):
    """
    Returns strategic recommendations across all historical checkpoints
    [PRE-RACE, 5, 10, 15, 20, 25, 30, 40, 45].
    """
    try:
        series = service.get_checkpoint_series(session_id=session_id, driver_id=driver_id)
        return JSONResponse(content={"session_id": session_id, "driver_id": driver_id, "checkpoints": series})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
