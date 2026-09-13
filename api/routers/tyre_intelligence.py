"""
TrackShift — Confounder-Aware Tyre Intelligence Router
=======================================================
REST Endpoints for:
- Feature Provenance Catalog (/api/tyre-intelligence/provenance)
- Estimated Tyre Performance Degradation Curve (/api/tyre-intelligence/degradation-curve)
- 8-Model Confounder Ablation Study (/api/tyre-intelligence/ablation)
- Post-Race Validation Suite (/api/tyre-intelligence/post-race-validation)
- Confounder Breakdown (/api/tyre-intelligence/confounder-breakdown)
- Session-specific Tyre Intelligence (/api/sessions/{session_id}/tyre-intelligence)
"""

import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from api.services.tyre_intelligence_service import TyreIntelligenceService

router = APIRouter(tags=["tyre-intelligence"])

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tyredebt.db")


def get_service(request: Request) -> TyreIntelligenceService:
    app_data = getattr(request.app.state, "app_data", {})
    return TyreIntelligenceService(db_path=DB_PATH, app_data=app_data)


@router.get("/api/tyre-intelligence/provenance")
async def get_provenance(service: TyreIntelligenceService = Depends(get_service)):
    """Returns the feature provenance catalog for all 11 observable features."""
    try:
        data = service.get_provenance_catalog()
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provenance fetch failed: {str(e)}")


@router.get("/api/tyre-intelligence/degradation-curve")
async def get_degradation_curve(
    circuit_id: str = Query("silverstone", description="Circuit ID"),
    driver_id: str = Query("HAM", description="Driver code"),
    session_id: Optional[str] = Query(None, description="Session ID"),
    stint_id: Optional[str] = Query(None, description="Stint ID"),
    checkpoint_lap: Optional[int] = Query(None, description="Causal evaluation age"),
    service: TyreIntelligenceService = Depends(get_service),
):
    """
    Returns the Estimated Tyre Performance Degradation Curve with bootstrap uncertainty
    and observable confounder breakdown.
    """
    try:
        data = service.get_estimated_degradation_curve(
            circuit_id=circuit_id,
            driver_id=driver_id,
            session_id=session_id,
            stint_id=stint_id,
            max_tyre_age=checkpoint_lap,
        )
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Curve generation failed: {str(e)}")


@router.get("/api/tyre-intelligence/ablation")
async def get_ablation(
    dataset_name: str = Query("2024_2025_Telemetry", description="Ablation dataset split"),
    service: TyreIntelligenceService = Depends(get_service),
):
    """
    Returns the 8-model ablation study and placebo test report.
    """
    try:
        data = service.get_ablation_study(dataset_name=dataset_name)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ablation study failed: {str(e)}")


@router.get("/api/tyre-intelligence/post-race-validation")
async def get_post_race_validation(
    circuit_id: Optional[str] = Query(None, description="Filter by circuit"),
    service: TyreIntelligenceService = Depends(get_service),
):
    """
    Returns post-race validation comparing predicted wear against actual race-day pace (+1, +3, +5, +10 laps).
    """
    try:
        data = service.get_post_race_validation(circuit_id=circuit_id)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Post-race validation failed: {str(e)}")


@router.get("/api/tyre-intelligence/confounder-breakdown")
async def get_confounder_breakdown(
    circuit_id: str = Query("silverstone", description="Circuit ID"),
    driver_id: str = Query("HAM", description="Driver code"),
    service: TyreIntelligenceService = Depends(get_service),
):
    """
    Returns detailed observable confounder decomposition for a given driver and circuit.
    """
    try:
        data = service.get_confounder_breakdown(circuit_id=circuit_id, driver_id=driver_id)
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Confounder breakdown failed: {str(e)}")


@router.get("/api/sessions/{session_id}/driver-advisory")
@router.get("/sessions/{session_id}/driver-advisory")
async def get_session_driver_advisory(
    session_id: str,
    driver_id: Optional[str] = Query(None, description="Driver code"),
    lap: Optional[int] = Query(None, description="Current lap number"),
    request: Request = None,
):
    """
    Returns concise, operational, machine-readable radio advisory recommendation for driver/race-engineer.
    """
    try:
        app_data = getattr(request.app.state, "app_data", {}) if request else {}
        from api.services.driver_advisory_service import DriverAdvisoryService
        adv_service = DriverAdvisoryService(db_path=DB_PATH, app_data=app_data)
        data = adv_service.get_driver_advisory(session_id=session_id, driver_id=driver_id, lap=lap)
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Driver advisory failed: {str(e)}")


@router.get("/api/tyre-intelligence/driver-advisory")
async def get_tyre_intel_driver_advisory(
    session_id: str = Query("2024_silverstone_R", description="Session ID"),
    driver_id: Optional[str] = Query(None, description="Driver code"),
    lap: Optional[int] = Query(None, description="Current lap number"),
    current_lap: Optional[int] = Query(None, description="Current lap number fallback"),
    request: Request = None,
):
    """
    Query-param scoped driver advisory endpoint.
    """
    try:
        effective_lap = lap if lap is not None else current_lap
        app_data = getattr(request.app.state, "app_data", {}) if request else {}
        from api.services.driver_advisory_service import DriverAdvisoryService
        adv_service = DriverAdvisoryService(db_path=DB_PATH, app_data=app_data)
        data = adv_service.get_driver_advisory(session_id=session_id, driver_id=driver_id, lap=effective_lap)
        return JSONResponse(content=data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Driver advisory failed: {str(e)}")

