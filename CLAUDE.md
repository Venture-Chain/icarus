# Icarus: Quantitative Trading Framework

Quantitative trading platform with multi-broker orchestration, pluggable strategies, and real-time
risk controls. Built by Venture Chain (Apache 2.0). Deploy strategies to IB, Alpaca, or multiple
accounts simultaneously. Users implement their own strategies via the plugin system.

Proprietary research lives in `research/` (gitignored, separate repo).

## Stack

- **API**: Python 3.12, FastAPI, SQLAlchemy 2.0 (async via asyncpg)
- **Database**: PostgreSQL + TimescaleDB 16 (time-series hypertables)
- **Cache/Streams**: Redis 7 (caching + Redis Streams for real-time events)
- **UI**: React 19 + TypeScript 5.9 + Vite (Control Room dashboard, terminal aesthetic)
- **ML**: XGBoost/LightGBM for strategy models, FinBERT for sentiment (GPU via host)
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
| ib-gateway | 5104 | IB API |
| ib-gateway | 5105 | noVNC web UI (login + 2FA) |
| icarus-worker | (bg) | Data ingestion |

## Project Structure

```
icarus/
  api/
    main.py                     # FastAPI app setup, routers, WebSocket
    config.py                   # Settings from environment
    routers/
      strategy.py               # Strategy registration, deployment
      portfolio.py              # Positions, risk metrics, kill-switch
      data.py                   # Price, news, sentiment, filings, fundamentals, smart money
      research.py               # Backtest, research logging
    engines/
      strategy_engine.py        # Strategy plugin loader and signal generation
      risk_engine.py            # VaR, CVaR, limits, kill-switch
      execution_engine.py       # Signal-to-order conversion, sizing, broker placement
      backtest_engine.py        # Walk-forward testing, survivorship bias handling
      portfolio_optimizer.py    # Mean-variance, risk parity, Black-Litterman
      cost_model.py             # Commission, slippage, tiered pricing
      sensitivity_engine.py     # Stress testing, scenario analysis
      quantum_engine.py         # Quantum finance (HLQuantum integration)
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
    models/
  worker/
    main.py                     # Async data pulls from all sources (rate-aware scheduling)
    db_writer.py                # Writes to PostgreSQL
  ui/
    src/
      App.tsx                   # Main layout (6-panel grid)
      App.css                   # Terminal aesthetic styles
      components/
        RiskConsole.tsx          # VaR, CVaR, Sharpe, limit bars
        PortfolioOverview.tsx    # P&L, positions, exposure bars
        SystemHealth.tsx         # IB, data feeds, connectivity status
        StrategyCommand.tsx      # Deploy, backtest commands
        KillSwitch.tsx           # Emergency kill switch
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
Default limits: max position 5%, daily loss 2%, drawdown 10%, max 3 concurrent positions.
No overnight positions (hard flatten at 3:55 PM EST). Kill switch for emergency flatten.

### Data Ingestion (Worker)
Rate-aware scheduling with per-source budgets:
Alpaca (5min), yfinance (30min), Finnhub (15min), Alpha Vantage (60min, 2 tickers/day rotating),
StockTwits (20min), SEC EDGAR (60min). All published to Redis Streams.

### Control Room UI
6-panel CSS Grid layout with dark terminal aesthetic. Real-time WebSocket connection to API.
Market status detection (EST 9:30-16:00). Kill switch in dedicated panel.

## Testing

- **Python**: pytest
- **Frontend**: Vitest
- Tests must pass before opening a PR

## Conventions

- Python: type hints everywhere, async/await for all I/O
- No comments narrating what code obviously does
- One logical change per commit
- Commit messages follow .claude/writing-style.md
- Live trading disabled by default (LIVE_TRADING_ENABLED=false)

## What to Avoid

- Do not over-engineer. Minimum change that works.
- Do not add error handling for scenarios that cannot happen.
- Do not touch .env files.
- Do not commit directly to main.
- Do not use em dashes in any written output.
- No proprietary strategy logic in this repo (belongs in research/).
- No hardcoded API keys or credentials.
