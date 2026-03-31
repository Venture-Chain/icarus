"""
News relevance monitor.
Consumes news, sentiment, and filings streams from Redis.
Generates notifications for material events affecting holdings and universe tickers.
Runs 24/7.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime

import asyncpg
import redis.asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("icarus.news-monitor")

sys.path.insert(0, "/api")


class NewsMonitor:
    """Watches news streams and generates notifications for relevant events."""

    # Tickers we care about most (IB holdings + universe)
    HIGH_PRIORITY = {"RKLB", "LUNR", "ASTS", "IONQ", "RGTI"}

    def __init__(self, redis_url: str, database_url: str):
        self.redis_url = redis_url
        self.database_url = database_url
        self.redis: aioredis.Redis | None = None
        self.db_pool = None
        self._running = True
        self.group = "news-monitor"
        self.consumer = "monitor-1"
        self._seen_headlines: set[str] = set()

    async def start(self):
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        self.db_pool = await asyncpg.create_pool(
            self.database_url.replace("postgresql+asyncpg://", "postgresql://"),
            min_size=1, max_size=3,
        )

        streams = ["market:news", "market:filings"]
        for stream in streams:
            try:
                await self.redis.xgroup_create(stream, self.group, id="0", mkstream=True)
            except aioredis.ResponseError as e:
                if "BUSYGROUP" not in str(e):
                    raise

        log.info("news monitor started")

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.group,
                    consumername=self.consumer,
                    streams={s: ">" for s in streams},
                    count=20,
                    block=5000,
                )
                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    for msg_id, msg_data in stream_messages:
                        try:
                            await self._process(stream_name, msg_data)
                            await self.redis.xack(stream_name, self.group, msg_id)
                        except Exception as e:
                            log.error("failed to process %s/%s: %s", stream_name, msg_id, e)

            except Exception as e:
                log.error("news monitor loop error: %s", e)
                await asyncio.sleep(1)

    async def _process(self, stream: str, data: dict):
        ticker = data.get("ticker", "")
        payload = json.loads(data.get("data", "{}"))

        if stream == "market:news":
            headline = payload.get("headline", "")
            if not headline or headline in self._seen_headlines:
                return
            self._seen_headlines.add(headline)
            # Cap dedup set
            if len(self._seen_headlines) > 10000:
                self._seen_headlines = set(list(self._seen_headlines)[-5000:])

            sentiment_score = payload.get("sentiment_score", 0)
            sentiment_label = payload.get("sentiment_label", "neutral")

            # Notify on high-priority tickers or strongly negative news
            is_high_priority = ticker in self.HIGH_PRIORITY
            is_strongly_negative = sentiment_label == "negative" and abs(sentiment_score) > 0.7
            is_strongly_positive = sentiment_label == "positive" and sentiment_score > 0.8

            if is_high_priority or is_strongly_negative or is_strongly_positive:
                severity = "warning" if is_strongly_negative else "info"
                if is_high_priority and is_strongly_negative:
                    severity = "critical"

                await self._notify(
                    type="news_alert",
                    title=f"[{ticker}] {headline[:200]}",
                    body=f"Sentiment: {sentiment_label} ({sentiment_score:.2f}). Source: {payload.get('source', 'unknown')}",
                    severity=severity,
                    ticker=ticker,
                    metadata={"url": payload.get("url", ""), "sentiment": sentiment_label},
                )

        elif stream == "market:filings":
            filing_type = payload.get("type", "")
            title = payload.get("title", "")

            if ticker in self.HIGH_PRIORITY:
                await self._notify(
                    type="news_alert",
                    title=f"[{ticker}] SEC Filing: {filing_type}",
                    body=title[:500],
                    severity="info",
                    ticker=ticker,
                    metadata={"filing_type": filing_type, "url": payload.get("link", "")},
                )

    async def _notify(self, type: str, title: str, body: str, severity: str, ticker: str = None, metadata: dict = None):
        """Write notification to DB and publish to Redis."""
        try:
            row = await self.db_pool.fetchrow(
                """
                INSERT INTO notifications (type, severity, title, body, metadata, ticker)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id, created_at
                """,
                type, severity, title, body, json.dumps(metadata or {}), ticker,
            )
            notification = {
                "id": row["id"],
                "type": type,
                "severity": severity,
                "title": title,
                "body": body,
                "ticker": ticker,
                "created_at": row["created_at"].isoformat(),
            }
            await self.redis.publish("icarus:notifications", json.dumps(notification))
        except Exception as e:
            log.error("notify failed: %s", e)

    async def stop(self):
        self._running = False
        if self.redis:
            await self.redis.close()
        if self.db_pool:
            await self.db_pool.close()


async def main():
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")
    database_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://icarus:icarus@timescaledb:5432/icarus")
    monitor = NewsMonitor(redis_url, database_url)
    try:
        await monitor.start()
    except KeyboardInterrupt:
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
