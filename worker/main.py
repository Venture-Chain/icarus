"""
Icarus data ingestion worker.
Pulls market data from all sources on schedule, publishes to Redis Streams.

Rate budget strategy:
  - Alpaca 5min: primary price source for broad watchlist (1 batch per cycle)
  - Alpaca 1min: universe tickers only, every 1 min during market hours
  - yfinance: fallback/supplementary prices, daily bars only
  - Finnhub: news (top tickers per cycle, 1 req each), every 5 min
  - Alpha Vantage: fundamentals only, 2 tickers/cycle, rotates daily
  - StockTwits: social sentiment, 10 tickers per cycle
  - Reddit: aggregated subreddit scrape, not per-ticker
  - SEC EDGAR: filings + Form 4, full watchlist, RSS
  - FINRA ATS: dark pool weekly CSV download (Saturday)
  - Quiver Quant: congressional trades + short interest, daily
  - Finnhub: economic calendar, daily
  - FinBERT: GPU sentiment scoring on incoming news (inline)
"""
import asyncio
import csv
import io
import json
import logging
import os
import sys
from datetime import datetime, timedelta, date, time as dtime
from zoneinfo import ZoneInfo

import redis.asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("icarus-worker")

sys.path.insert(0, "/app/../api")

ET = ZoneInfo("America/New_York")


def is_market_hours() -> bool:
    """Check if US market is open (9:30-16:00 ET, weekdays)."""
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    market_open = dtime(9, 30)
    market_close = dtime(16, 0)
    return market_open <= now.time() <= market_close


