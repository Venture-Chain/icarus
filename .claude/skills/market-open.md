---
description: Morning briefing with overnight news, pre-market movers, portfolio state, algorithm performance, and smart money alerts.
user_invocable: true
---

# /market-open

Morning briefing workflow. Run before or at market open.

1. **Overnight news**: For each holding (GET /portfolio/positions), fetch GET /data/news/{ticker}. Surface anything published since last market close. Include FinBERT sentiment scores.

2. **Pre-market movers**: GET /data/market/overview for SPY, QQQ, VIX. Note direction and magnitude. Check international ETFs (EFA, EEM) for overnight context.

3. **IB portfolio state**: GET /portfolio/positions?account_id=ib-default. Show total value, overnight change, any large movers in the portfolio.

4. **Algorithm performance**: GET /strategies/ to list active strategies. For each with active deployments (GET /strategies/{name}/deployments), summarize yesterday's performance: trades, P&L, win rate.

5. **Smart money overnight**: GET /notifications/?type=smart_money&limit=10 for recent dark pool anomalies, congressional trades, or insider buys that arrived overnight.

6. **Economic calendar**: GET /data/market/calendar for today's events. Flag high-impact events (Fed, CPI, NFP, FOMC).

7. **Synthesis**: One paragraph covering: market mood, key risks for today, what to watch. Keep under 100 words.
