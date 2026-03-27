"""
Icarus data ingestion worker.
Pulls market data from all sources on schedule, publishes to Redis Streams.
"""
import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta

import redis.asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("icarus-worker")

# Add parent path so we can import from api/
sys.path.insert(0, "/app/../api")


class IngestionWorker:
    """Coordinates data pulls from all sources."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: aioredis.Redis | None = None
        self.watchlist: list[str] = []
        self._running = True

    async def start(self):
        log.info("connecting to Redis")
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)

        # Default watchlist (will be configurable via DB later)
        self.watchlist = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD",
            "SPY", "QQQ", "IWM", "DIA",
        ]

        log.info(f"watchlist: {len(self.watchlist)} tickers")

        # Run ingestion loops concurrently
        await asyncio.gather(
            self._price_loop(),
            self._alpaca_bars_loop(),
            self._news_loop(),
            self._sentiment_loop(),
            self._social_loop(),
            self._filings_loop(),
        )

    async def _price_loop(self):
        """Pull prices every 5 minutes during market hours, hourly otherwise."""
        import yfinance as yf

        while self._running:
            try:
                log.info("pulling prices")
                for ticker in self.watchlist:
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period="5d", interval="1d")
                        if hist.empty:
                            continue
                        latest = hist.iloc[-1]
                        data = {
                            "open": float(latest["Open"]),
                            "high": float(latest["High"]),
                            "low": float(latest["Low"]),
                            "close": float(latest["Close"]),
                            "volume": int(latest["Volume"]),
                        }
                        await self.redis.xadd("market:prices", {
                            "ticker": ticker,
                            "data": json.dumps(data),
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                    except Exception as e:
                        log.warning(f"price pull failed for {ticker}: {e}")
                log.info("prices updated")
            except Exception as e:
                log.error(f"price loop error: {e}")
            await asyncio.sleep(300)  # 5 min

    async def _alpaca_bars_loop(self):
        """Pull intraday bars from Alpaca every 5 minutes. Free tier: IEX feed, 200 req/min."""
        import httpx
        import os

        api_key = os.environ.get("ALPACA_API_KEY", "")
        api_secret = os.environ.get("ALPACA_API_SECRET", "")
        if not api_key or not api_secret:
            log.warning("ALPACA_API_KEY/SECRET not set, Alpaca ingestion disabled")
            return

        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}

        while self._running:
            try:
                log.info("pulling Alpaca bars")
                async with httpx.AsyncClient(timeout=15) as client:
                    # Batch request: up to 200 symbols per call
                    symbols = ",".join(self.watchlist)
                    resp = await client.get(
                        "https://data.alpaca.markets/v2/stocks/bars",
                        params={
                            "symbols": symbols,
                            "timeframe": "5Min",
                            "limit": 1,
                            "feed": "iex",
                            "sort": "desc",
                        },
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        bars = data.get("bars", {})
                        for ticker, bar_list in bars.items():
                            if not bar_list:
                                continue
                            bar = bar_list[0]
                            await self.redis.xadd("market:prices", {
                                "ticker": ticker,
                                "source": "alpaca",
                                "data": json.dumps({
                                    "open": float(bar["o"]),
                                    "high": float(bar["h"]),
                                    "low": float(bar["l"]),
                                    "close": float(bar["c"]),
                                    "volume": int(bar["v"]),
                                    "vwap": float(bar.get("vw", 0)),
                                }),
                                "timestamp": datetime.utcnow().isoformat(),
                            })
                        log.info(f"Alpaca bars updated: {len(bars)} tickers")
                    else:
                        log.warning(f"Alpaca bars HTTP {resp.status_code}")
            except Exception as e:
                log.error(f"Alpaca bars loop error: {e}")
            await asyncio.sleep(300)  # 5 min

    async def _news_loop(self):
        """Pull news every 15 minutes."""
        import httpx
        import os

        api_key = os.environ.get("FINNHUB_API_KEY", "")
        if not api_key:
            log.warning("FINNHUB_API_KEY not set, news ingestion disabled")
            return

        while self._running:
            try:
                log.info("pulling news")
                async with httpx.AsyncClient() as client:
                    for ticker in self.watchlist[:10]:  # Rate limit: top 10
                        try:
                            today = datetime.now().strftime("%Y-%m-%d")
                            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                            resp = await client.get(
                                "https://finnhub.io/api/v1/company-news",
                                params={"symbol": ticker, "from": yesterday, "to": today, "token": api_key},
                            )
                            if resp.status_code == 200:
                                articles = resp.json()
                                for article in articles[:5]:  # Cap per ticker
                                    await self.redis.xadd("market:news", {
                                        "ticker": ticker,
                                        "data": json.dumps({
                                            "headline": article.get("headline", ""),
                                            "source": article.get("source", ""),
                                            "url": article.get("url", ""),
                                            "summary": article.get("summary", "")[:500],
                                            "datetime": article.get("datetime", 0),
                                        }),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    })
                        except Exception as e:
                            log.warning(f"news pull failed for {ticker}: {e}")
                        await asyncio.sleep(1)  # Rate limit spacing
                log.info("news updated")
            except Exception as e:
                log.error(f"news loop error: {e}")
            await asyncio.sleep(900)  # 15 min

    async def _sentiment_loop(self):
        """Pull sentiment every 30 minutes."""
        import httpx
        import os

        av_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        if not av_key:
            log.warning("ALPHA_VANTAGE_API_KEY not set, sentiment ingestion disabled")
            return

        while self._running:
            try:
                log.info("pulling sentiment")
                async with httpx.AsyncClient() as client:
                    # Alpha Vantage: 25 req/day, be conservative
                    for ticker in self.watchlist[:5]:
                        try:
                            resp = await client.get(
                                "https://www.alphavantage.co/query",
                                params={"function": "NEWS_SENTIMENT", "tickers": ticker, "apikey": av_key},
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                feed = data.get("feed", [])
                                for item in feed[:3]:
                                    sentiment = item.get("overall_sentiment_score", 0)
                                    await self.redis.xadd("market:sentiment", {
                                        "ticker": ticker,
                                        "source": "alpha_vantage",
                                        "data": json.dumps({
                                            "score": float(sentiment),
                                            "label": item.get("overall_sentiment_label", ""),
                                            "title": item.get("title", "")[:200],
                                        }),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    })
                        except Exception as e:
                            log.warning(f"sentiment pull failed for {ticker}: {e}")
                        await asyncio.sleep(2)
                log.info("sentiment updated")
            except Exception as e:
                log.error(f"sentiment loop error: {e}")
            await asyncio.sleep(1800)  # 30 min

    async def _social_loop(self):
        """Pull Reddit and StockTwits every 20 minutes."""
        import httpx

        while self._running:
            try:
                log.info("pulling social data")
                # StockTwits (no auth needed)
                async with httpx.AsyncClient() as client:
                    for ticker in self.watchlist[:10]:
                        try:
                            resp = await client.get(
                                f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                messages = data.get("messages", [])
                                bullish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
                                bearish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
                                total = bullish + bearish
                                await self.redis.xadd("social:stocktwits", {
                                    "ticker": ticker,
                                    "data": json.dumps({
                                        "bullish": bullish,
                                        "bearish": bearish,
                                        "total": total,
                                        "bull_ratio": bullish / total if total > 0 else 0.5,
                                        "message_count": len(messages),
                                    }),
                                    "timestamp": datetime.utcnow().isoformat(),
                                })
                        except Exception as e:
                            log.warning(f"stocktwits pull failed for {ticker}: {e}")
                        await asyncio.sleep(1)
                log.info("social data updated")
            except Exception as e:
                log.error(f"social loop error: {e}")
            await asyncio.sleep(1200)  # 20 min

    async def _filings_loop(self):
        """Pull SEC filings every hour."""
        import feedparser

        while self._running:
            try:
                log.info("pulling SEC filings")
                for ticker in self.watchlist[:20]:
                    try:
                        url = (
                            f"https://www.sec.gov/cgi-bin/browse-edgar"
                            f"?action=getcompany&company={ticker}&type=8-K"
                            f"&dateb=&owner=include&count=5&search_text=&action=getcompany&output=atom"
                        )
                        feed = feedparser.parse(url)
                        for entry in feed.entries[:3]:
                            await self.redis.xadd("market:filings", {
                                "ticker": ticker,
                                "data": json.dumps({
                                    "title": entry.get("title", ""),
                                    "filed": entry.get("filed", ""),
                                    "link": entry.get("link", ""),
                                    "type": "8-K",
                                }),
                                "timestamp": datetime.utcnow().isoformat(),
                            })
                    except Exception as e:
                        log.warning(f"filing pull failed for {ticker}: {e}")
                log.info("filings updated")
            except Exception as e:
                log.error(f"filings loop error: {e}")
            await asyncio.sleep(3600)  # 1 hour

    async def stop(self):
        self._running = False
        if self.redis:
            await self.redis.close()


async def main():
    import os
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")
    worker = IngestionWorker(redis_url)
    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
