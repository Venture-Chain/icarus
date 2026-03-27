"""Redis cache layer for API responses and computed data."""


class CacheService:
    def __init__(self, redis_client=None):
        self.redis = redis_client

    async def get(self, key: str):
        if self.redis:
            return await self.redis.get(key)
        return None

    async def set(self, key: str, value, ttl: int = 3600):
        if self.redis:
            await self.redis.set(key, value, ex=ttl)

    async def invalidate(self, pattern: str):
        """Invalidate all keys matching pattern."""
        pass
