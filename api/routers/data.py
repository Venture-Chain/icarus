from fastapi import APIRouter, Query

import redis.asyncio as aioredis
from config import settings
from services.rate_limiter import RateLimiter

router = APIRouter()


@router.get("/prices/{ticker}")
async def get_prices(ticker: str, start: str = None, end: str = None):
    """Get historical price data for a ticker."""
    return {"ticker": ticker, "start": start, "end": end, "data": []}


@router.get("/news/{ticker}")
async def get_news(ticker: str, source: str = None):
    """Get news for a ticker from specified source."""
    return {"ticker": ticker, "source": source, "articles": []}


@router.get("/sentiment/{ticker}")
async def get_sentiment(ticker: str, source: str = None, start: str = None, end: str = None):
    """Get sentiment scores for a ticker."""
    return {"ticker": ticker, "source": source, "scores": []}


@router.get("/filings/{ticker}")
async def get_filings(ticker: str, filing_type: str = None):
    """Get SEC filings for a ticker."""
    return {"ticker": ticker, "type": filing_type, "filings": []}


@router.get("/fundamentals/{ticker}")
async def get_fundamentals(ticker: str):
    """Get fundamental data for a ticker."""
    return {"ticker": ticker, "fundamentals": {}}


@router.get("/rate-limits")
async def get_rate_limits():
    """Get current rate limit usage for all data sources."""
    r = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        limiter = RateLimiter(r)
        return await limiter.remaining_all()
    finally:
        await r.close()
