---
name: hypothesis
description: Research a trading hypothesis with quantitative analysis.
---

# /hypothesis "{description}"

1. Define the hypothesis clearly
2. Select stock universe
3. Determine data requirements and time period
4. Construct the factor as a numerical signal
5. Run factor analysis via POST /research/factor/analyze
6. If promising: backtest with POST /research/backtest/run
7. Assess robustness and parameter sensitivity
8. Log results via POST /research/log
9. Recommend next steps
