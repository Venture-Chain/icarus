"""
Redis Streams for data pipeline.
Producers write market data, consumers process and store.
"""
import json
import logging
from datetime import datetime

import redis.asyncio as aioredis

from config import settings

log = logging.getLogger("icarus.streams")

# Stream names
STREAM_PRICES = "market:prices"
STREAM_NEWS = "market:news"
STREAM_SENTIMENT = "market:sentiment"
STREAM_FILINGS = "market:filings"
STREAM_SOCIAL_REDDIT = "social:reddit"
STREAM_SOCIAL_STOCKTWITS = "social:stocktwits"

# Consumer groups
GROUP_DATA_QUALITY = "data-quality"
GROUP_DB_WRITER = "db-writer"
GROUP_STRATEGY = "strategy-engine"

ALL_STREAMS = [
    STREAM_PRICES, STREAM_NEWS, STREAM_SENTIMENT,
    STREAM_FILINGS, STREAM_SOCIAL_REDDIT, STREAM_SOCIAL_STOCKTWITS,
]

ALL_GROUPS = [GROUP_DATA_QUALITY, GROUP_DB_WRITER, GROUP_STRATEGY]


class StreamProducer:
    """Write data into Redis Streams."""

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def publish_price(self, ticker: str, data: dict):
        await self.redis.xadd(STREAM_PRICES, {
            "ticker": ticker,
            "data": json.dumps(data),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def publish_news(self, ticker: str, articles: list):
        for article in articles:
            await self.redis.xadd(STREAM_NEWS, {
                "ticker": ticker,
                "data": json.dumps(article),
                "timestamp": datetime.utcnow().isoformat(),
            })

    async def publish_sentiment(self, ticker: str, source: str, score: dict):
        await self.redis.xadd(STREAM_SENTIMENT, {
            "ticker": ticker,
            "source": source,
            "data": json.dumps(score),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def publish_filing(self, ticker: str, filing: dict):
        await self.redis.xadd(STREAM_FILINGS, {
            "ticker": ticker,
            "data": json.dumps(filing),
            "timestamp": datetime.utcnow().isoformat(),
        })

    async def publish_social(self, stream: str, ticker: str, post: dict):
        await self.redis.xadd(stream, {
            "ticker": ticker,
            "data": json.dumps(post),
            "timestamp": datetime.utcnow().isoformat(),
        })


class StreamConsumer:
    """Read from Redis Streams using consumer groups."""

    def __init__(self, redis: aioredis.Redis, group: str, consumer_name: str):
        self.redis = redis
        self.group = group
        self.consumer_name = consumer_name

    async def ensure_groups(self):
        """Create consumer groups if they don't exist."""
        for stream in ALL_STREAMS:
            try:
                await self.redis.xgroup_create(stream, self.group, id="0", mkstream=True)
            except aioredis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

    async def read(self, streams: list[str], count: int = 10, block: int = 5000) -> list:
        """Read pending messages from streams. block is in ms."""
        stream_ids = {s: ">" for s in streams}
        try:
            messages = await self.redis.xreadgroup(
                groupname=self.group,
                consumername=self.consumer_name,
                streams=stream_ids,
                count=count,
                block=block,
            )
            return messages or []
        except aioredis.ResponseError:
            return []

    async def ack(self, stream: str, message_id: str):
        """Acknowledge a processed message."""
        await self.redis.xack(stream, self.group, message_id)


async def create_redis_connection() -> aioredis.Redis:
    """Create async Redis connection."""
    return aioredis.from_url(settings.redis_url, decode_responses=True)