class IngestionWorker:
    """Coordinates data pulls from all sources with rate-aware scheduling."""

    STREAM_MAX_LEN = 50_000

    # Universe: tickers for 1-min bar ingestion (day trading candidates)
    UNIVERSE = ["RKLB", "LUNR", "ASTS", "IONQ", "RGTI"]

    # Market indicators for broad watchlist (5-min bars)
    MARKET_TICKERS = [
        # Indices
        "SPY", "QQQ", "DIA", "IWM",
        # Macro
        "TLT", "GLD", "USO", "UUP",
        # International
        "EFA", "EEM", "FXI", "EWJ", "EWG",
        # Sectors
        "XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLU", "XLRE", "XLC", "XLB", "XLY",
    ]

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis: aioredis.Redis | None = None
        self.watchlist: list[str] = []
        self._running = True
        self._av_rotation_idx = 0
        self._finbert_model = None
        self._finbert_tokenizer = None

    async def start(self):
        log.info("connecting to Redis")
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)

        # Build full watchlist: universe + market tickers + IB holdings (future)
        self.watchlist = list(set(self.UNIVERSE + self.MARKET_TICKERS + [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA",
            "JPM", "V", "JNJ",
        ]))
        log.info("watchlist: %d tickers (%d universe, %d market)",
                 len(self.watchlist), len(self.UNIVERSE), len(self.MARKET_TICKERS))

        self._load_finbert()

        await asyncio.gather(
            self._alpaca_bars_loop(),           # 5 min, broad watchlist
            self._alpaca_1min_loop(),            # 1 min, universe only, market hours
            self._yfinance_daily_loop(),         # 30 min, daily bars
            self._news_loop(),                   # 5 min, all tickers (was 15 min)
            self._av_fundamentals_loop(),        # 60 min, 2 rotating tickers
            self._social_loop(),                 # 20 min, 10 tickers
            self._filings_loop(),                # 60 min, all tickers via RSS
            self._economic_calendar_loop(),      # daily, Finnhub
            self._dark_pool_loop(),              # weekly (Saturday), FINRA ATS
            self._congressional_trades_loop(),   # daily, Quiver Quant
            self._short_interest_loop(),         # daily, Quiver Quant
            self._stream_trimmer(),              # 10 min
        )

    def _load_finbert(self):
        """Load FinBERT model for GPU sentiment scoring."""
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch

            model_name = "ProsusAI/finbert"
            log.info("loading FinBERT model: %s", model_name)
            self._finbert_tokenizer = AutoTokenizer.from_pretrained(model_name)
            self._finbert_model = AutoModelForSequenceClassification.from_pretrained(model_name)

            if torch.cuda.is_available():
                self._finbert_model = self._finbert_model.to("cuda")
                log.info("FinBERT loaded on GPU (CUDA)")
            else:
                log.info("FinBERT loaded on CPU (no CUDA available)")
        except ImportError:
            log.warning("transformers/torch not installed, FinBERT disabled")
        except Exception as e:
            log.error("FinBERT load failed: %s", e)

    def _score_sentiment(self, text: str) -> dict:
        """Score a headline with FinBERT. Returns {label, score, positive, negative, neutral}."""
        if not self._finbert_model or not self._finbert_tokenizer or not text:
            return {"label": "neutral", "score": 0, "positive": 0, "negative": 0, "neutral": 1}

        try:
            import torch
            inputs = self._finbert_tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            if torch.cuda.is_available():
                inputs = {k: v.to("cuda") for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self._finbert_model(**inputs)
            probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

            # FinBERT classes: positive, negative, neutral
            positive = float(probs[0])
            negative = float(probs[1])
            neutral = float(probs[2])

            if positive > negative and positive > neutral:
                label = "positive"
                score = positive
            elif negative > positive and negative > neutral:
                label = "negative"
                score = -negative
            else:
                label = "neutral"
                score = 0

            return {"label": label, "score": score, "positive": positive, "negative": negative, "neutral": neutral}
        except Exception as e:
            log.warning("FinBERT scoring failed: %s", e)
            return {"label": "neutral", "score": 0, "positive": 0, "negative": 0, "neutral": 1}

    # -- Prices (Alpaca 5min: broad watchlist) --------------------------------

    async def _alpaca_bars_loop(self):
        """Pull 5-min bars from Alpaca for the full watchlist."""
        import httpx

        api_key = os.environ.get("ALPACA_API_KEY", "")
        api_secret = os.environ.get("ALPACA_API_SECRET", "")
        if not api_key or not api_secret:
            log.warning("ALPACA keys not set, Alpaca ingestion disabled")
            return

        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}

        while self._running:
            try:
                log.info("pulling Alpaca 5min bars (%d tickers)", len(self.watchlist))
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
                        log.info("Alpaca 5min bars: %d tickers", len(bars))
                    elif resp.status_code == 429:
                        log.warning("Alpaca rate limited, backing off 60s")
                        await asyncio.sleep(60)
                    else:
                        log.warning("Alpaca HTTP %d", resp.status_code)
            except Exception as e:
                log.error("Alpaca 5min bars error: %s", e)
            await asyncio.sleep(300)

    # -- Prices (Alpaca 1min: universe only, market hours) --------------------

    async def _alpaca_1min_loop(self):
        """Pull 1-min bars for universe tickers during market hours."""
        import httpx

        api_key = os.environ.get("ALPACA_API_KEY", "")
        api_secret = os.environ.get("ALPACA_API_SECRET", "")
        if not api_key or not api_secret:
            log.warning("ALPACA keys not set, 1min bars disabled")
            return

        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}

        while self._running:
            if not is_market_hours():
                await asyncio.sleep(60)
                continue

            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(
                        "https://data.alpaca.markets/v2/stocks/bars",
                        params={
                            "symbols": ",".join(self.UNIVERSE),
                            "timeframe": "1Min",
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
                            await self.redis.xadd("market:prices:1min", {
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
                                "timestamp": bar.get("t", datetime.utcnow().isoformat()),
                            }, maxlen=self.STREAM_MAX_LEN)
                            # Also write to main stream for DB persistence
                            await self._publish_price(ticker, "alpaca_1min", {
                                "open": float(bar["o"]),
                                "high": float(bar["h"]),
                                "low": float(bar["l"]),
                                "close": float(bar["c"]),
                                "volume": int(bar["v"]),
                                "vwap": float(bar.get("vw", 0)),
                            })
                    elif resp.status_code == 429:
                        await asyncio.sleep(30)
            except Exception as e:
                log.error("Alpaca 1min error: %s", e)
            await asyncio.sleep(60)

    # -- Prices (yfinance: supplementary, daily only) -------------------------

    async def _yfinance_daily_loop(self):
        """Pull daily bars from yfinance as fallback."""
        import yfinance as yf

        backoff = 1800
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
                    await asyncio.sleep(2)
                if failures >= len(self.watchlist):
                    backoff = min(backoff * 2, 7200)
                    log.warning("all yfinance tickers failed, backing off %ds", backoff)
                else:
                    backoff = 1800
                    log.info("yfinance daily bars: %d/%d ok",
                             len(self.watchlist) - failures, len(self.watchlist))
            except Exception as e:
                log.error("yfinance loop error: %s", e)
                backoff = min(backoff * 2, 7200)
            await asyncio.sleep(backoff)

    # -- News (Finnhub, every 5 min, with FinBERT scoring) --------------------

    async def _news_loop(self):
        """Pull news every 5 minutes. Score with FinBERT. 24/7 operation."""
        import httpx

        api_key = os.environ.get("FINNHUB_API_KEY", "")
        if not api_key:
            log.warning("FINNHUB_API_KEY not set, news ingestion disabled")
            return

        while self._running:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    # Prioritize universe + first 10 of watchlist
                    tickers_to_check = list(dict.fromkeys(self.UNIVERSE + self.watchlist[:15]))
                    for ticker in tickers_to_check:
                        try:
                            today = datetime.now().strftime("%Y-%m-%d")
                            yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                            resp = await client.get(
                                "https://finnhub.io/api/v1/company-news",
                                params={"symbol": ticker, "from": yesterday, "to": today, "token": api_key},
                            )
                            if resp.status_code == 200:
                                for article in resp.json()[:5]:
                                    headline = article.get("headline", "")
                                    sentiment = self._score_sentiment(headline)
                                    await self.redis.xadd("market:news", {
                                        "ticker": ticker,
                                        "data": json.dumps({
                                            "headline": headline,
                                            "source": article.get("source", ""),
                                            "url": article.get("url", ""),
                                            "summary": article.get("summary", "")[:500],
                                            "datetime": article.get("datetime", 0),
                                            "sentiment_label": sentiment["label"],
                                            "sentiment_score": sentiment["score"],
                                            "sentiment_positive": sentiment["positive"],
                                            "sentiment_negative": sentiment["negative"],
                                            "sentiment_neutral": sentiment["neutral"],
                                        }),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }, maxlen=self.STREAM_MAX_LEN)
                            elif resp.status_code == 429:
                                log.warning("Finnhub rate limited, stopping news cycle early")
                                break
                        except Exception as e:
                            log.warning("Finnhub news failed for %s: %s", ticker, e)
                        await asyncio.sleep(1)
                log.info("news updated (%d tickers)", len(tickers_to_check))
            except Exception as e:
                log.error("news loop error: %s", e)
            await asyncio.sleep(300)  # 5 min

    # -- Fundamentals (Alpha Vantage) -----------------------------------------

    async def _av_fundamentals_loop(self):
        """Pull fundamentals from Alpha Vantage. 2 tickers per cycle, rotating."""
        import httpx

        av_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
        if not av_key:
            log.warning("ALPHA_VANTAGE_API_KEY not set, fundamentals disabled")
            return

        daily_count = 0
        daily_limit = 20
        day_marker = datetime.utcnow().date()

        while self._running:
            try:
                today = datetime.utcnow().date()
                if today != day_marker:
                    daily_count = 0
                    day_marker = today

                if daily_count >= daily_limit:
                    await asyncio.sleep(3600)
                    continue

                batch_size = 2
                tickers_to_pull = []
                for _ in range(batch_size):
                    tickers_to_pull.append(self.watchlist[self._av_rotation_idx % len(self.watchlist)])
                    self._av_rotation_idx += 1

                async with httpx.AsyncClient(timeout=30) as client:
                    for ticker in tickers_to_pull:
                        if daily_count >= daily_limit:
                            break
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
                        await asyncio.sleep(15)

                log.info("Alpha Vantage: %d/%d daily requests used", daily_count, daily_limit)
            except Exception as e:
                log.error("AV fundamentals loop error: %s", e)
            await asyncio.sleep(3600)

    # -- Social (StockTwits) --------------------------------------------------

    async def _social_loop(self):
        """Pull StockTwits every 20 minutes."""
        import httpx

        while self._running:
            try:
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
                                break
                        except Exception as e:
                            log.warning("StockTwits failed for %s: %s", ticker, e)
                        await asyncio.sleep(2)
            except Exception as e:
                log.error("social loop error: %s", e)
            await asyncio.sleep(1200)

    # -- Filings (SEC EDGAR) --------------------------------------------------

    async def _filings_loop(self):
        """Pull SEC filings every hour. RSS feed."""
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

    # -- Economic Calendar (Finnhub) ------------------------------------------

    async def _economic_calendar_loop(self):
        """Pull economic calendar daily from Finnhub."""
        import httpx

        api_key = os.environ.get("FINNHUB_API_KEY", "")
        if not api_key:
            return

        while self._running:
            try:
                today = date.today()
                end = today + timedelta(days=7)
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://finnhub.io/api/v1/calendar/economic",
                        params={"from": str(today), "to": str(end), "token": api_key},
                    )
                    if resp.status_code == 200:
                        events = resp.json().get("economicCalendar", [])
                        for event in events:
                            await self.redis.xadd("market:calendar", {
                                "data": json.dumps({
                                    "date": event.get("date", ""),
                                    "time": event.get("time", ""),
                                    "country": event.get("country", "US"),
                                    "event": event.get("event", ""),
                                    "impact": event.get("impact", "medium"),
                                    "actual": str(event.get("actual", "")),
                                    "forecast": str(event.get("estimate", "")),
                                    "previous": str(event.get("prev", "")),
                                }),
                                "timestamp": datetime.utcnow().isoformat(),
                            }, maxlen=self.STREAM_MAX_LEN)
                        log.info("economic calendar: %d events", len(events))
            except Exception as e:
                log.error("economic calendar error: %s", e)
            await asyncio.sleep(86400)  # daily

    # -- Dark Pool (FINRA ATS weekly CSV) -------------------------------------

    async def _dark_pool_loop(self):
        """Download FINRA ATS data weekly. Runs Saturday mornings."""
        import httpx

        while self._running:
            now = datetime.now(ET)
            # Run on Saturdays at 8 AM ET
            if now.weekday() != 5 or now.hour != 8:
                await asyncio.sleep(3600)
                continue

            try:
                log.info("downloading FINRA ATS dark pool data")
                async with httpx.AsyncClient(timeout=60) as client:
                    # FINRA publishes OTC/ATS data as downloadable files
                    # This is a simplified version; real implementation would parse
                    # the actual FINRA ATS transparency data files
                    resp = await client.get(
                        "https://api.finra.org/data/group/otcMarket/name/weeklyDownload",
                        headers={"Accept": "application/json"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        count = 0
                        for record in data:
                            ticker = record.get("symbol", "")
                            if not ticker:
                                continue
                            await self.redis.xadd("market:smart_money", {
                                "type": "dark_pool",
                                "ticker": ticker,
                                "data": json.dumps({
                                    "ats_name": record.get("issuerName", ""),
                                    "share_volume": record.get("totalWeeklyShareQuantity", 0),
                                    "trade_count": record.get("totalWeeklyTradeCount", 0),
                                    "report_date": str(date.today()),
                                }),
                                "timestamp": datetime.utcnow().isoformat(),
                            }, maxlen=self.STREAM_MAX_LEN)
                            count += 1
                        log.info("dark pool data: %d records", count)
                    else:
                        log.warning("FINRA ATS HTTP %d", resp.status_code)
            except Exception as e:
                log.error("dark pool error: %s", e)
            await asyncio.sleep(86400)  # don't retry until tomorrow

    # -- Congressional Trades (Quiver Quant) ----------------------------------

    async def _congressional_trades_loop(self):
        """Pull congressional trades daily from Quiver Quant."""
        import httpx

        api_key = os.environ.get("QUIVER_QUANT_API_KEY", "")
        # Quiver Quant free tier may not need a key for some endpoints

        while self._running:
            try:
                log.info("pulling congressional trades")
                async with httpx.AsyncClient(timeout=30) as client:
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"

                    resp = await client.get(
                        "https://api.quiverquant.com/beta/live/congresstrading",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        trades = resp.json()
                        count = 0
                        for trade in trades[:100]:  # cap to avoid flooding
                            ticker = trade.get("Ticker", "")
                            if not ticker:
                                continue
                            await self.redis.xadd("market:smart_money", {
                                "type": "congressional",
                                "ticker": ticker,
                                "data": json.dumps({
                                    "congress_member": trade.get("Representative", ""),
                                    "chamber": trade.get("House", "house").lower(),
                                    "direction": "buy" if trade.get("Transaction", "").lower().startswith("purchase") else "sell",
                                    "amount": trade.get("Amount", ""),
                                    "trade_date": trade.get("TransactionDate", ""),
                                    "disclosure_date": trade.get("DisclosureDate", ""),
                                }),
                                "timestamp": datetime.utcnow().isoformat(),
                            }, maxlen=self.STREAM_MAX_LEN)
                            count += 1
                        log.info("congressional trades: %d records", count)
                    elif resp.status_code == 403:
                        log.warning("Quiver Quant: access denied (API key may be needed)")
                    else:
                        log.warning("Quiver Quant congress HTTP %d", resp.status_code)
            except Exception as e:
                log.error("congressional trades error: %s", e)
            await asyncio.sleep(86400)  # daily

    # -- Short Interest (Quiver Quant) ----------------------------------------

    async def _short_interest_loop(self):
        """Pull short interest data daily."""
        import httpx

        api_key = os.environ.get("QUIVER_QUANT_API_KEY", "")

        while self._running:
            try:
                log.info("pulling short interest")
                async with httpx.AsyncClient(timeout=30) as client:
                    headers = {}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"

                    # Pull short interest for universe tickers specifically
                    for ticker in self.UNIVERSE + self.watchlist[:10]:
                        try:
                            resp = await client.get(
                                f"https://api.quiverquant.com/beta/live/shortinterest/{ticker}",
                                headers=headers,
                            )
                            if resp.status_code == 200:
                                data = resp.json()
                                if data:
                                    latest = data[0] if isinstance(data, list) else data
                                    await self.redis.xadd("market:smart_money", {
                                        "type": "short_interest",
                                        "ticker": ticker,
                                        "data": json.dumps({
                                            "short_shares": latest.get("ShortVolume", 0),
                                            "short_pct_float": latest.get("ShortPercentFloat", 0),
                                            "days_to_cover": latest.get("DaysToCover", 0),
                                            "report_date": latest.get("Date", str(date.today())),
                                        }),
                                        "timestamp": datetime.utcnow().isoformat(),
                                    }, maxlen=self.STREAM_MAX_LEN)
                            await asyncio.sleep(2)
                        except Exception as e:
                            log.warning("short interest failed for %s: %s", ticker, e)
                log.info("short interest updated")
            except Exception as e:
                log.error("short interest error: %s", e)
            await asyncio.sleep(86400)  # daily

    # -- Stream maintenance ---------------------------------------------------

    async def _stream_trimmer(self):
        """Trim Redis Streams to prevent unbounded memory growth."""
        streams = [
            "market:prices", "market:prices:1min", "market:news",
            "market:sentiment", "market:filings", "market:calendar",
            "market:smart_money", "social:reddit", "social:stocktwits",
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
                        pass
            except Exception as e:
                log.error("stream trimmer error: %s", e)
            await asyncio.sleep(600)

    # -- Helpers --------------------------------------------------------------

    async def _publish_price(self, ticker: str, source: str, data: dict):
        """Publish a price entry to the main stream."""
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
