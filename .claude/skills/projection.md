---
description: Run Monte Carlo projections and scenario analysis for a ticker or portfolio.
user_invocable: true
---

# /projection

## Monte Carlo

Collect: ticker or portfolio list, years (default 10), initial_value, annual_contribution (default 0).

Call: POST /research/projections/monte-carlo
Body: {ticker, portfolio, years, iterations: 5000, initial_value, annual_contribution}

Present:
- Percentile curves (P5, P25, P50, P75, P95) over time
- Final value: mean, median, P5 (worst case), P95 (best case)
- Probability of positive outcome
- Estimated annual return and volatility used

## Scenario Analysis

Collect: portfolio tickers, portfolio_value, scenarios (default: base, bull, bear, recession, rate_hike).

Call: POST /research/projections/scenario
Body: {portfolio, portfolio_value, scenarios}

Present:
- Table: scenario, probability, projected 1Y value, PnL, return %
- Expected value across all scenarios
- Call out any scenario with > 20% loss
- Which scenario presents the most risk given current positioning

Offer follow-up: adjust parameters, compare two portfolio compositions, or cross-reference with GET /portfolio/risk.
