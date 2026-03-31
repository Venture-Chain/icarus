---
description: Deploy a strategy to paper or promote to live trading.
user_invocable: true
---

# /deploy-strategy

1. **List available**: GET /strategies/ to show all loaded strategies.

2. **Check existing deployments**: GET /strategies/{name}/deployments. Show any active deployments with their config.

3. **Collect parameters**: Ask for:
   - Strategy name (required)
   - Mode: paper or live (default: paper)
   - Account ID: alpaca-paper or alpaca-live (default: paper)
   - Universe: list of tickers (default: RKLB, LUNR, ASTS, IONQ, RGTI)
   - Capital: amount to allocate (default: $10,000)
   - No overnight: true/false (default: true)
   - Daily loss limit: % (default: 2%)
   - Max concurrent positions: (default: 3)

4. **Safety check before deploying**:
   - If mode is "live": require explicit confirmation, warn about real money
   - If capital > $50,000: flag as high capital, confirm
   - Verify the strategy has been paper traded (check for existing paper deployments)

5. **Deploy**: PUT /strategies/{name}/deploy with:
   ```json
   {"mode": "paper", "account_id": "alpaca-paper", "universe": [...], "capital": 10000, "no_overnight": true, "daily_loss_limit_pct": 0.02, "max_concurrent_positions": 3}
   ```

6. **Confirm**: Show deployment ID, status, and config. Remind user the runner will start executing at next market open.

7. **Stop a deployment**: DELETE /strategies/{name}/deployments/{id} to stop.
