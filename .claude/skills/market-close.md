---
description: End-of-day wrap with daily P&L, algorithm trades, positions flattened, and overnight risk.
user_invocable: true
---

# /market-close

End-of-day wrap. Run after market close.

1. **Daily P&L**: GET /portfolio/positions for both accounts. Show total value, daily change, unrealized P&L. GET /portfolio/risk for exposure summary.

2. **Algorithm trades today**: GET /strategies/ then GET /strategies/{name}/deployments for active deployments. Summarize: total trades, wins/losses, net P&L, best trade, worst trade.

3. **Positions flattened**: Confirm all Alpaca positions were closed at 3:55 PM. GET /portfolio/positions?account_id=alpaca-paper (should be empty). Flag if any positions remain.

4. **IB holdings update**: Any material after-hours news? GET /data/news/{ticker} for each IB holding. Flag earnings reports, FDA decisions, or other catalysts.

5. **Overnight risk**: GET /portfolio/risk for IB-only. Note any concentrated positions (> 10%). Check if VIX elevated (gap risk).

6. **Summary**: One paragraph. How did the day go? What carries into tomorrow?
