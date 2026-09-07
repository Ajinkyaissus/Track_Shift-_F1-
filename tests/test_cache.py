"""
Unit and integration tests for TrackShift KV Cache subsystem.
Tests cache hit/miss, TTL expiration, invalidation, version isolation,
in-memory fallback, and single-flight stampede protection.
"""

import asyncio
import time
import pytest
from api.cache import (
    CacheKeys,
    CacheService,
    MemoryCache,
    RedisClientWrapper,
    DATA_VERSION,
    LEDGER_VERSION
)


@pytest.mark.asyncio
async def test_memory_cache_get_set_delete():
    mem = MemoryCache()
    key = "test:key:1"
    val = {"alpha": 123, "beta": "trackshift"}

    assert await mem.get(key) is None
    assert await mem.exists(key) is False

    # Set
    ok = await mem.set(key, val)
    assert ok is True
    assert await mem.exists(key) is True

    # Get
    res = await mem.get(key)
    assert res == val
    assert res["alpha"] == 123

    # Delete
    del_ok = await mem.delete(key)
    assert del_ok is True
    assert await mem.get(key) is None
    assert await mem.exists(key) is False


@pytest.mark.asyncio
async def test_memory_cache_expiration():
    mem = MemoryCache()
    key = "test:expiring:key"
    val = {"status": "temp"}

    # Set with 1 second TTL
    await mem.set(key, val, ttl=1)
    assert await mem.get(key) == val

    # Wait for expiration
    await asyncio.sleep(1.1)
    assert await mem.get(key) is None
    assert await mem.exists(key) is False


@pytest.mark.asyncio
async def test_cache_service_fallback_to_memory():
    # Force a non-existent redis connection
    bad_redis = RedisClientWrapper(url="redis://127.0.0.1:59999/9", connect_timeout=0.1)
    cache = CacheService(redis_wrapper=bad_redis)
    await cache.initialize()

    # Verify fallback state
    assert cache.is_redis_active is False
    stats = cache.get_stats()
    assert stats["tier"] == "memory_fallback"

    # Operations still succeed transparently
    test_key = CacheKeys.circuit_map("monza", DATA_VERSION)
    payload = {"circuit": "monza", "points": [1, 2, 3]}

    await cache.set(test_key, payload)
    fetched = await cache.get(test_key)
    assert fetched == payload

    assert await cache.exists(test_key) is True
    await cache.delete(test_key)
    assert await cache.exists(test_key) is False


@pytest.mark.asyncio
async def test_cache_version_isolation():
    cache = CacheService()
    await cache.initialize()

    stint_id = "2024_monza_R_VER_1"
    v3_key = CacheKeys.stint_attribution(stint_id, "v3_stage3_legacy")
    v4_key = CacheKeys.stint_attribution(stint_id, "v4_tcn_stage3_2026-09-07")

    await cache.set(v3_key, {"model": "v3", "r2": 0.05})
    await cache.set(v4_key, {"model": "v4_tcn", "r2": 0.42})

    res_v3 = await cache.get(v3_key)
    res_v4 = await cache.get(v4_key)

    assert res_v3["model"] == "v3"
    assert res_v4["model"] == "v4_tcn"
    assert v3_key != v4_key


@pytest.mark.asyncio
async def test_cache_invalidation():
    cache = CacheService()
    await cache.initialize()

    stint_id = "2024_spa_R_LEC_1"
    k1 = CacheKeys.stint_ledger(stint_id, LEDGER_VERSION)
    k2 = CacheKeys.stint_attribution(stint_id, "v4_tcn_stage3")
    k3 = CacheKeys.behavioral_embedding("v4_tcn_stage3", stint_id)
    k_other = CacheKeys.stint_ledger("2024_monza_R_VER_1", LEDGER_VERSION)

    await cache.set(k1, {"data": 1})
    await cache.set(k2, {"data": 2})
    await cache.set(k3, {"data": 3})
    await cache.set(k_other, {"data": 4})

    # Invalidate stint
    deleted = await cache.invalidate_stint(stint_id)
    assert deleted >= 3

    assert await cache.get(k1) is None
    assert await cache.get(k2) is None
    assert await cache.get(k3) is None
    # Other stint remains unaffected
    assert await cache.get(k_other) == {"data": 4}


@pytest.mark.asyncio
async def test_single_flight_stampede_protection():
    cache = CacheService()
    await cache.initialize()

    key = "test:stampede:compute"
    compute_count = 0

    async def _heavy_compute():
        nonlocal compute_count
        compute_count += 1
        await asyncio.sleep(0.05)  # Simulate 50ms DL inference
        return {"embedding": [0.1, 0.2, 0.3], "compute_id": compute_count}

    # Launch 20 concurrent requests for the same missing key
    tasks = [cache.single_flight(key, _heavy_compute) for _ in range(20)]
    results = await asyncio.gather(*tasks)

    # Exactly 1 computation must have executed!
    assert compute_count == 1
    assert len(results) == 20
    for r in results:
        assert r["embedding"] == [0.1, 0.2, 0.3]
        assert r["compute_id"] == 1
