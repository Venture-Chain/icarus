---
description: Risk metrics, limit utilization, stress scenarios, and VaR assessment.
user_invocable: true
---

# /risk-check

1. **Current risk**: GET /portfolio/risk. Show: portfolio value, net/gross exposure, largest position %, unrealized P&L.

2. **Limit utilization**: Check against hard limits:
   - Daily loss: 2% of capital
   - Max drawdown: 10% from peak
   - Position concentration: largest vs 5% limit
   - Concurrent positions: count vs max 3

3. **VIX regime**: GET /data/prices/VIX. Current level and trend.
   - < 15: low vol, normal sizing
   - 15-20: moderate
   - 20-30: elevated, consider reducing size 25%
   - > 30: high vol, reduce size 50%

4. **Stress scenarios**: Approximate P&L impact if:
   - Market drops 3% today (SPY -3%)
   - Largest holding drops 10%
   - All positions hit stops simultaneously

5. **Algorithm status**: Any deployments stopped for daily loss limit? GET /strategies/ and check deployment status.

6. **Recommendations**: Flag limits approaching 80%. Suggest adjustments if VIX regime changed.
