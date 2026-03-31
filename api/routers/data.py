from datetime import datetime, timedelta

from fastapi import APIRouter, Query, Request

import redis.asyncio as aioredis
from config import settings
from services.rate_limiter import RateLimiter

router = APIRouter()


@router.get("/prices/{ticker}")
async def get_prices(
    ticker: str,
    request: Request,
    start: str = None,
    end: str = None,
    interval: str = "5min",
    limit: int = Query(500, le=5000),
):
    """Get historical price data for a ticker."""
    pool = request.app.state.db_pool
    now = datetime.utcnow()

    if not start:
        start = (now - timedelta(days=7)).isoformat()
    if not end:
        end = now.isoformat()

    rows = await pool.fetch(
        """
        SELECT time, open, high, low, close, volume, source
        FROM market_data
        WHERE ticker = $1 AND time >= $2 AND time <= $3
        ORDER BY time DESC
        LIMIT $4
        """,
        ticker.upper(), start, end, limit,
    )
    return {
        "ticker": ticker.upper(),
        "interval": interval,
        "count": len(rows),
        "data": [
            {
                "time": str(r["time"]),
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "volume": r["volume"],
                "source": r["source"],
            }
            for r in rows
        ],
    }


@router.get("/news/{ticker}")
async def get_news(
    ticker: str,
    request: Request,
    hours: int = Query(24, le=168),
    limit: int = Query(50, le=200),
):
    """Get recent news for a ticker with FinBERT sentiment scores."""
    pool = request.app.state.db_pool
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    rows = await pool.fetch(
        """
        SELECT time, source, score, magnitude, raw_text, metadata
        FROM sentiment_scores
        WHERE ticker = $1 AND time >= $2
        ORDER BY time DESC
        LIMIT $3
        """,
        ticker.upper(), cutoff.isoformat(), limit,
    )
    return {
        "ticker": ticker.upper(),
        "count": len(rows),
        "articles": [
            {
                "time": str(r["time"]),
                "source": r["source"],
                "sentiment_score": r["score"],
                "magnitude": r["magnitude"],
                "headline": r["raw_text"],
                "metadata": r["metadata"],
            }
            for r in rows
        ],
    }


@router.get("/sentiment/{ticker}")
async def get_sentiment(
    ticker: str,
    request: Request,
    hours: int = Query(24, le=168),
):
    """Get aggregated sentiment for a ticker."""
    pool = request.app.state.db_pool
    cutoff = datetime.utcnow() - timedelta(hours=hours)

    row = await pool.fetchrow(
        """
        SELECT
            COUNT(*) as total,
            AVG(score) as avg_score,
            COUNT(*) FILTER (WHERE score > 0.3) as positive,
            COUNT(*) FILTER (WHERE score < -0.3) as negative,
            COUNT(*) FILTER (WHERE score BETWEEN -0.3 AND 0.3) as neutral
        FROM sentiment_scores
        WHERE ticker = $1 AND time >= $2
        """,
        ticker.upper(), cutoff.isoformat(),
    )
    return {
        "ticker": ticker.upper(),
        "hours": hours,
        "total": row["total"],
        "avg_score": float(row["avg_score"]) if row["avg_score"] else 0,
        "positive": row["positive"],
        "negative": row["negative"],
        "neutral": row["neutral"],
    }


@router.get("/filings/{ticker}")
async def get_filings(
    ticker: str,
    request: Request,
    filing_type: str = None,
    limit: int = Query(20, le=100),
):
    """Get SEC filings for a ticker."""
    pool = request.app.state.db_pool

    if filing_type:
        rows = await pool.fetch(
            """
            SELECT id, filing_type, filing_date, url, description, metadata
            FROM filings
            WHERE ticker = $1 AND filing_type = $2
            ORDER BY filing_date DESC
            LIMIT $3
            """,
            ticker.upper(), filing_type, limit,
        )
    else:
        rows = await pool.fetch(
            """
            SELECT id, filing_type, filing_date, url, description, metadata
            FROM filings
            WHERE ticker = $1
            ORDER BY filing_date DESC
            LIMIT $2
            """,
            ticker.upper(), limit,
        )
    return {
        "ticker": ticker.upper(),
        "count": len(rows),
        "filings": [
            {
                "id": r["id"],
                "type": r["filing_type"],
                "date": str(r["filing_date"]),
                "url": r["url"],
                "description": r["description"],
            }
            for r in rows
        ],
    }


