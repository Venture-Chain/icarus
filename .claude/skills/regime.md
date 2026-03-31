---
description: Market regime analysis covering VIX, sector rotation, breadth, and yield signals.
user_invocable: true
---

# /regime

1. **VIX regime**: GET /data/prices/VIX. Current level, 5-day trend, 20-day average.
   - < 15: Low vol (risk-on, trend-following works)
   - 15-20: Normal (standard conditions)
   - 20-30: Elevated (mean-reversion setups, reduce size)
   - > 30: Crisis (high dispersion, defensive posture)

2. **Market trend**: GET /data/prices/SPY. Position vs. 20-day and 50-day moving averages. Is market trending or range-bound?

3. **Sector rotation**: GET /data/prices/{etf} for all 11 sectors (XLK, XLF, XLE, XLV, XLI, XLP, XLU, XLRE, XLC, XLB, XLY). Rank by 5-day performance.
   - Cyclicals leading (XLK, XLI, XLY): risk-on, economic expansion
   - Defensives leading (XLP, XLU, XLV): risk-off, late cycle
   - Energy leading (XLE): inflation trade

4. **Breadth**: Compare SPY vs. RSP (equal-weight S&P). If SPY outperforming RSP, breadth is narrowing (fewer stocks driving the market, fragile).

5. **Bond market signal**: GET /data/prices/TLT. Rising TLT = falling yields = risk-off or rate cut expectations. Falling TLT = rising yields = tightening.

6. **Dollar**: GET /data/prices/UUP. Strong dollar = headwind for equities and commodities.

7. **Regime classification**: Based on all signals, classify the current market as one of:
   - Risk-on trending
   - Risk-on choppy
   - Neutral/transitional
   - Risk-off correcting
   - Crisis/high volatility

8. **Algorithm implications**: How should the current regime affect:
   - Pattern selection (breakouts vs. mean-reversion)
   - Position sizing (reduce in high vol)
   - Universe focus (defensive vs. growth names)
