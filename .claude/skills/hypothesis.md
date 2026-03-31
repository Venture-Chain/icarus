---
description: Research a trading hypothesis with data gathering, testing, and logging.
user_invocable: true
---

# /hypothesis

Research workflow for testing a trading idea.

1. **Define**: State the hypothesis clearly. Example: "RKLB tends to rally after dark pool Z-score > 2.5 with positive FinBERT sentiment."

2. **Data requirements**: Determine what data is needed:
   - Price data: GET /data/prices/{ticker}?start=&end=&interval=
   - News/sentiment: GET /data/news/{ticker}, GET /data/sentiment/{ticker}
   - Smart money: GET /data/smart-money/{ticker}
   - Fundamentals: GET /data/fundamentals/{ticker}
   - Filings: GET /data/filings/{ticker}

3. **Gather evidence**: Pull the relevant data and look for the pattern. Compute correlations, frequencies, success rates.

4. **Test**: If the hypothesis suggests a tradeable pattern, run a backtest via POST /research/backtest/run with appropriate parameters.

5. **Assess robustness**: Does the pattern hold across multiple time periods? Is the sample size large enough? What's the false positive rate?

6. **Log findings**: POST /research/log with:
   ```json
   {"hypothesis": "...", "methodology": "...", "findings": "...", "data_sources": [...]}
   ```

7. **Next steps**: If promising, suggest creating a strategy implementation. If weak, note why and archive.
