"""
Async Redis client wrapper with connection pooling, health checks,
and graceful degradation handling when Redis server is unavailable.
"""

import os
import logging
import asyncio
from typing import Optional

logger = logging.getLogger("trackshift.cache.redis")

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    aioredis = None
    REDIS_AVAILABLE = False

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

class RedisClientWrapper:
    """
    Manages an async Redis connection pool.
    Gracefully handles unavailability, timeouts, and network disconnects.
    """

    def __init__(self, url: str = REDIS_URL, connect_timeout: float = 1.0):
        self.url = url
        self.connect_timeout = connect_timeout
        self.client: Optional[object] = None
        self._is_connected: bool = False
        self._lock = asyncio.Lock()

    async def connect(self) -> bool:
        """Attempts to connect to Redis. Returns True if successful, False otherwise."""
        if not REDIS_AVAILABLE:
            logger.info("redis-py package is not available or Redis is disabled. Operating in memory-only mode.")
            self._is_connected = False
            return False

        async with self._lock:
            if self._is_connected and self.client is not None:
                return True

            try:
                client = aioredis.from_url(
                    self.url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=self.connect_timeout,
                    socket_timeout=self.connect_timeout,
                    max_connections=20
                )
                await asyncio.wait_for(client.ping(), timeout=self.connect_timeout)
                self.client = client
                self._is_connected = True
                logger.info("Successfully connected to Redis KV Cache at %s", self.url)
                return True
            except (Exception, asyncio.TimeoutError) as e:
                logger.warning("Redis not available at %s (%s). Falling back to In-Memory KV cache.", self.url, str(e))
                self.client = None
                self._is_connected = False
                return False

    async def ping(self) -> bool:
        """Pings Redis to test connection liveness."""
        if not self._is_connected or self.client is None:
            return False
        try:
            return bool(await self.client.ping())
        except Exception:
            self._is_connected = False
            return False

    async def close(self):
        """Closes the Redis connection pool."""
        if self.client is not None:
            try:
                await self.client.aclose()
            except Exception:
                pass
            self.client = None
            self._is_connected = False

    @property
    def is_connected(self) -> bool:
        return self._is_connected
