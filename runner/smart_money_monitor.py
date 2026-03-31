"""
Smart money monitor.
Consumes the market:smart_money Redis Stream and generates notifications
for dark pool anomalies, congressional trades, and high-conviction setups.
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
log = logging.getLogger("icarus.smart-money-monitor")

sys.path.insert(0, "/api")


class SmartMoneyMonitor:
    """Watches smart money data and generates alerts for significant activity."""

    UNIVERSE = {"RKLB", "LUNR", "ASTS", "IONQ", "RGTI"}

    def __init__(self, redis_url: str, database_url: str):
        self.redis_url = redis_url
        self.database_url = database_url
        self.redis: aioredis.Redis | None = None
        self.db_pool = None
        self._running = True
        self.group = "smart-money-monitor"
        self.consumer = "monitor-1"

    async def start(self):
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        self.db_pool = await asyncpg.create_pool(
            self.database_url.replace("postgresql+asyncpg://", "postgresql://"),
            min_size=1, max_size=3,
        )

        stream = "market:smart_money"
        try:
            await self.redis.xgroup_create(stream, self.group, id="0", mkstream=True)
        except aioredis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        log.info("smart money monitor started")

        while self._running:
            try:
                messages = await self.redis.xreadgroup(
                    groupname=self.group,
                    consumername=self.consumer,
                    streams={stream: ">"},
                    count=20,
                    block=5000,
                )
                if not messages:
                    continue

                for _, stream_messages in messages:
                    for msg_id, msg_data in stream_messages:
                        try:
                            await self._process(msg_data)
                            await self.redis.xack(stream, self.group, msg_id)
                        except Exception as e:
                            log.error("failed to process %s: %s", msg_id, e)

            except Exception as e:
                log.error("smart money monitor error: %s", e)
                await asyncio.sleep(1)

    async def _process(self, data: dict):
        sm_type = data.get("type", "")
        ticker = data.get("ticker", "")
        payload = json.loads(data.get("data", "{}"))

        if sm_type == "dark_pool":
            await self._handle_dark_pool(ticker, payload)
        elif sm_type == "congressional":
            await self._handle_congressional(ticker, payload)
        elif sm_type == "short_interest":
            await self._handle_short_interest(ticker, payload)

        # Run confluence check after any smart money event on universe tickers
        if ticker in self.UNIVERSE:
            await self._check_confluence(ticker)

    async def _handle_dark_pool(self, ticker: str, payload: dict):
        """Alert on dark pool Z-score anomalies."""
        # We need the Z-score from the DB after it's been computed
        # For now, alert on any dark pool data for universe tickers
        volume = payload.get("share_volume", 0)
        if ticker in self.UNIVERSE and volume > 0:
            await self._notify(
                type="smart_money",
                title=f"[{ticker}] Dark pool activity detected",
                body=f"Volume: {volume:,} shares at {payload.get('ats_name', 'unknown ATS')}",
                severity="info",
                ticker=ticker,
                metadata={"source": "dark_pool", **payload},
            )

    async def _handle_congressional(self, ticker: str, payload: dict):
        """Alert on congressional trades."""
        member = payload.get("congress_member", "Unknown")
        direction = payload.get("direction", "unknown")
        amount = payload.get("amount", "")

        severity = "warning" if ticker in self.UNIVERSE else "info"

        await self._notify(
            type="smart_money",
            title=f"[{ticker}] Congress {direction}: {member}",
            body=f"Amount: {amount}. Date: {payload.get('trade_date', 'unknown')}",
            severity=severity,
            ticker=ticker,
            metadata={"source": "congressional", **payload},
        )

    async def _handle_short_interest(self, ticker: str, payload: dict):
        """Alert on significant short interest changes."""
        change = payload.get("change_pct", 0)
        if not change:
            return

        # Only alert on significant moves
        if abs(change) < 5:
            return

        direction = "declining" if change < 0 else "increasing"
        severity = "warning" if ticker in self.UNIVERSE else "info"

        await self._notify(
            type="smart_money",
            title=f"[{ticker}] Short interest {direction} {abs(change):.1f}%",
            body=f"Float short: {payload.get('short_pct_float', 0):.1f}%, Days to cover: {payload.get('days_to_cover', 0):.1f}",
            severity=severity,
            ticker=ticker,
            metadata={"source": "short_interest", **payload},
        )

    async def _check_confluence(self, ticker: str):
        """Run confluence scoring and alert on high-conviction setups."""
        try:
            from engines.confluence_engine import ConfluenceEngine
            engine = ConfluenceEngine()
            score = await engine.score(ticker, self.db_pool)

            if score.conviction >= 70:
                await self._notify(
                    type="smart_money",
                    title=f"[{ticker}] High conviction {score.direction} setup ({score.conviction}/100)",
                    body=score.explanation,
                    severity="critical",
                    ticker=ticker,
                    metadata={
                        "source": "confluence",
                        "conviction": score.conviction,
                        "direction": score.direction,
                        "signals": [
                            {"source": s.source, "direction": s.direction, "detail": s.detail}
                            for s in score.signals
                        ],
                    },
                )
        except Exception as e:
            log.error("confluence check failed for %s: %s", ticker, e)

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
    monitor = SmartMoneyMonitor(redis_url, database_url)
    try:
        await monitor.start()
    except KeyboardInterrupt:
        await monitor.stop()


if __name__ == "__main__":
    asyncio.run(main())
