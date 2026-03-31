---
description: IB + Alpaca positions, risk metrics, unrealized P&L, and news affecting holdings.
user_invocable: true
---

# /portfolio-status

1. **Positions**: GET /portfolio/positions for all accounts. Show table: ticker, quantity, avg cost, current price, unrealized P&L, % of portfolio.

2. **Risk metrics**: GET /portfolio/risk. Show: portfolio value, long/short exposure, net/gross exposure, largest position %, unrealized P&L.

3. **Account breakdown**: GET /accounts/ for all connected accounts. Show type (IB vs Alpaca), paper vs live, connection status.

4. **News on holdings**: For each held ticker, GET /data/news/{ticker} (last 24 hours). Surface material headlines with FinBERT sentiment. Flag strongly negative news.

5. **Alerts**: GET /notifications/?unread_only=true&limit=5 for recent unread alerts.

Present as clean tables. IB positions first (main portfolio), then Alpaca (trading account).
