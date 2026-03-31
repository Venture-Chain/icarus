---
description: Manage the trading algorithm's universe of tickers.
user_invocable: true
---

# /universe

1. **Current universe**: List the algorithm's current ticker universe. Default: RKLB, LUNR, ASTS, IONQ, RGTI. Check active deployments via GET /strategies/{name}/deployments for actual configured universe.

2. **Ticker evaluation**: For a candidate ticker, run a quick screen:
   - GET /data/prices/{ticker}: check liquidity (avg daily volume), volatility (ATR), price range
   - GET /data/smart-money/{ticker}: confluence score and signals
   - GET /data/sentiment/{ticker}: is there enough social/news coverage for sentiment signals?
   - Minimum requirements: > 500k avg daily volume, > 2% daily ATR, adequate 1-min bar history

3. **Add a ticker**: If evaluation passes, suggest updating the deployment config via PUT /strategies/{name}/deploy with the expanded universe list. Note: this creates a new deployment or updates existing.

4. **Remove a ticker**: If a ticker is underperforming or no longer meets criteria, suggest removing it from the universe. Review its algorithm performance first.

5. **Smart money screening**: Find high-conviction setups across a broader list. GET /data/smart-money/{ticker} for a watchlist of candidates. Surface any with conviction > 60 as potential universe additions.

6. **Performance by ticker**: For the current universe, compare algorithm performance per ticker: which tickers generate the most signals, best win rate, highest average P&L.

7. **Sector balance**: Note if the current universe is concentrated in one sector. Suggest diversification if all tickers are in the same industry.
