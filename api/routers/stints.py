"""
Stints Router for TrackShift.
Endpoints for races, stints, tyre debt ledgers, attributions, counterfactuals, and comparisons.
"""

from typing import Optional
from fastapi import APIRouter
from api.services.counterfactual_service import CounterfactualRequest

router = APIRouter(tags=["stints"])

stints_service = None
tyre_debt_service = None
counterfactual_service = None

def set_stint_services(st_service, td_service, cf_service):
    global stints_service, tyre_debt_service, counterfactual_service
    stints_service = st_service
    tyre_debt_service = td_service
    counterfactual_service = cf_service

def get_stints_service():
    global stints_service
    if stints_service is None:
        from api.services.stints_service import StintsService
        from api.main import app_data, DB_PATH
        stints_service = StintsService(DB_PATH, app_data)
    return stints_service

def get_tyre_debt_service():
    global tyre_debt_service
    if tyre_debt_service is None:
        from api.services.tyre_debt_service import TyreDebtService
        from api.main import app_data, DB_PATH
        tyre_debt_service = TyreDebtService(DB_PATH, app_data)
    return tyre_debt_service

def get_counterfactual_service():
    global counterfactual_service
    if counterfactual_service is None:
        from api.services.counterfactual_service import CounterfactualService
        from api.main import app_data
        counterfactual_service = CounterfactualService(app_data)
    return counterfactual_service

@router.get("/races")
async def get_races():
    return await get_stints_service().get_races()

@router.get("/stints")
async def get_stints_by_query(race_id: Optional[str] = None):
    return await get_stints_service().get_stints_by_query(race_id)

@router.get("/sessions/{race_id}/stints")
async def get_stints(race_id: str):
    return await get_stints_service().get_stints_by_query(race_id)

@router.get("/stints/{stint_id}/ledger")
async def get_ledger(stint_id: str):
    return await get_tyre_debt_service().get_ledger(stint_id)

@router.get("/stints/{stint_id}/attribution")
async def get_attribution(stint_id: str):
    return await get_tyre_debt_service().get_attribution(stint_id)

@router.post("/stints/{stint_id}/counterfactual")
async def compute_counterfactual(stint_id: str, req: CounterfactualRequest):
    return await get_counterfactual_service().compute_counterfactual(stint_id, req.feature, req.delta_pct)

@router.get("/stints/compare")
async def compare_stints(stint_a: str, stint_b: str):
    return await get_stints_service().compare_stints(stint_a, stint_b)
