"""StockTwits data service. Retail trader sentiment per ticker."""
import logging
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class StockTwitsService:
    BASE_URL = "https://api.stocktwits.com/api/2"

    async def _get(self, endpoint: str) -> Any:
        """Shared GET with error handling."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{self.BASE_URL}/{endpoint}")
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("StockTwits HTTP %d on %s: %s", e.response.status_code, endpoint, e.response.text[:200])
            return None
        except httpx.RequestError as e:
            logger.error("StockTwits request failed for %s: %s", endpoint, str(e))
            return None

    async def get_sentiment(self, ticker: str) -> dict:
        """Get sentiment breakdown from recent messages for a ticker."""
        data = await self._get(f"streams/symbol/{ticker}.json")
        if not data:
            return {}

        messages = data.get("messages", [])
        bullish = 0
        bearish = 0

        for m in messages:
            sentiment = m.get("entities", {}).get("sentiment", {}).get("basic")
            if sentiment == "Bullish":
                bullish += 1
            elif sentiment == "Bearish":
                bearish += 1

        total = bullish + bearish
        return {
            "ticker": ticker,
            "bullish": bullish,
            "bearish": bearish,
            "total_scored": total,
            "bull_ratio": bullish / total if total > 0 else 0.5,
            "messages_count": len(messages),
            "latest_timestamp": self._parse_timestamp(messages[0]) if messages else None,
        }

    async def get_trending(self) -> list[dict]:
        """Get trending tickers on StockTwits."""
        data = await self._get("trending/symbols.json")
        if not data:
            return []

        symbols = data.get("symbols", [])
        return [
            {
                "ticker": s.get("symbol", ""),
                "title": s.get("title", ""),
                "watchlist_count": s.get("watchlist_count", 0),
            }
            for s in symbols
        ]

    def _parse_timestamp(self, message: dict) -> str | None:
        """Parse StockTwits message timestamp to ISO format."""
        raw = message.get("created_at")
        if not raw:
            return None
        try:
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ")
            return dt.isoformat()
        except (ValueError, TypeError):
            return raw
