"""
Database writer consumer.
Reads from Redis Streams and persists to TimescaleDB.
"""
import asyncio
import json
import logging
from datetime import datetime

import redis.asyncio as aioredis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

log = logging.getLogger("icarus.db-writer")


class DBWriter:
    """Consumes Redis Streams and writes to TimescaleDB."""

    def __init__(self, redis_url: str, database_url: str):
        self.redis_url = redis_url
        self.database_url = database_url
        self.redis: aioredis.Redis | None = None
        self.engine = None
        self._running = True
        self.group = "db-writer"
        self.consumer = "writer-1"

    async def start(self):
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        self.engine = create_async_engine(self.database_url)

        # Ensure consumer groups exist
        streams = [
            "market:prices", "market:news", "market:sentiment",
            "market:filings", "social:reddit", "social:stocktwits",
        ]
        for stream in streams:
            try:
                await self.redis.xgroup_create(stream, self.group, id="0", mkstream=True)
            except aioredis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

        log.info("db-writer started")

        while self._running:
            try:
                stream_ids = {s: ">" for s in streams}
                messages = await self.redis.xreadgroup(
                    groupname=self.group,
                    consumername=self.consumer,
                    streams=stream_ids,
                    count=50,
                    block=5000,
                )
                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for msg_id, msg_data in stream_messages:
                        try:
                            await self._process_message(stream_name, msg_data)
                            await self.redis.xack(stream_name, self.group, msg_id)
                        except Exception as e:
                            log.error(f"failed to process {stream_name}/{msg_id}: {e}")

            except Exception as e:
                log.error(f"db-writer loop error: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, stream: str, data: dict):
        ticker = data.get("ticker", "")
        payload = json.loads(data.get("data", "{}"))
        timestamp = data.get("timestamp", datetime.utcnow().isoformat())

        async with self.engine.begin() as conn:
            if stream == "market:prices":
                await conn.execute(text("""
                    INSERT INTO market_data (time, ticker, open, high, low, close, volume, source)
                    VALUES (:time, :ticker, :open, :high, :low, :close, :volume, :source)
                    ON CONFLICT (time, ticker) DO UPDATE SET
                        close = EXCLUDED.close, volume = EXCLUDED.volume
                """), {
                    "time": timestamp, "ticker": ticker,
                    "open": payload.get("open"), "high": payload.get("high"),
                    "low": payload.get("low"), "close": payload.get("close"),
                    "volume": payload.get("volume"), "source": "yfinance",
                })

            elif stream == "market:news":
                await conn.execute(text("""
                    INSERT INTO sentiment_scores (time, ticker, source, score, magnitude, raw_text, metadata)
                    VALUES (:time, :ticker, :source, :score, :magnitude, :raw_text, :metadata)
                    ON CONFLICT (time, ticker, source) DO NOTHING
                """), {
                    "time": timestamp, "ticker": ticker, "source": "finnhub",
                    "score": 0, "magnitude": 0,
                    "raw_text": payload.get("headline", ""),
                    "metadata": json.dumps(payload),
                })

            elif stream == "market:sentiment":
                await conn.execute(text("""
                    INSERT INTO sentiment_scores (time, ticker, source, score, magnitude, raw_text, metadata)
                    VALUES (:time, :ticker, :source, :score, :magnitude, :raw_text, :metadata)
                    ON CONFLICT (time, ticker, source) DO NOTHING
                """), {
                    "time": timestamp, "ticker": ticker,
                    "source": payload.get("source", data.get("source", "unknown")),
                    "score": payload.get("score", 0),
                    "magnitude": 0,
                    "raw_text": payload.get("title", ""),
                    "metadata": json.dumps(payload),
                })

            elif stream == "market:filings":
                await conn.execute(text("""
                    INSERT INTO filings (ticker, filing_type, filing_date, url, description, metadata)
                    VALUES (:ticker, :type, :date, :url, :desc, :metadata)
                """), {
                    "ticker": ticker,
                    "type": payload.get("type", "8-K"),
                    "date": payload.get("filed", timestamp),
                    "url": payload.get("link", ""),
                    "desc": payload.get("title", ""),
                    "metadata": json.dumps(payload),
                })

            elif stream in ("social:reddit", "social:stocktwits"):
                source = "reddit" if "reddit" in stream else "stocktwits"
                await conn.execute(text("""
                    INSERT INTO social_posts (time, ticker, source, author, content, score, engagement)
                    VALUES (:time, :ticker, :source, :author, :content, :score, :engagement)
                    ON CONFLICT DO NOTHING
                """), {
                    "time": timestamp, "ticker": ticker, "source": source,
                    "author": payload.get("author", ""),
                    "content": json.dumps(payload)[:1000],
                    "score": payload.get("score", payload.get("bull_ratio", 0)),
                    "engagement": json.dumps(payload),
                })

    async def stop(self):
        self._running = False
        if self.redis:
            await self.redis.close()
        if self.engine:
            await self.engine.dispose()
