"""Notification service. Writes to DB and publishes to Redis for WebSocket delivery."""
import json
import logging
from datetime import datetime

log = logging.getLogger("icarus.notifier")


class Notifier:
    """Create notifications and publish them for real-time delivery."""

    TYPES = {"news_alert", "portfolio_alert", "stop_triggered", "risk_warning", "smart_money", "system"}
    SEVERITIES = {"info", "warning", "critical"}

    def __init__(self, db_pool, redis):
        self.db_pool = db_pool
        self.redis = redis

    async def notify(
        self,
        type: str,
        title: str,
        body: str = "",
        severity: str = "info",
        ticker: str = None,
        metadata: dict = None,
    ) -> int:
        """Create a notification, persist to DB, publish to Redis."""
        if type not in self.TYPES:
            log.warning("unknown notification type: %s", type)
        if severity not in self.SEVERITIES:
            severity = "info"

        row = await self.db_pool.fetchrow(
            """
            INSERT INTO notifications (type, severity, title, body, metadata, ticker)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, created_at
            """,
            type, severity, title, body,
            json.dumps(metadata or {}), ticker,
        )

        notification = {
            "id": row["id"],
            "type": type,
            "severity": severity,
            "title": title,
            "body": body,
            "ticker": ticker,
            "metadata": metadata or {},
            "created_at": row["created_at"].isoformat(),
        }

        # Publish to Redis for WebSocket clients
        await self.redis.publish("icarus:notifications", json.dumps(notification))

        if severity == "critical":
            log.warning("CRITICAL notification: %s - %s", title, body)

        return row["id"]
