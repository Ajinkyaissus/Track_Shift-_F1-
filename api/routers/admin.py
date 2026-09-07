"""
Admin & Observability Router for TrackShift.
Endpoints for cache invalidation and live metrics monitoring.
"""

from fastapi import APIRouter
from api.cache import get_cache_service

router = APIRouter(tags=["admin"])

@router.get("/metrics")
@router.get("/cache/metrics")
async def get_metrics():
    cache = get_cache_service()
    return cache.get_stats()

@router.post("/admin/cache/invalidate/stint/{stint_id}")
async def invalidate_stint_cache(stint_id: str):
    cache = get_cache_service()
    deleted = await cache.invalidate_stint(stint_id)
    return {"stint_id": stint_id, "invalidated_keys_count": deleted}

@router.post("/admin/cache/invalidate/model/{model_version}")
async def invalidate_model_cache(model_version: str):
    cache = get_cache_service()
    deleted = await cache.invalidate_model(model_version)
    return {"model_version": model_version, "invalidated_keys_count": deleted}

@router.post("/admin/cache/clear")
async def clear_entire_cache():
    cache = get_cache_service()
    await cache.memory.clear()
    if cache.is_redis_active and cache.redis.client is not None:
        try:
            await cache.redis.client.flushdb()
        except Exception:
            pass
    return {"status": "cleared"}
