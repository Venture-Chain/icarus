---
description: Comprehensive state-of-the-market report covering global, US, macro, sectors, news, sentiment, and smart money.
user_invocable: true
---

# /market-report

Fetch all data in parallel where possible, then synthesize into sections.

## Data Collection

GET /data/market/overview for broad summary.
GET /data/market/calendar for today's economic events.
GET /portfolio/positions for current holdings.

Prices (GET /data/prices/{ticker} for each):
- International: EFA, EEM, FXI, EWJ, EWG
- US broad: SPY, QQQ, DIA, IWM
- Macro: VIX, TLT, GLD, USO, UUP
- Sectors: XLK, XLF, XLE, XLV, XLI, XLP, XLU, XLRE, XLC, XLB, XLY

For each holding: GET /data/news/{ticker}, GET /data/sentiment/{ticker}, GET /data/smart-money/{ticker}

## Report Sections

### 1. Global/International
Overnight moves in EFA, EEM, FXI, EWJ, EWG. Flag any ETF down > 1%.

### 2. US Pre-Market
SPY, QQQ, DIA, IWM: price, change, implied direction. Note divergence from international action.

### 3. Macro
- VIX: level and change. Flag > 20 (elevated), > 30 (fear).
- TLT: bond signal. Rising = risk-off.
- GLD: safe haven demand. USO: economic activity proxy. UUP: dollar strength.
One paragraph macro synthesis.

### 4. Sector Rotation
Rank all 11 sector ETFs by change %. Table: sector, ETF, change %.
Top 3 and bottom 3. Note if defensives (XLP, XLU, XLV) leading (risk-off rotation).

### 5. Economic Calendar
Today's events from /data/market/calendar. Flag high-impact: Fed, CPI, NFP, FOMC, GDP.

### 6. Key News
For each holding, material stories only. Include FinBERT sentiment score.
Flag stories scoring below -0.5 or above 0.5.

### 7. Sentiment Aggregate
Table: ticker, sentiment score, trend vs. prior. Flag extreme readings (< -0.6 or > 0.6).

### 8. Smart Money
For each holding: dark pool Z-scores > 2.0, congressional trades, insider Form 4 buys, short interest changes.

### 9. Holdings Impact
One-line per holding: what today's data means for the position.
Flag holdings with multiple negative signals.

### 10. Synthesis (150 words max)
- Market regime: risk-on, risk-off, or mixed
- Key themes driving today
- Primary risks to monitor
- Opportunities to watch
