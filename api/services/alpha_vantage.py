"""Alpha Vantage data service. News sentiment, fundamentals, and financials."""
import logging
import time
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class AlphaVantageService:
    BASE_URL = "https://www.alphavantage.co/query"
    # Free tier: 25 requests/day. Track to avoid wasted calls.
    DAILY_LIMIT = 25

    def __init__(self) -> None:
        self.api_key: str = settings.alpha_vantage_api_key
        self._request_count: int = 0
        self._count_reset_at: float = time.time() + 86400

    def _check_rate_limit(self) -> bool:
        """Returns True if we can make another request. Resets counter daily."""
        now = time.time()
        if now > self._count_reset_at:
            self._request_count = 0
            self._count_reset_at = now + 86400
        if self._request_count >= self.DAILY_LIMIT:
            logger.warning("Alpha Vantage daily rate limit reached (%d/%d)", self._request_count, self.DAILY_LIMIT)
            return False
        return True

    async def _get(self, params: dict[str, str]) -> Any:
        """Shared GET with rate limiting and error handling."""
        if not self._check_rate_limit():
            return None
        params["apikey"] = self.api_key
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(self.BASE_URL, params=params)
                resp.raise_for_status()
                self._request_count += 1
                data = resp.json()
                if "Error Message" in data:
                    logger.error("Alpha Vantage error: %s", data["Error Message"])
                    return None
                if "Note" in data:
                    logger.warning("Alpha Vantage rate limit note: %s", data["Note"][:100])
                    return None
                return data
        except httpx.HTTPStatusError as e:
            logger.error("Alpha Vantage HTTP %d: %s", e.response.status_code, e.response.text[:200])
            return None
        except httpx.RequestError as e:
            logger.error("Alpha Vantage request failed: %s", str(e))
            return None

    async def get_news_sentiment(self, ticker: str) -> dict:
        """Get news sentiment analysis for a ticker."""
        result = await self._get({"function": "NEWS_SENTIMENT", "tickers": ticker})
        return result if isinstance(result, dict) else {}

    async def get_overview(self, ticker: str) -> dict:
        """Get company overview: PE, EPS, market cap, sector, etc."""
        result = await self._get({"function": "OVERVIEW", "symbol": ticker})
        return result if isinstance(result, dict) else {}

    async def get_income_statement(self, ticker: str) -> dict:
        """Get annual and quarterly income statements."""
        result = await self._get({"function": "INCOME_STATEMENT", "symbol": ticker})
        return result if isinstance(result, dict) else {}

    async def get_balance_sheet(self, ticker: str) -> dict:
        """Get annual and quarterly balance sheets."""
        result = await self._get({"function": "BALANCE_SHEET", "symbol": ticker})
        return result if isinstance(result, dict) else {}
