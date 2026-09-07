"""
TrackShift API Routers Subsystem.
"""

from api.routers.circuits import router as circuits_router, set_circuits_service
from api.routers.stints import router as stints_router, set_stint_services
from api.routers.signatures import router as signatures_router, set_signatures_service
from api.routers.admin import router as admin_router

__all__ = [
    "circuits_router",
    "set_circuits_service",
    "stints_router",
    "set_stint_services",
    "signatures_router",
    "set_signatures_service",
    "admin_router"
]
