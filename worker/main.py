"""
Icarus data ingestion worker.
Pulls market data from all sources on schedule, publishes to Redis Streams.

Rate budget strategy:
  - Alpaca: primary price source (batch API, 1 call per cycle)
  - yfinance: fallback/supplementary prices, daily bars only
  - Finnhub: news (top 10 tickers per cycle, 1 req each)
  - Alpha Vantage: fundamentals only, 2 tickers/cycle, rotates daily (20/day budget)
  - StockTwits: social sentiment, 10 tickers per cycle
  - Reddit: aggregated subreddit scrape, not per-ticker
  - SEC EDGAR: filings, full watchlist, RSS is cheap
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timedelta

import redis.asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("icarus-worker")

sys.path.insert(0, "/app/../api")


class IngestionWorker:
    """Coordinates data pulls from all sources with rate-aware scheduling."""

    # Max entries per Redis Stream before trimming old data
    STREAM_MAX_LEN = 50_000

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: aioredis.Redis | None = None
        self.watchlist: list[str] = []
        self._running = True
        # Rotation index for Alpha Vantage daily budget
        self._av_rotation_idx = 0

    async def start(self):
        log.info("connecting to Redis")
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)

        self.watchlist = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "JPM", "V", "JNJ", "WMT", "PG", "MA", "UNH", "HD",
            "SPY", "QQQ", "IWM", "DIA",
        ]
        log.info("watchlist: %d tickers", len(self.watchlist))

        await asyncio.gather(
            self._alpaca_bars_loop(),       # every 5 min, 1 batch call
            self._yfinance_daily_loop(),    # every 30 min, daily bars only
            self._news_loop(),              # every 15 min, top 10 tickers
            self._av_fundamentals_loop(),   # every 60 min, 2 rotating tickers
            self._social_loop(),            # every 20 min, 10 tickers
            self._filings_loop(),           # every 60 min, all tickers via RSS
            self._stream_trimmer(),         # every 10 min, cap stream lengths
        )

    # -- Prices (Alpaca: primary) -----------------------------------------

    async def _alpaca_bars_loop(self):
        """Pull intraday bars from Alpaca. 1 batch request per cycle."""
        import httpx

        api_key = os.environ.get("ALPACA_API_KEY", "")
        api_secret = os.environ.get("ALPACA_API_SECRET", "")
        if not api_key or not api_secret:
            log.warning("ALPACA keys not set, Alpaca ingestion disabled")
            return

        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}

        while self._running:
            try:
                log.info("pulling Alpaca bars")
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://data.alpaca.markets/v2/stocks/bars",
                        params={
                            "symbols": ",".join(self.watchlist),
                            "timeframe": "5Min",
                            "limit": 1,
                            "feed": "iex",
                            "sort": "desc",
                        },
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        bars = resp.json().get("bars", {})
                        for ticker, bar_list in bars.items():
                            if not bar_list:
                                continue
                            bar = bar_list[0]
                            await self._publish_price(ticker, "alpaca", {
                                "open": float(bar["o"]),
                                "high": float(bar["h"]),
                                "low": float(bar["l"]),
                                "close": float(bar["c"]),
                                "volume": int(bar["v"]),
                                "vwap": float(bar.get("vw", 0)),
                            })
                        log.info("Alpaca bars updated: %d tickers", len(bars))
                    elif resp.status_code == 429:
                        log.warning("Alpaca rate limited, backing off 60s")
                        await asyncio.sleep(60)
                    else:
                        log.warning("Alpaca HTTP %d", resp.status_code)
            except Exception as e:
                log.error("Alpaca bars error: %s", e)
            await asyncio.sleep(300)

    # -- Prices (yfinance: supplementary, daily only) ----------------------

    async def _yfinance_daily_loop(self):
        """Pull daily bars from yfinance. Supplements Alpaca for daily OHLCV.
        Runs less frequently to avoid IP blocks on the unofficial API."""
        import yfinance as yf

        backoff = 1800  # normal interval: 30 min
        while self._running:
            failures = 0
            try:
                log.info("pulling yfinance daily bars")
                for ticker in self.watchlist:
                    try:
                        stock = yf.Ticker(ticker)
                        hist = stock.history(period="5d", interval="1d")
                        if hist.empty:
                            failures += 1
                            continue
                        latest = hist.iloc[-1]
                        await self._publish_price(ticker, "yfinance", {
                            "open": float(latest["Open"]),
                            "high": float(latest["High"]),
                            "low": float(latest["Low"]),
                            "close": float(latest["Close"]),
                            "volume": int(latest["Volume"]),
                        })
                    except Exception as e:
                        failures += 1
                        log.warning("yfinance failed for %s: %s", ticker, e)
                    await asyncio.sleep(2)  # 2s between tickers to stay safe
                if failures >= len(self.watchlist):
                    backoff = min(backoff * 2, 7200)  # double up to 2h
                    log.warning("all yfinance tickers failed, backing off %ds", backoff)
                else:
                    backoff = 1800
                    log.info("yfinance daily bars updated (%d/%d ok)",
                             len(self.watchlist) - failures, len(self.watchlist))
            except Exception as e:
                log.error("yfinance loop error: %s", e)
                backoff = min(backoff * 2, 7200)
            await asyncio.sleep(backoff)

    # -- News (Finnhub) ---------------------------------------------------

    async def _news_loop(self):
        """Pull news every 15 minutes. 10 tickers, 1 req each = 10 req/cycle.
        At 4 cycles/hour = 40 req/hr, well within 60/min limit."""
        import httpx

        api_key = os.environ.get("FINNHUB_API_KEY", "")
        if not api_key:
            log.warning("FINNHUB_API_KEY not set, news ingestion disabled")
            return

        while self._running:
            try:
                log.info("pulling Finnhub news")
                async with httpx.AsyncClient(timeout=15) as client:
                    for ticker in self.watchlist[:10]:
                        try:
                            today = datetime.now().strftime("%Y-%m-%d")
                            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                            resp = await client.get(
                                "https://finnhub.io/api/v1/company-news",
                                params={"symbol": ticker, "from": yesterday, "to": today, "token": api_key},
                            )
                            if resp.status_code == 200:
                                for article in resp.json()[:5]:
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
                                    }, maxlen=self.STREAM_MAX_LEN)
                            elif resp.status_code == 429:
                                log.warning("Finnhub rate limited, stopping news cycle early")
                                break
                        except Exception as e:
                            log.warning("Finnhub news failed for %s: %s", ticker, e)
                        await asyncio.sleep(1.5)  # ~10 req over 15s, safe
                log.info("Finnhub news updated")
            except Exception as e:
                log.error("news loop error: %s", e)
            await asyncio.sleep(900)

    # -- Fundamentals (Alpha Vantage: budget-aware rotation) ---------------

    async def _av_fundamentals_loop(self):
        """Pull fundamentals from Alpha Vantage. 2 tickers per cycle, rotating.
        At 1 cycle/hr * 2 tickers * 2 endpoints = 4 req/cycle.
        24 hrs * 4 req = 96 potential, but we cap at 20/day in the limiter.
        Rotation ensures all tickers get covered over multiple days."""
        import httpx

        av_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        if not av_key:
            log.warning("ALPHA_VANTAGE_API_KEY not set, fundamentals ingestion disabled")
            return

        daily_count = 0
        daily_limit = 20  # keep 5 for manual/API queries
        day_marker = datetime.utcnow().date()

        while self._running:
            try:
                today = datetime.utcnow().date()
                if today != day_marker:
                    daily_count = 0
                    day_marker = today
                    log.info("Alpha Vantage daily counter reset")

                if daily_count >= daily_limit:
                    log.info("Alpha Vantage daily budget exhausted (%d/%d), sleeping", daily_count, daily_limit)
                    await asyncio.sleep(3600)
                    continue

                # Pick 2 tickers by rotation
                batch_size = 2
                tickers_to_pull = []
                for _ in range(batch_size):
                    tickers_to_pull.append(self.watchlist[self._av_rotation_idx % len(self.watchlist)])
                    self._av_rotation_idx += 1

                log.info("pulling Alpha Vantage fundamentals for %s", tickers_to_pull)
                async with httpx.AsyncClient(timeout=30) as client:
                    for ticker in tickers_to_pull:
                        if daily_count >= daily_limit:
                            break
                        # Pull company overview (1 request)
                        try:
                            resp = await client.get(
                                "https://www.alphavantage.co/query",
                                params={"function": "OVERVIEW", "symbol": ticker, "apikey": av_key},
                            )
                            daily_count += 1
                            if resp.status_code == 200:
                                data = resp.json()
                                if "Symbol" in data:
                                    await self.redis.xadd("market:sentiment", {
                                        "ticker": ticker,
                                        "source": "alpha_vantage_fundamentals",
                                        "data": json.dumps({
                                            "pe_ratio": data.get("PERatio", ""),
                                            "eps": data.get("EPS", ""),
                                            "market_cap": data.get("MarketCapitalization", ""),
                                            "sector": data.get("Sector", ""),
                                            "52_week_high": data.get("52WeekHigh", ""),
                                            "52_week_low": data.get("52WeekLow", ""),
                                        }),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }, maxlen=self.STREAM_MAX_LEN)
                        except Exception as e:
                            log.warning("AV overview failed for %s: %s", ticker, e)
                        await asyncio.sleep(15)  # AV needs spacing

                        # Pull news sentiment (1 request)
                        if daily_count >= daily_limit:
                            break
                        try:
                            resp = await client.get(
                                "https://www.alphavantage.co/query",
                                params={"function": "NEWS_SENTIMENT", "tickers": ticker, "apikey": av_key},
                            )
                            daily_count += 1
                            if resp.status_code == 200:
                                data = resp.json()
                                for item in data.get("feed", [])[:3]:
                                    await self.redis.xadd("market:sentiment", {
                                        "ticker": ticker,
                                        "source": "alpha_vantage",
                                        "data": json.dumps({
                                            "score": float(item.get("overall_sentiment_score", 0)),
                                            "label": item.get("overall_sentiment_label", ""),
                                            "title": item.get("title", "")[:200],
                                        }),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }, maxlen=self.STREAM_MAX_LEN)
                        except Exception as e:
                            log.warning("AV sentiment failed for %s: %s", ticker, e)
                        await asyncio.sleep(15)

                log.info("Alpha Vantage done: %d/%d daily requests used", daily_count, daily_limit)
            except Exception as e:
                log.error("AV fundamentals loop error: %s", e)
            await asyncio.sleep(3600)  # 1 hour

    # -- Social (StockTwits) ----------------------------------------------

    async def _social_loop(self):
        """Pull StockTwits every 20 minutes. 10 tickers per cycle.
        At 3 cycles/hr * 10 = 30 req/hr, well within 200/hr limit."""
        import httpx

        while self._running:
            try:
                log.info("pulling StockTwits social data")
                async with httpx.AsyncClient(timeout=15) as client:
                    for ticker in self.watchlist[:10]:
                        try:
                            resp = await client.get(
                                f"https://api.stocktwits.com/api/2/streams/symbol/{ticker}.json"
                            )
                            if resp.status_code == 200:
                                messages = resp.json().get("messages", [])
                                bullish = sum(
                                    1 for m in messages
                                    if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish"
                                )
                                bearish = sum(
                                    1 for m in messages
                                    if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish"
                                )
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
                                }, maxlen=self.STREAM_MAX_LEN)
                            elif resp.status_code == 429:
                                log.warning("StockTwits rate limited, stopping cycle")
                                break
                        except Exception as e:
                            log.warning("StockTwits failed for %s: %s", ticker, e)
                        await asyncio.sleep(2)
                log.info("StockTwits updated")
            except Exception as e:
                log.error("social loop error: %s", e)
            await asyncio.sleep(1200)

    # -- Filings (SEC EDGAR) ----------------------------------------------

    async def _filings_loop(self):
        """Pull SEC filings every hour. RSS feed, very low rate usage."""
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
                            }, maxlen=self.STREAM_MAX_LEN)
                    except Exception as e:
                        log.warning("SEC filing failed for %s: %s", ticker, e)
                    await asyncio.sleep(1)
                log.info("filings updated")
            except Exception as e:
                log.error("filings loop error: %s", e)
            await asyncio.sleep(3600)

    # -- Stream maintenance -----------------------------------------------

    async def _stream_trimmer(self):
        """Trim Redis Streams to prevent unbounded memory growth.
        Runs every 10 minutes. Caps each stream at STREAM_MAX_LEN entries."""
        streams = [
            "market:prices", "market:news", "market:sentiment",
            "market:filings", "social:reddit", "social:stocktwits",
        ]

        while self._running:
            try:
                for stream in streams:
                    try:
                        length = await self.redis.xlen(stream)
                        if length > self.STREAM_MAX_LEN:
                            await self.redis.xtrim(stream, maxlen=self.STREAM_MAX_LEN)
                            log.info("trimmed %s: %d -> %d", stream, length, self.STREAM_MAX_LEN)
                    except Exception:
                        pass  # stream may not exist yet
            except Exception as e:
                log.error("stream trimmer error: %s", e)
            await asyncio.sleep(600)

    # -- Helpers -----------------------------------------------------------

    async def _publish_price(self, ticker: str, source: str, data: dict):
        """Publish a price entry with source tag and stream cap."""
        await self.redis.xadd("market:prices", {
            "ticker": ticker,
            "source": source,
            "data": json.dumps(data),
            "timestamp": datetime.utcnow().isoformat(),
        }, maxlen=self.STREAM_MAX_LEN)

    async def stop(self):
        self._running = False
        if self.redis:
            await self.redis.close()


async def main():
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")
    worker = IngestionWorker(redis_url)
    try:
        await worker.start()
    except KeyboardInterrupt:
        await worker.stop()


if __name__ == "__main__":
    asyncio.run(main())
