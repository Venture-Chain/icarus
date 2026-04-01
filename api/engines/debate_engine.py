"""
Debate engine: stores and retrieves structured bull/bear analysis results.
Debates are generated externally (via conversation) and submitted through the API.
Redis is primary (TTL 24h). DB write is optional for ML training history.
"""
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis

log = logging.getLogger("icarus.debate")

DEBATE_TTL_SECONDS = 86400  # 24 hours
REDIS_KEY_PREFIX = "debate:"
REDIS_INDEX_KEY = "debate:active_tickers"


@dataclass
class DebateResult:
    ticker: str
    bull_thesis: str
    bull_catalysts: list[str]
    bull_conviction: int
    bear_thesis: str
    bear_risks: list[str]
    bear_conviction: int
    judge_direction: str  # long, short, skip
    judge_conviction: int
    price_targets: dict  # {"1w": float, "1m": float, "3m": float}
    entry_price: float
    stop_price: float
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=24)
    )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["expires_at"] = self.expires_at.isoformat()
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "DebateResult":
        data = {**data}
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at


class DebateEngine:
    def __init__(self, redis: aioredis.Redis, db_pool=None):
        self._redis = redis
        self._db_pool = db_pool  # optional asyncpg pool

    def _redis_key(self, ticker: str) -> str:
        return f"{REDIS_KEY_PREFIX}{ticker.upper()}"

    async def store_debate(self, result: DebateResult) -> None:
        key = self._redis_key(result.ticker)
        payload = json.dumps(result.to_dict())
        await self._redis.setex(key, DEBATE_TTL_SECONDS, payload)
        await self._redis.sadd(REDIS_INDEX_KEY, result.ticker.upper())

        if self._db_pool:
            await self._persist_to_db(result)

    async def get_debate(self, ticker: str) -> DebateResult | None:
        raw = await self._redis.get(self._redis_key(ticker))
        if not raw:
            return None
        result = DebateResult.from_dict(json.loads(raw))
        if result.is_expired():
            await self._redis.delete(self._redis_key(ticker))
            await self._redis.srem(REDIS_INDEX_KEY, ticker.upper())
            return None
        return result

    async def get_all_debates(self) -> list[DebateResult]:
        tickers = await self._redis.smembers(REDIS_INDEX_KEY)
        results = []
        stale = []
        for ticker in tickers:
            debate = await self.get_debate(ticker)
            if debate:
                results.append(debate)
            else:
                stale.append(ticker)
        if stale:
            await self._redis.srem(REDIS_INDEX_KEY, *stale)
        return results

    async def invalidate(self, ticker: str) -> bool:
        deleted = await self._redis.delete(self._redis_key(ticker))
        await self._redis.srem(REDIS_INDEX_KEY, ticker.upper())
        return deleted > 0

    async def conviction_boost(self, ticker: str) -> float:
        """
        Returns a confidence boost in [-0.3, 0.3] for active debates.
        Positive for bullish judge direction, negative for bearish.
        Returns 0.0 if no active debate exists.
        """
        debate = await self.get_debate(ticker)
        if not debate:
            return 0.0
        conviction_pct = debate.judge_conviction / 100.0
        if debate.judge_direction == "long":
            return round(conviction_pct * 0.3, 4)
        if debate.judge_direction == "short":
            return round(-conviction_pct * 0.3, 4)
        return 0.0

    async def _persist_to_db(self, result: DebateResult) -> None:
        if not self._db_pool:
            return
        try:
            async with self._db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO debate_results (
                        ticker, bull_thesis, bull_catalysts, bull_conviction,
                        bear_thesis, bear_risks, bear_conviction,
                        judge_direction, judge_conviction, price_targets,
                        entry_price, stop_price, created_at, expires_at
                    ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
                    ON CONFLICT DO NOTHING
                    """,
                    result.ticker.upper(),
                    result.bull_thesis,
                    result.bull_catalysts,
                    result.bull_conviction,
                    result.bear_thesis,
                    result.bear_risks,
                    result.bear_conviction,
                    result.judge_direction,
                    result.judge_conviction,
                    json.dumps(result.price_targets),
                    result.entry_price,
                    result.stop_price,
                    result.created_at,
                    result.expires_at,
                )
        except Exception:
            log.exception("Failed to persist debate result for %s", result.ticker)
