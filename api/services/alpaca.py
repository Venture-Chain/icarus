"""Alpaca Markets data service. Historical bars, quotes, snapshots, and news."""
import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

from config import settings

logger = logging.getLogger(__name__)


class AlpacaService:
    """Alpaca Data API v2 client. Free tier: 200 req/min, IEX real-time."""

    DATA_URL = "https://data.alpaca.markets/v2"
    NEWS_URL = "https://data.alpaca.markets/v1beta1"

    def __init__(self) -> None:
        self.api_key: str = settings.alpaca_api_key
        self.api_secret: str = settings.alpaca_api_secret
        self._headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.api_secret,
        }

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> Any:
        params = params or {}
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url, params=params, headers=self._headers)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("Alpaca HTTP %d: %s", e.response.status_code, e.response.text[:200])
            return None
        except httpx.RequestError as e:
            logger.error("Alpaca request failed: %s", str(e))
            return None

    async def get_bars(
        self,
        ticker: str,
        timeframe: str = "1Day",
        start: str | None = None,
        end: str | None = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Get historical OHLCV bars.

        timeframe: 1Min, 5Min, 15Min, 30Min, 1Hour, 1Day, 1Week, 1Month
        Free tier uses IEX exchange data.
        """
        if not start:
            start = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%dT00:00:00Z")
        params: dict[str, Any] = {
            "timeframe": timeframe,
            "start": start,
            "limit": limit,
            "feed": "iex",
            "sort": "asc",
        }
        if end:
            params["end"] = end

        all_bars: list[dict] = []
        next_token: str | None = None

        while True:
            if next_token:
                params["page_token"] = next_token
            result = await self._get(f"{self.DATA_URL}/stocks/{ticker}/bars", params)
            if not result:
                break
            bars = result.get("bars") or []
            for bar in bars:
                all_bars.append({
                    "timestamp": bar["t"],
                    "open": float(bar["o"]),
                    "high": float(bar["h"]),
                    "low": float(bar["l"]),
                    "close": float(bar["c"]),
                    "volume": int(bar["v"]),
                    "vwap": float(bar.get("vw", 0)),
                    "trade_count": int(bar.get("n", 0)),
                })
            next_token = result.get("next_page_token")
            if not next_token or len(all_bars) >= limit:
                break

        return all_bars

    async def get_latest_quote(self, ticker: str) -> dict | None:
        """Get latest bid/ask quote (IEX feed)."""
        result = await self._get(
            f"{self.DATA_URL}/stocks/{ticker}/quotes/latest",
            {"feed": "iex"},
        )
        if not result or "quote" not in result:
            return None
        q = result["quote"]
        return {
            "bid": float(q.get("bp", 0)),
            "ask": float(q.get("ap", 0)),
            "bid_size": int(q.get("bs", 0)),
            "ask_size": int(q.get("as", 0)),
            "timestamp": q.get("t", ""),
        }

    async def get_snapshot(self, ticker: str) -> dict | None:
        """Get current snapshot: latest trade, quote, minute bar, daily bar."""
        result = await self._get(
            f"{self.DATA_URL}/stocks/{ticker}/snapshot",
            {"feed": "iex"},
        )
        if not result:
            return None
        snapshot: dict[str, Any] = {}
        if "latestTrade" in result:
            t = result["latestTrade"]
            snapshot["latest_trade"] = {"price": float(t["p"]), "size": int(t["s"]), "timestamp": t["t"]}
        if "latestQuote" in result:
            q = result["latestQuote"]
            snapshot["latest_quote"] = {"bid": float(q["bp"]), "ask": float(q["ap"])}
        if "dailyBar" in result:
            d = result["dailyBar"]
            snapshot["daily_bar"] = {
                "open": float(d["o"]), "high": float(d["h"]),
                "low": float(d["l"]), "close": float(d["c"]),
                "volume": int(d["v"]),
            }
        return snapshot

    async def get_multi_bars(
        self,
        tickers: list[str],
        timeframe: str = "1Day",
        start: str | None = None,
        limit: int = 100,
    ) -> dict[str, list[dict]]:
        """Get bars for multiple symbols in one request."""
        if not start:
            start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00Z")
        result = await self._get(
            f"{self.DATA_URL}/stocks/bars",
            {
                "symbols": ",".join(tickers),
                "timeframe": timeframe,
                "start": start,
                "limit": limit,
                "feed": "iex",
            },
        )
        if not result or "bars" not in result:
            return {}
        out: dict[str, list[dict]] = {}
        for sym, bars in result["bars"].items():
            out[sym] = [
                {
                    "timestamp": b["t"],
                    "open": float(b["o"]),
                    "high": float(b["h"]),
                    "low": float(b["l"]),
                    "close": float(b["c"]),
                    "volume": int(b["v"]),
                    "vwap": float(b.get("vw", 0)),
                }
                for b in bars
            ]
        return out

    async def get_news(
        self,
        tickers: list[str] | None = None,
        start: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Get market news. Can filter by symbols."""
        params: dict[str, Any] = {"limit": limit, "sort": "desc"}
        if tickers:
            params["symbols"] = ",".join(tickers)
        if start:
            params["start"] = start
        result = await self._get(f"{self.NEWS_URL}/news", params)
        if not result or "news" not in result:
            return []
        return [
            {
                "headline": article.get("headline", ""),
                "source": article.get("source", ""),
                "url": article.get("url", ""),
                "summary": article.get("summary", "")[:500],
                "symbols": article.get("symbols", []),
                "created_at": article.get("created_at", ""),
            }
            for article in result["news"]
        ]
