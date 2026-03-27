---
name: portfolio-status
description: Current portfolio state, positions, risk metrics.
---

# /portfolio-status

1. GET /portfolio/positions for current holdings
2. GET /portfolio/risk for risk metrics
3. GET /strategies/ for active strategies
4. Synthesize:
   - Position list with P&L
   - Risk limit utilization
   - Strategy attribution
   - Hedging status
   - Action items
