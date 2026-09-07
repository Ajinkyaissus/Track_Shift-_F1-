"""
Signatures Router for TrackShift.
Endpoints for driver profile signatures and signature transfer simulations.
"""

from fastapi import APIRouter
from api.services.signatures_service import SignatureTransferRequest

router = APIRouter(tags=["signatures"])

signatures_service = None

def set_signatures_service(service):
    global signatures_service
    signatures_service = service

def get_signatures_service():
    global signatures_service
    if signatures_service is None:
        from api.services.signatures_service import SignaturesService
        from api.main import app_data, DB_PATH
        signatures_service = SignaturesService(DB_PATH, app_data)
    return signatures_service

@router.get("/signatures")
async def get_signatures():
    return await get_signatures_service().get_signatures()

@router.post("/stints/{stint_id}/signature_transfer")
async def compute_signature_transfer(stint_id: str, req: SignatureTransferRequest):
    target_driver = req.target_driver_id or req.target_driver
    return await get_signatures_service().compute_signature_transfer(stint_id, target_driver)
