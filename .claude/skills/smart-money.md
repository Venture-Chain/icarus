---
description: Review smart money activity: dark pools, congressional trades, insider purchases, short interest, confluence setups.
user_invocable: true
---

# /smart-money

1. Determine scope:
   - If user specifies a ticker: analyze that ticker only
   - Otherwise: GET /portfolio/positions, then analyze each holding

2. For each ticker, GET /data/smart-money/{ticker} and extract:

   **Dark pool**: Z-score vs. 30-day avg volume. Flag abs(Z) > 2.0, highlight Z > 3.0 as high conviction.

   **Congressional trades**: Trades filed in last 30 days. Show: politician, direction (buy/sell), amount range, date. Note if multiple politicians traded same direction.

   **Insider activity (Form 4)**: Purchases only. Show: name, title, shares, price, date. Flag C-suite purchases above $100k.

   **Short interest**: % of float, week-over-week change, days to cover. Flag > 15% (squeeze potential) or > 20% drop (short covering).

3. Confluence scoring:
   - Feature any ticker with conviction > 70
   - Explain which signals combine to drive the score
   - Note directional bias (bullish vs. bearish)

4. Summary table:
   Ticker | Dark Pool Z | Congressional | Insider Buys | Short % Float | Conviction
   Sort by conviction descending.

5. Narrative: top 2-3 setups, sector themes, what smart money is signaling collectively.

6. Follow-up options:
   - Cross-reference with GET /data/sentiment/{ticker} and GET /data/news/{ticker}
   - Check exposure alignment via GET /portfolio/positions
