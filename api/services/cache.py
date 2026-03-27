"""Redis cache layer for API responses and computed data."""
import json
import logging
from typing import Any, Callable, Awaitable

import redis.asyncio as redis

from config import settings

logger = logging.getLogger(__name__)


class CacheService:

    def __init__(self, redis_client: redis.Redis | None = None) -> None:
        self._redis: redis.Redis | None = redis_client

    async def connect(self) -> None:
        """Initialize Redis connection from settings if not injected."""
        if not self._redis:
            try:
                self._redis = redis.from_url(settings.redis_url, decode_responses=True)
                await self._redis.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning("Redis unavailable, cache disabled: %s", str(e))
                self._redis = None

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    async def get(self, key: str) -> Any:
        """Get a value from cache. Returns None on miss or error."""
        if not self._redis:
            return None
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return raw
        except Exception as e:
            logger.error("Cache get failed for %s: %s", key, str(e))
            return None

    async def set(self, key: str, value: Any, ttl: int = 3600) -> None:
        """Set a value in cache with TTL. Silently fails if Redis is unavailable."""
        if not self._redis:
            return
        try:
            serialized = json.dumps(value, default=str)
            await self._redis.set(key, serialized, ex=ttl)
        except Exception as e:
            logger.error("Cache set failed for %s: %s", key, str(e))

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable[[], Awaitable[Any]],
        ttl: int = 3600,
    ) -> Any:
        """Return cached value or call fetch_func, cache the result, and return it."""
        cached = await self.get(key)
        if cached is not None:
            return cached
        result = await fetch_func()
        if result is not None:
            await self.set(key, result, ttl)
        return result

    async def invalidate(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count of deleted keys."""
        if not self._redis:
            return 0
        try:
            deleted = 0
            async for key in self._redis.scan_iter(match=pattern, count=100):
                await self._redis.delete(key)
                deleted += 1
            return deleted
        except Exception as e:
            logger.error("Cache invalidate failed for pattern %s: %s", pattern, str(e))
            return 0

    async def delete(self, key: str) -> bool:
        """Delete a single key. Returns True if the key existed."""
        if not self._redis:
            return False
        try:
            result = await self._redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error("Cache delete failed for %s: %s", key, str(e))
            return False
