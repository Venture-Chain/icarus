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
| icarus-worker | (bg) | Data ingestion + FinBERT sentiment |
| icarus-runner | (bg) | Strategy runner + deployment engine |

## Project Structure

```
icarus/
  api/
    main.py                     # FastAPI app setup, routers, WebSocket
    config.py                   # Settings from environment
    routers/
      strategy.py               # Strategy registration, deployment, deploy flow
      portfolio.py              # Positions, risk metrics, kill-switch
      data.py                   # Price, news, sentiment, filings, fundamentals, smart money
      research.py               # Backtest, Monte Carlo projections, scenario analysis
      notifications.py          # Notification CRUD (list, unread count, mark read)
    engines/
      strategy_engine.py        # Strategy plugin loader and signal generation
      risk_engine.py            # VaR, CVaR, limits, kill-switch
      execution_engine.py       # Signal-to-order conversion, sizing, broker placement
      backtest_engine.py        # Walk-forward testing, survivorship bias handling
      portfolio_optimizer.py    # Mean-variance, risk parity, Black-Litterman
      cost_model.py             # Commission, slippage, tiered pricing
      sensitivity_engine.py     # Stress testing, scenario analysis
      quantum_engine.py         # Quantum finance (HLQuantum integration)
      confluence_engine.py      # Smart money confluence scoring (0-100 conviction)
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
      notifier.py               # Notification service (DB + Redis pub/sub)
    strategies/
      base.py                   # BaseStrategy + Signal + SignalContext + DataRequirement
      example_momentum.py       # MA crossover (educational)
      example_mean_reversion.py # Mean reversion (educational)
    models/
  worker/
    main.py                     # Data ingestion: 1-min bars, news, FinBERT, smart money, calendar
    db_writer.py                # Redis Streams consumer, writes to TimescaleDB
  runner/
    main.py                     # Strategy runner: deployments, flatten loop, snapshots
    virtual_portfolio.py        # Paper trading simulation
    news_monitor.py             # 24/7 news stream consumer, generates notifications
    smart_money_monitor.py      # Dark pool/congress/insider alert generator
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
Strategies define `required_data()` and implement `compute_signals(universe, as_of, context) -> list[Signal]`.
`SignalContext` carries trigger type, capital, market state, and confluence scores.
The runner manages deployments: scheduled execution, daily loss limits, end-of-day flatten.

### Three-Layer Trading Algorithm
1. Pattern Scanner (rule-based): breakouts, momentum, volume spikes
2. ML Confidence Filter (XGBoost): scores setup probability, threshold > 0.6
3. Context Check (data queries + rules): FinBERT news, sentiment, calendar, smart money

Strategy lives in `research/strategies/swing_pattern.py` (gitignored).

### Risk Management
Default limits: max position 5%, daily loss 2%, drawdown 10%, max 3 concurrent positions.
No overnight positions (hard flatten at 3:55 PM EST). Kill switch for emergency flatten.

### Smart Money Data
Dark pool volume (FINRA ATS weekly, Z-score), congressional trades (daily),
insider purchases (Form 4), short interest (daily). Confluence scoring 0-100.

### Data Ingestion (Worker)
1-min bars for universe tickers (RKLB, LUNR, ASTS, IONQ, RGTI), 5-min for broad watchlist.
FinBERT (ProsusAI/finbert) scores every headline inline on GPU.
News polling every 5 min (24/7). Economic calendar daily. Smart money sources on schedule.
All published to Redis Streams, consumed by db_writer, news_monitor, and smart_money_monitor.

### Notifications
Notifier service writes to DB + Redis pub/sub. WebSocket forwards to Control Room.
Types: news_alert, portfolio_alert, stop_triggered, risk_warning, smart_money, system.
Severities: info, warning, critical.

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