@router.get("/fundamentals/{ticker}")
async def get_fundamentals(ticker: str, request: Request):
    """Get fundamental data for a ticker."""
    pool = request.app.state.db_pool

    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (metric) metric, value, period, as_of, source
        FROM fundamentals
        WHERE ticker = $1
        ORDER BY metric, as_of DESC
        """,
        ticker.upper(),
    )
    return {
        "ticker": ticker.upper(),
        "fundamentals": {
            r["metric"]: {
                "value": r["value"],
                "period": r["period"],
                "as_of": str(r["as_of"]),
                "source": r["source"],
            }
            for r in rows
        },
    }


@router.get("/market/overview")
async def get_market_overview(request: Request):
    """Latest prices for market indicators (indices, macro, sectors)."""
    pool = request.app.state.db_pool

    tickers = [
        "SPY", "QQQ", "DIA", "IWM",
        "VIX", "TLT", "GLD", "USO", "UUP",
        "XLK", "XLF", "XLE", "XLV", "XLI", "XLP", "XLU", "XLRE", "XLC", "XLB", "XLY",
        "EFA", "EEM", "FXI", "EWJ", "EWG",
    ]

    rows = await pool.fetch(
        """
        SELECT DISTINCT ON (ticker) ticker, time, close, volume
        FROM market_data
        WHERE ticker = ANY($1)
        ORDER BY ticker, time DESC
        """,
        tickers,
    )
    return {
        "count": len(rows),
        "data": {
            r["ticker"]: {
                "price": r["close"],
                "volume": r["volume"],
                "time": str(r["time"]),
            }
            for r in rows
        },
    }


@router.get("/market/calendar")
async def get_economic_calendar(
    request: Request,
    days: int = Query(7, le=30),
):
    """Upcoming economic events."""
    pool = request.app.state.db_pool
    today = datetime.utcnow().date()

    rows = await pool.fetch(
        """
        SELECT event_date, event_time, country, event, impact, actual, forecast, previous
        FROM economic_calendar
        WHERE event_date >= $1 AND event_date <= $2
        ORDER BY event_date, event_time
        """,
        today, today + timedelta(days=days),
    )
    return {
        "count": len(rows),
        "events": [
            {
                "date": str(r["event_date"]),
                "time": str(r["event_time"]) if r["event_time"] else None,
                "country": r["country"],
                "event": r["event"],
                "impact": r["impact"],
                "actual": r["actual"],
                "forecast": r["forecast"],
                "previous": r["previous"],
            }
            for r in rows
        ],
    }


@router.get("/smart-money/{ticker}")
async def get_smart_money(ticker: str, request: Request):
    """Dark pool Z-score, congressional trades, insider activity, short interest for a ticker."""
    pool = request.app.state.db_pool
    t = ticker.upper()

    dark_pool = await pool.fetch(
        """
        SELECT report_date, ats_name, share_volume, z_score
        FROM dark_pool_volume
        WHERE ticker = $1
        ORDER BY report_date DESC
        LIMIT 10
        """,
        t,
    )

    congress = await pool.fetch(
        """
        SELECT congress_member, chamber, direction, amount_min, amount_max, trade_date, disclosure_date
        FROM congressional_trades
        WHERE ticker = $1
        ORDER BY trade_date DESC
        LIMIT 10
        """,
        t,
    )

    insiders = await pool.fetch(
        """
        SELECT filing_type, filing_date, description, metadata
        FROM filings
        WHERE ticker = $1 AND filing_type = '4'
        ORDER BY filing_date DESC
        LIMIT 10
        """,
        t,
    )

    short = await pool.fetchrow(
        """
        SELECT report_date, short_shares, short_pct_float, days_to_cover, change_pct
        FROM short_interest
        WHERE ticker = $1
        ORDER BY report_date DESC
        LIMIT 1
        """,
        t,
    )

    # Compute latest Z-score (aggregate across all ATS venues for latest report)
    latest_z = await pool.fetchrow(
        """
        SELECT MAX(z_score) as max_z, SUM(share_volume) as total_volume, report_date
        FROM dark_pool_volume
        WHERE ticker = $1 AND report_date = (
            SELECT MAX(report_date) FROM dark_pool_volume WHERE ticker = $1
        )
        GROUP BY report_date
        """,
        t,
    )

    return {
        "ticker": t,
        "dark_pool": {
            "latest_z_score": float(latest_z["max_z"]) if latest_z and latest_z["max_z"] else None,
            "latest_volume": latest_z["total_volume"] if latest_z else None,
            "report_date": str(latest_z["report_date"]) if latest_z else None,
            "history": [
                {
                    "date": str(r["report_date"]),
                    "ats": r["ats_name"],
                    "volume": r["share_volume"],
                    "z_score": r["z_score"],
                }
                for r in dark_pool
            ],
        },
        "congressional_trades": [
            {
                "member": r["congress_member"],
                "chamber": r["chamber"],
                "direction": r["direction"],
                "amount_range": [r["amount_min"], r["amount_max"]],
                "trade_date": str(r["trade_date"]),
                "disclosure_date": str(r["disclosure_date"]),
            }
            for r in congress
        ],
        "insider_trades": [
            {
                "type": r["filing_type"],
                "date": str(r["filing_date"]),
                "description": r["description"],
            }
            for r in insiders
        ],
        "short_interest": {
            "report_date": str(short["report_date"]) if short else None,
            "short_shares": short["short_shares"] if short else None,
            "short_pct_float": short["short_pct_float"] if short else None,
            "days_to_cover": short["days_to_cover"] if short else None,
            "change_pct": short["change_pct"] if short else None,
        } if short else None,
    }


@router.get("/rate-limits")
async def get_rate_limits(request: Request):
    """Get current rate limit usage for all data sources."""
    r = request.app.state.redis
    limiter = RateLimiter(r)
    return await limiter.remaining_all()
