---
description: Algorithm status, recent trades, performance stats, active deployments.
user_invocable: true
---

# /strategies

1. **List strategies**: GET /strategies/. Show all loaded strategies with name and description.

2. **Active deployments**: For each strategy, GET /strategies/{name}/deployments. Show table: deployment ID, account, status, universe, capital, deployed date.

3. **Performance**: For active deployments, summarize from deployment snapshots:
   - NAV and daily P&L
   - Win rate and total trades
   - Sharpe ratio (if enough data)
   - Max drawdown
   - Current positions held

4. **Layer 2 model**: If swing_pattern is active, note ML model confidence distribution from recent signals. What's the average confidence of generated signals? How many were filtered out below the 0.6 threshold?

5. **Recent signals**: Last 10 signals generated across all deployments. Show: ticker, direction, confidence, pattern type, outcome (if known).

6. **Deployment health**: Flag any deployment stopped by daily loss limit or drawdown. Note time until next market open if stopped.
