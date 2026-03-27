"""
Centralized rate limiter for all external data sources.

Each source has explicit limits. The limiter tracks usage and blocks calls
that would exceed the budget. Counters are stored in Redis so they survive
worker restarts and are shared across instances.
"""
import asyncio
import logging
import time
from dataclasses import dataclass

import redis.asyncio as aioredis

log = logging.getLogger("icarus.rate_limiter")


@dataclass
class SourceLimits:
    """Rate limits for a single data source."""
    name: str
    per_minute: int = 0      # 0 = no per-minute limit
    per_hour: int = 0        # 0 = no per-hour limit
    per_day: int = 0         # 0 = no per-day limit
    min_interval_sec: float = 0.0  # minimum seconds between requests


# Documented free-tier limits with safety margins (80% of actual)
SOURCE_LIMITS: dict[str, SourceLimits] = {
    "alpaca": SourceLimits(
        name="alpaca",
        per_minute=150,       # actual: 200/min
        min_interval_sec=0.3,
    ),
    "finnhub": SourceLimits(
        name="finnhub",
        per_minute=45,        # actual: 60/min
        min_interval_sec=1.0,
    ),
    "alpha_vantage": SourceLimits(
        name="alpha_vantage",
        per_day=20,           # actual: 25/day, keep 5 for manual queries
        min_interval_sec=15.0,
    ),
    "stocktwits": SourceLimits(
        name="stocktwits",
        per_hour=150,         # actual: 200/hr
        min_interval_sec=2.0,
    ),
    "sec_edgar": SourceLimits(
        name="sec_edgar",
        per_minute=8,         # actual: 10/sec, but we self-throttle much lower
        min_interval_sec=1.0,
    ),
    "reddit": SourceLimits(
        name="reddit",
        per_minute=45,        # actual: 60/min
        min_interval_sec=1.0,
    ),
    "yfinance": SourceLimits(
        name="yfinance",
        per_minute=30,        # unofficial, be conservative
        per_hour=500,
        min_interval_sec=2.0,
    ),
}


class RateLimiter:
    """Token-bucket rate limiter backed by Redis counters."""

    REDIS_PREFIX = "icarus:ratelimit"

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis
        self._last_request: dict[str, float] = {}

    def _minute_key(self, source: str) -> str:
        minute = int(time.time() / 60)
        return f"{self.REDIS_PREFIX}:{source}:min:{minute}"

    def _hour_key(self, source: str) -> str:
        hour = int(time.time() / 3600)
        return f"{self.REDIS_PREFIX}:{source}:hr:{hour}"

    def _day_key(self, source: str) -> str:
        day = int(time.time() / 86400)
        return f"{self.REDIS_PREFIX}:{source}:day:{day}"

    async def acquire(self, source: str) -> bool:
        """Try to acquire a request slot. Returns True if allowed, False if throttled."""
        limits = SOURCE_LIMITS.get(source)
        if not limits:
            return True

        # Check minimum interval
        now = time.time()
        last = self._last_request.get(source, 0)
        if limits.min_interval_sec > 0 and (now - last) < limits.min_interval_sec:
            wait = limits.min_interval_sec - (now - last)
            log.debug("%s: throttling %.1fs (min interval)", source, wait)
            await asyncio.sleep(wait)

        # Check per-minute limit
        if limits.per_minute > 0:
            key = self._minute_key(source)
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 120)  # 2 min TTL for safety
            if count > limits.per_minute:
                log.warning("%s: per-minute limit reached (%d/%d)", source, count, limits.per_minute)
                await self.redis.decr(key)
                return False

        # Check per-hour limit
        if limits.per_hour > 0:
            key = self._hour_key(source)
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 7200)
            if count > limits.per_hour:
                log.warning("%s: per-hour limit reached (%d/%d)", source, count, limits.per_hour)
                await self.redis.decr(key)
                return False

        # Check per-day limit
        if limits.per_day > 0:
            key = self._day_key(source)
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, 172800)
            if count > limits.per_day:
                log.warning("%s: daily limit reached (%d/%d)", source, count, limits.per_day)
                await self.redis.decr(key)
                return False

        self._last_request[source] = time.time()
        return True

    async def wait_and_acquire(self, source: str, max_wait: float = 60.0) -> bool:
        """Wait up to max_wait seconds for a slot. Returns False if timed out."""
        deadline = time.time() + max_wait
        while time.time() < deadline:
            if await self.acquire(source):
                return True
            await asyncio.sleep(2.0)
        log.warning("%s: timed out waiting for rate limit slot", source)
        return False

    async def remaining(self, source: str) -> dict:
        """Get remaining quota for a source. Useful for scheduling decisions."""
        limits = SOURCE_LIMITS.get(source)
        if not limits:
            return {"source": source, "unlimited": True}

        result: dict = {"source": source}

        if limits.per_minute > 0:
            count = int(await self.redis.get(self._minute_key(source)) or 0)
            result["minute"] = {"used": count, "limit": limits.per_minute, "remaining": limits.per_minute - count}

        if limits.per_hour > 0:
            count = int(await self.redis.get(self._hour_key(source)) or 0)
            result["hour"] = {"used": count, "limit": limits.per_hour, "remaining": limits.per_hour - count}

        if limits.per_day > 0:
            count = int(await self.redis.get(self._day_key(source)) or 0)
            result["day"] = {"used": count, "limit": limits.per_day, "remaining": limits.per_day - count}

        return result

    async def remaining_all(self) -> list[dict]:
        """Get remaining quota for all sources."""
        return [await self.remaining(source) for source in SOURCE_LIMITS]
