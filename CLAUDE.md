# Icarus: Quantitative Trading Framework

Open-source (Apache 2.0) quantitative trading platform with Interactive Brokers integration.
Built by Venture Chain. Provides infrastructure for systematic trading: risk management,
execution, backtesting, portfolio optimization, and data ingestion. Users implement their
own strategies via the plugin system.

Proprietary research lives separately in `../icarus-research/`.

## Stack

- **API**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async via asyncpg)
- **Database**: PostgreSQL + TimescaleDB 16 (time-series hypertables)
- **Cache/Streams**: Redis 7 (caching + Redis Streams for real-time events)
- **UI**: React 19 + TypeScript 5.9 + Vite (Control Room dashboard, terminal aesthetic)
- **ML**: PyTorch (CPU in container, CUDA via host mount) + scikit-learn
- **Broker**: Interactive Brokers Gateway (ibapi + IBC for 2FA, Xvfb + noVNC for headless)
- **Data Sources**: Alpaca (primary), Finnhub, Alpha Vantage, yfinance, SEC EDGAR, StockTwits, Reddit

## Local Dev

```
docker compose up
```

| Service | Port | Purpose |
|---|---|---|
| icarus-api | 5100 | FastAPI REST + WebSocket |
| icarus-ui | 5101 | Control Room dashboard |
| timescaledb | 5102 | TimescaleDB (PostgreSQL) |
| redis | 5103 | Cache + streams |
| ib-gateway | 5104 | IB API (+ 5105 VNC, 5106 noVNC) |
| icarus-worker | (bg) | Data ingestion |

## Project Structure

```
icarus/
  api/
    main.py                     # FastAPI app setup, routers, WebSocket
    config.py                   # Settings from environment
    routers/
      strategy.py               # Strategy registration, deployment
      portfolio.py              # Positions, risk metrics, kill-switch, live-checklist
      data.py                   # Price, news, sentiment, filings, fundamentals
      research.py               # Backtest, factor analysis, research logging
      ml.py                     # Model training, inference, experiments
      approvals.py              # CIO approval requests (WebSocket + HTTP)
    engines/
      strategy_engine.py        # Signal generation and execution flow
      risk_engine.py            # VaR, CVaR, limits, kill-switch
      execution_engine.py       # Signal-to-order conversion, sizing, IB placement
      backtest_engine.py        # Walk-forward testing, survivorship bias handling
      portfolio_optimizer.py    # Mean-variance, risk parity, Black-Litterman
      hedging_engine.py         # Beta, sector, pair hedging recommendations
      ml_engine.py              # Model lifecycle: train, eval, predict
      cost_model.py             # Commission, slippage, tiered pricing
      valuation_engine.py       # DCF, comparable analysis
      sensitivity_engine.py     # Stress testing, scenario analysis
      data_quality_engine.py    # Data validation
      approval_engine.py        # CIO approval workflow
      live_checklist.py         # Pre-live-trading validation
    services/
      ib_client.py              # IB Gateway client (threading bridge)
      alpaca.py                 # Alpaca Markets batch API
      finnhub.py                # Finnhub news + fundamentals
      alpha_vantage.py          # Alpha Vantage (rotating daily budget)
      sec_edgar.py              # SEC filing scraper (RSS)
      stocktwits.py             # Social sentiment
      reddit.py                 # Subreddit aggregation
      yahoo.py                  # yfinance wrapper (fallback)
      cache.py                  # Redis caching layer
      rate_limiter.py           # API call budgeting
      streams.py                # Redis Streams publisher
    strategies/
      base.py                   # BaseStrategy + Signal + DataRequirement
      example_momentum.py       # MA crossover (educational)
      example_mean_reversion.py # Mean reversion (educational)
    models/                     # SQLAlchemy models
  worker/
    main.py                     # Async data pulls from all sources (rate-aware scheduling)
    db_writer.py                # Writes to PostgreSQL
  ml/
    features/
      base.py                   # Feature builders (returns, volatility, momentum, RSI, volume)
    models/
      base.py                   # BaseMLModel + ModelPrediction
  ui/
    src/
      App.tsx                   # Main layout (6-panel grid)
      App.css                   # Terminal aesthetic styles
      components/
        RiskConsole.tsx          # VaR, CVaR, Sharpe, limit bars
        PortfolioOverview.tsx    # P&L, positions, exposure bars
        SystemHealth.tsx         # IB, data feeds, connectivity status
        StrategyCommand.tsx      # Deploy, backtest commands
        ApprovalQueue.tsx        # CIO approval interface + kill switch
        AlertFeed.tsx            # Scrolling alert list
  ib-gateway/                   # Custom IB Gateway Docker image (Ubuntu + IBC + noVNC)
  db/
    init.sql                    # TimescaleDB schema (hypertables for market_data, etc.)
```

## Key Architecture

### Strategy Plugin System
All strategies extend `BaseStrategy` from `api/strategies/base.py`.
Strategies define `data_requirements` and implement `compute_signals(universe, as_of) -> list[Signal]`.
Signals carry direction (long/short/close/hedge), confidence, and metadata.
The execution engine converts signals to orders after risk engine approval.

### Risk Management
Default limits: max position 10%, sector 30%, gross exposure 200%, net 50%, daily loss 2%, drawdown 10%, VaR 3%.
Warning thresholds at 80% of limits. Kill switch with configurable triggers (max drawdown, daily loss, data failure, IB disconnect, manual).

### Data Ingestion (Worker)
Rate-aware scheduling with per-source budgets:
Alpaca (5min), yfinance (30min), Finnhub (15min), Alpha Vantage (60min, 2 tickers/day rotating),
StockTwits (20min), SEC EDGAR (60min). All published to Redis Streams.

### Control Room UI
6-panel CSS Grid layout with dark terminal aesthetic. Real-time WebSocket connection to API.
Market status detection (EST 9:30-16:00). Kill switch button in Approvals panel.

## Testing

- **Python**: pytest
- **Frontend**: Vitest
- Tests must pass before opening a PR

## Conventions

- Python: type hints everywhere, async/await for all I/O
- No comments narrating what code obviously does
- One logical change per commit
- All work on `feat/` branches, never commit to main
- PR descriptions match change size (see .claude/writing-style.md)
- Live trading disabled by default (LIVE_TRADING_ENABLED=false)

## What to Avoid

- Do not over-engineer. Minimum change that works.
- Do not add error handling for scenarios that cannot happen.
- Do not touch .env files.
- Do not commit directly to main.
- Do not use em dashes in any written output.
- No proprietary strategy logic in this repo (belongs in icarus-research/).
- No hardcoded API keys or credentials.
