"""Finnhub data service. News, sentiment, quotes, and company profiles."""
import logging
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class FinnhubService:
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self) -> None:
        self.api_key: str = settings.finnhub_api_key

    async def _get(self, endpoint: str, params: dict[str, Any] | None = None) -> Any:
        """Shared GET with error handling."""
        params = params or {}
        params["token"] = self.api_key
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{self.BASE_URL}/{endpoint}", params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Finnhub HTTP %d on %s: %s", e.response.status_code, endpoint, e.response.text[:200])
            return None
        except httpx.RequestError as e:
            logger.error("Finnhub request failed for %s: %s", endpoint, str(e))
            return None

    async def get_news(self, ticker: str, from_date: str | None = None, to_date: str | None = None) -> list[dict]:
        """Get company news articles."""
        params: dict[str, str] = {"symbol": ticker}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        result = await self._get("company-news", params)
        return result if isinstance(result, list) else []

    async def get_sentiment(self, ticker: str) -> dict:
        """Get aggregated news sentiment."""
        result = await self._get("news-sentiment", {"symbol": ticker})
        return result if isinstance(result, dict) else {}

    async def get_company_profile(self, ticker: str) -> dict:
        """Get company profile: market cap, industry, IPO date, etc."""
        result = await self._get("stock/profile2", {"symbol": ticker})
        return result if isinstance(result, dict) else {}

    async def get_quote(self, ticker: str) -> dict:
        """Get real-time price quote (current, high, low, open, previous close)."""
        result = await self._get("quote", {"symbol": ticker})
        return result if isinstance(result, dict) else {}
