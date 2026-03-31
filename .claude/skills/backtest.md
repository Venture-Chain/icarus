---
description: Run a backtest and analyze results with full metrics.
user_invocable: true
---

# /backtest

1. **Collect parameters**: Ask for strategy name, universe (tickers), start date, end date, initial capital. Use defaults if not provided: capital $100k, last 3 months.

2. **Run**: POST /research/backtest/run with:
   ```json
   {"strategy_name": "...", "universe": [...], "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "initial_capital": 100000}
   ```

3. **Results**: Display from response:
   - Total return and annualized return
   - Sharpe, Sortino, Calmar ratios
   - Max drawdown (%) and when it occurred
   - Win rate and profit factor
   - Total trades and avg trade P&L
   - Transaction cost drag
   - Equity curve (last 20 data points)

4. **Benchmark**: Compare total return to SPY buy-and-hold over the same period (GET /data/prices/SPY).

5. **Analysis**: What worked, what didn't. Note if Sharpe < 1.0 (weak), drawdown > 15% (concerning), or win rate < 40% (pattern may not be reliable).

6. **Log**: Offer to save findings via POST /research/log.

7. **Retrieve past runs**: GET /research/backtest/{id} to review previous results.
