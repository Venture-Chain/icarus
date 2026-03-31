---
name: market-open
description: Pre-market brief template. Override in research/ for custom methodology.
---

# /market-open

Pre-market brief workflow:

1. Pull overnight news via GET /data/news/{ticker} for watchlist
2. Check pre-market movers via GET /data/prices/{ticker}
3. Social sentiment via GET /data/sentiment/{ticker}
4. Any SEC filings via GET /data/filings/{ticker}
5. Current positions and risk via GET /portfolio/positions and GET /portfolio/risk
6. Summarize: key movers, risk alerts, opportunities
