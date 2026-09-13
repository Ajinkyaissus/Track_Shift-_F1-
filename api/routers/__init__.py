"""
TrackShift API Routers Subsystem.
"""

from api.routers.circuits import router as circuits_router, set_circuits_service
from api.routers.seasons import router as seasons_router, set_circuits_service as set_seasons_circuits_service
from api.routers.stints import router as stints_router, set_stint_services
from api.routers.signatures import router as signatures_router, set_signatures_service
from api.routers.degradation import router as degradation_router, set_degradation_service
from api.routers.race_intelligence import router as race_intelligence_router, set_race_intelligence_service
from api.routers.strategic_warfare import router as strategic_warfare_router
from api.routers.tyre_intelligence import router as tyre_intelligence_router
from api.routers.admin import router as admin_router
from api.routers.tdsm import router as tdsm_router, v1_router as tdsm_v1_router
from api.routers.physical_telemetry import router as physical_telemetry_router

__all__ = [
    "circuits_router",
    "set_circuits_service",
    "seasons_router",
    "set_seasons_circuits_service",
    "stints_router",
    "set_stint_services",
    "signatures_router",
    "set_signatures_service",
    "degradation_router",
    "set_degradation_service",
    "race_intelligence_router",
    "set_race_intelligence_service",
    "strategic_warfare_router",
    "tyre_intelligence_router",
    "admin_router",
    "tdsm_router",
    "tdsm_v1_router",
    "physical_telemetry_router"
]


