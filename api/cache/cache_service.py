"""
Unified KV Cache Service for TrackShift.
Provides transparent cache-first serving over Redis (distributed) with automatic
In-Memory fallback, async single-flight stampede protection, and granular invalidation.
"""

import json
import time
import logging
import asyncio
from typing import Any, Callable, Dict, Optional, Tuple, Union
import numpy as np

from api.cache.redis_client import RedisClientWrapper

logger = logging.getLogger("trackshift.cache.service")


class CustomJSONEncoder(json.JSONEncoder):
    """Encodes NumPy types, pandas types, and floats safely."""
    def default(self, obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, (np.floating, np.float32, np.float64)):
            return float(obj)
        if isinstance(obj, (np.integer, np.int32, np.int64)):
            return int(obj)
        if isinstance(obj, (np.bool_, bool)):
            return bool(obj)
        return super().default(obj)


def serialize_payload(value: Any) -> str:
    """Serializes analytical payloads to JSON safely."""
    return json.dumps(value, cls=CustomJSONEncoder)


def deserialize_payload(payload_str: str) -> Any:
    """Deserializes JSON payloads safely without pickle."""
    return json.loads(payload_str)


class MemoryCache:
    """
    In-memory fallback cache with TTL expiration and max-entries eviction.
    Thread-safe and async-compatible.
    """

    def __init__(self, max_entries: int = 5000):
        self._store: Dict[str, Tuple[Any, Optional[float]]] = {}
        self.max_entries = max_entries
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        now = time.time()
        async with self._lock:
            if key not in self._store:
                return None
            val, expires_at = self._store[key]
            if expires_at is not None and now > expires_at:
                del self._store[key]
                return None
            return val

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        now = time.time()
        expires_at = (now + ttl) if ttl is not None else None
        async with self._lock:
            if len(self._store) >= self.max_entries and key not in self._store:
                # Evict oldest 10%
                keys_to_remove = list(self._store.keys())[: max(1, self.max_entries // 10)]
                for k in keys_to_remove:
                    self._store.pop(k, None)
            self._store[key] = (value, expires_at)
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        now = time.time()
        async with self._lock:
            if key not in self._store:
                return False
            _, expires_at = self._store[key]
            if expires_at is not None and now > expires_at:
                del self._store[key]
                return False
            return True

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidates keys matching a wildcard pattern."""
        import fnmatch
        count = 0
        async with self._lock:
            keys = list(self._store.keys())
            for k in keys:
                if fnmatch.fnmatch(k, pattern) or pattern.replace("*", "") in k:
                    del self._store[k]
                    count += 1
        return count

    async def clear(self):
        async with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


class CacheService:
    """
    High-level cache service supporting:
    - Redis distributed KV cache as primary tier
    - MemoryCache as development / disconnection fallback tier
    - Single-flight stampede protection for concurrent cache-miss bursts
    - Metric tracking for cache hits, misses, and latencies
    """

    def __init__(self, redis_wrapper: Optional[RedisClientWrapper] = None):
        self.redis = redis_wrapper or RedisClientWrapper()
        self.memory = MemoryCache()
        self._flight_locks: Dict[str, asyncio.Lock] = {}
        self._flight_table_lock = asyncio.Lock()
        
        # Metrics
        self.hits_total = 0
        self.misses_total = 0
        self.sets_total = 0
        self.stampede_saves_total = 0
        self.inferences_total = 0
        self.total_inference_time_ms = 0.0

    async def initialize(self):
        """Initializes backend connection."""
        await self.redis.connect()

    async def close(self):
        await self.redis.close()

    @property
    def is_redis_active(self) -> bool:
        return self.redis.is_connected

    async def get(self, key: str) -> Optional[Any]:
        """Fetches from cache (Redis if available, else Memory)."""
        start_t = time.perf_counter()
        result = None

        if self.redis.is_connected and self.redis.client is not None:
            try:
                raw = await self.redis.client.get(key)
                if raw is not None:
                    result = deserialize_payload(raw)
            except Exception as e:
                logger.debug("Redis get error for key %s: %s. Falling back to memory.", key, e)
                result = await self.memory.get(key)
        else:
            result = await self.memory.get(key)

        if result is not None:
            self.hits_total += 1
        else:
            self.misses_total += 1

        return result

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Stores in cache (both Redis and Memory cache for robust fallback)."""
        self.sets_total += 1
        val_str = serialize_payload(value)
        mem_ok = await self.memory.set(key, value, ttl=ttl)

        if self.redis.is_connected and self.redis.client is not None:
            try:
                if ttl is not None:
                    await self.redis.client.setex(key, ttl, val_str)
                else:
                    await self.redis.client.set(key, val_str)
                return True
            except Exception as e:
                logger.debug("Redis set error for key %s: %s", key, e)
                return mem_ok
        return mem_ok

    async def delete(self, key: str) -> bool:
        """Deletes a key from all tiers."""
        mem_ok = await self.memory.delete(key)
        if self.redis.is_connected and self.redis.client is not None:
            try:
                await self.redis.client.delete(key)
                return True
            except Exception:
                pass
        return mem_ok

    async def exists(self, key: str) -> bool:
        """Checks if key exists and is non-expired."""
        if self.redis.is_connected and self.redis.client is not None:
            try:
                return bool(await self.redis.client.exists(key))
            except Exception:
                pass
        return await self.memory.exists(key)

    async def single_flight(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[int] = None,
        attach_metadata: bool = True
    ) -> Any:
        """
        Executes single-flight compute with async stampede protection.
        If 50 concurrent requests arrive for the same missing key, only 1 triggers
        the computation while the other 49 wait and receive the cached result.
        """
        # 1. Fast path: check cache first
        cached = await self.get(key)
        if cached is not None:
            if attach_metadata and isinstance(cached, dict):
                # Ensure cache hit flag is marked true
                if "cache" in cached and isinstance(cached["cache"], dict):
                    cached["cache"]["hit"] = True
                else:
                    cached["cache"] = {"hit": True}
            return cached

        # 2. Acquire or create the lock for this specific key
        async with self._flight_table_lock:
            if key not in self._flight_locks:
                self._flight_locks[key] = asyncio.Lock()
            key_lock = self._flight_locks[key]

        # 3. Synchronize under the key-specific lock
        async with key_lock:
            # Double-check if another flight just populated the cache
            cached_after_wait = await self.get(key)
            if cached_after_wait is not None:
                self.stampede_saves_total += 1
                if attach_metadata and isinstance(cached_after_wait, dict):
                    if "cache" in cached_after_wait and isinstance(cached_after_wait["cache"], dict):
                        cached_after_wait["cache"]["hit"] = True
                    else:
                        cached_after_wait["cache"] = {"hit": True}
                return cached_after_wait

            # 4. Compute result
            t0 = time.perf_counter()
            self.inferences_total += 1
            if asyncio.iscoroutinefunction(compute_fn):
                result = await compute_fn()
            else:
                result = compute_fn()
            inference_dur_ms = (time.perf_counter() - t0) * 1000.0
            self.total_inference_time_ms += inference_dur_ms

            # 5. Store in cache
            if attach_metadata and isinstance(result, dict):
                result["cache"] = {
                    "hit": False,
                    "compute_latency_ms": round(inference_dur_ms, 2)
                }

            await self.set(key, result, ttl=ttl)

        # 6. Cleanup flight lock if no longer waiting
        async with self._flight_table_lock:
            if key in self._flight_locks and not self._flight_locks[key].locked():
                self._flight_locks.pop(key, None)

        return result

    async def invalidate_stint(self, stint_id: str) -> int:
        """Invalidates all cached data associated with a stint."""
        pattern = f"*{stint_id}*"
        return await self.invalidate_pattern(pattern)

    async def invalidate_model(self, model_version: str) -> int:
        """Invalidates all cached data associated with a model version."""
        pattern = f"*{model_version}*"
        return await self.invalidate_pattern(pattern)

    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidates keys matching a pattern across Redis and Memory."""
        mem_deleted = await self.memory.invalidate_pattern(pattern)
        redis_deleted = 0
        if self.redis.is_connected and self.redis.client is not None:
            try:
                keys = []
                async for k in self.redis.client.scan_iter(match=pattern):
                    keys.append(k)
                if keys:
                    redis_deleted = await self.redis.client.delete(*keys)
            except Exception as e:
                logger.warning("Error invalidating pattern %s in Redis: %s", pattern, e)
        return max(mem_deleted, redis_deleted)

    def get_stats(self) -> Dict[str, Any]:
        """Returns cache telemetry and hit rate statistics."""
        total_requests = self.hits_total + self.misses_total
        hit_rate = (self.hits_total / total_requests) if total_requests > 0 else 0.0
        avg_infer_latency = (self.total_inference_time_ms / self.inferences_total) if self.inferences_total > 0 else 0.0

        return {
            "tier": "redis" if self.redis.is_connected else "memory_fallback",
            "redis_connected": self.redis.is_connected,
            "memory_entries": self.memory.size,
            "cache_hits_total": self.hits_total,
            "cache_misses_total": self.misses_total,
            "cache_hit_rate": round(hit_rate, 4),
            "cache_sets_total": self.sets_total,
            "stampede_preventions": self.stampede_saves_total,
            "model_inferences_total": self.inferences_total,
            "avg_inference_latency_ms": round(avg_infer_latency, 2)
        }


# Global singleton cache service
_global_cache_service: Optional[CacheService] = None

def get_cache_service() -> CacheService:
    global _global_cache_service
    if _global_cache_service is None:
        _global_cache_service = CacheService()
    return _global_cache_service
