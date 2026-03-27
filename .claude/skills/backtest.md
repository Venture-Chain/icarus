---
name: backtest
description: Run a backtest and analyze results.
---

# /backtest {strategy} --start {date} --end {date} --universe {tickers}

1. POST /research/backtest/run with strategy name, date range, universe
2. Poll GET /research/backtest/{id} until complete
3. Analyze results:
   - Equity curve shape
   - Sharpe, Sortino, Calmar ratios
   - Max drawdown periods
   - Win rate and profit factor
   - Transaction cost drag
4. Compare to SPY buy-and-hold benchmark
5. Report findings
