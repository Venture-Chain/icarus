---
description: Weekly P&L, algorithm performance, pattern analysis, regime assessment, smart money summary.
user_invocable: true
---

# /weekly-review

1. **Weekly P&L**: GET /portfolio/positions for both IB and Alpaca. Compare to 7 days ago. Show total return, by-account breakdown.

2. **Algorithm performance**: GET /strategies/ and deployments. For the week:
   - Total trades and win rate
   - Net P&L from algorithm trades
   - Best and worst trades
   - Average confidence of executed signals
   - Patterns that generated the most signals

3. **What worked**: Which pattern types (breakout, momentum, volume spike) had the best outcomes? Which tickers performed best in the algorithm's universe?

4. **What didn't work**: Losing patterns, false signals, any day where daily loss limit was hit. Root causes.

5. **Market regime**: GET /data/prices/VIX, GET /data/prices/SPY (weekly change). Was the market risk-on or risk-off? How did regime affect algorithm performance?

6. **Smart money summary**: GET /notifications/?type=smart_money&limit=30. Notable dark pool anomalies, congressional trades, insider buys this week. Any confluence setups that materialized?

7. **Adjustments**: Based on this week's data, should we:
   - Adjust ML confidence threshold?
   - Add/remove tickers from the universe?
   - Modify position sizing for current VIX regime?
   - Retrain the Layer 2 model?

8. **Log**: POST /research/log with weekly summary.
