---
description: Stock research workflow with prices, news, sentiment, filings, fundamentals, and smart money confluence.
user_invocable: true
---

# /research {ticker}

Full research report for a ticker.

1. **Price action**: GET /data/prices/{ticker}?interval=1day. Show recent trend, support/resistance levels, 52-week range, volume trend.

2. **Fundamentals**: GET /data/fundamentals/{ticker}. Key metrics: market cap, P/E, revenue growth, margins, debt/equity.

3. **News**: GET /data/news/{ticker}. Last 20 headlines with FinBERT sentiment scores. Note dominant narrative (positive, negative, mixed).

4. **Sentiment**: GET /data/sentiment/{ticker}. Social and news aggregate sentiment. Trend vs. prior week.

5. **Filings**: GET /data/filings/{ticker}. Recent SEC filings. Flag 8-K (material events), 10-Q, 10-K, insider Form 4s.

6. **Smart money confluence**: GET /data/smart-money/{ticker}. Full smart money analysis:
   - Dark pool Z-score and interpretation
   - Congressional trades (last 45 days)
   - Insider purchases (Form 4, last 30 days)
   - Short interest and trend
   - Conviction score and direction

7. **Synthesis**: Combine all data into a research summary:
   - Bull case (what supports going long)
   - Bear case (what supports caution)
   - Key catalysts ahead
   - Smart money alignment
   - Overall assessment: strong buy, buy, neutral, avoid

8. **Universe candidate**: If the user is evaluating this ticker for the algorithm's universe, note whether it meets criteria: liquid, volatile, adequate 1-min bar history, favorable smart money signals.

9. **Log**: Offer to save via POST /research/log.
