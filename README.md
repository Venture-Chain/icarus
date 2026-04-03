# Icarus

Open-source quantitative trading framework. Monitor your portfolio, automate trading strategies, and research markets with smart money data, sentiment analysis, and AI-assisted workflows.

Built by [Venture Chain](https://venture-chain.com). Apache 2.0.

## What Icarus Does

- **Multi-Strategy Trading**: Deploy multiple strategies simultaneously (day trading, sector rotation, VIX hedging) with independent risk controls per deployment
- **Broker-First Position Tracking**: Alpaca API is the source of truth for positions. The orders table provides deployment ownership mapping, but actual holdings are always verified against the broker
- **Three-Layer Algorithm**: Pattern scanner (breakouts, VWAP, opening range) + ML confidence filter (XGBoost) + context check (news, sentiment, smart money)
- **Smart Money Data**: Dark pool volume (FINRA ATS), congressional trades, insider Form 4 purchases, short interest, confluence scoring 0-100
- **Sentiment Analysis**: FinBERT GPU-accelerated scoring on every news headline
- **Risk Controls**: Per-deployment position limits, daily loss limits, hard EOD flatten at 3:55 PM ET for day trading, startup flatten safety net, emergency kill switch in header
- **Trade Journal**: Real-time signal and order logging with strategy attribution, displayed in the Control Room
- **Portfolio Optimization**: Mean-variance, risk parity, Black-Litterman, minimum variance, and Mean-CVaR (tail-risk-aware allocation via CVXPY)
- **Research Tools**: Walk-forward backtesting, Monte Carlo projections, scenario analysis, CVaR optimization endpoint
- **Control Room**: React dashboard with real-time WebSocket updates, terminal aesthetic

## What Icarus Does NOT Do

Icarus is a framework, not a strategy. It does not ship with trading strategies. You bring the alpha. Place your strategies in `research/strategies/` (gitignored) and the engine auto-discovers them at startup.

## Architecture

```
                    Control Room (React + Vite)
                           |
                    REST + WebSocket
                           |
                    Icarus API (FastAPI)
            Data . Strategy . Risk . Trade Log
           /       |         |        |        \
     IB Gateway  TimescaleDB  Redis  Worker    Runner
     (read-only) (24 tables)  (pub/  (+FinBERT (+strategies
      portfolio    signals,    sub,   GPU,      +broker orders
      monitoring)  orders,     cache) intraday  +flatten loop
                   market_data)       backfill) +snapshots)
```

## Quick Start

1. Copy `.env.example` to `.env` and configure:
   - `FINNHUB_API_KEY`: free tier at finnhub.io (news, calendar, fundamentals)
   - `ALPACA_API_KEY` + `ALPACA_API_SECRET`: free paper account at alpaca.markets
   - `BROKER_ACCOUNTS`: JSON array configuring IB and/or Alpaca (see below)

2. Start the stack:
```bash
docker compose up --build
```

3. If using IB, open the gateway UI at http://localhost:5105 and log in with 2FA

4. Open the Control Room: http://localhost:5101

5. API docs: http://localhost:5100/docs

## Broker Configuration

Set `BROKER_ACCOUNTS` in your `.env`:

```json
[
  {"broker": "ib", "id": "ib-main", "mode": "paper", "host": "ib-gateway", "port": 4003, "client_id": 1},
  {"broker": "alpaca", "id": "alpaca-paper", "mode": "paper", "key_field": "alpaca_paper_api_key", "secret_field": "alpaca_paper_api_secret"}
]
```

IB is read-only (portfolio monitoring). Alpaca handles automated trading. Use `"mode": "paper"` until your strategy proves itself.

## Creating a Strategy

```python
from strategies.base import BaseStrategy, Signal, SignalContext, DataRequirement

class MyStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    @property
    def description(self) -> str:
        return "My custom strategy"

    def required_data(self) -> list[DataRequirement]:
        return [DataRequirement(data_type="prices", lookback_days=200)]

    def compute_signals(self, universe, as_of, context: SignalContext | None = None) -> list[Signal]:
        # Your logic here
        return []
```

Place it in `research/strategies/` and the engine auto-discovers it at startup. Both the API and runner containers mount `./research:/research`. The `research/` directory is gitignored, so your strategies stay private.

Strategies are deployed via the `strategy_deployments` and `deployment_config` tables. Each deployment has its own universe, capital allocation, position limits, and overnight rules.

## Services

| Service | Port | Purpose |
|---|---|---|
| Icarus API | 5100 | FastAPI REST + WebSocket |
| Control Room | 5101 | React dashboard (5-panel grid, kill switch in header) |
| TimescaleDB | 5102 | Time-series database (market_data, signals, orders, deployments) |
| Redis | 5103 | Cache + streams + pub/sub |
| IB Gateway | 5104 | Interactive Brokers API (read-only) |
| IB Gateway VNC | 5105 | Browser UI for IB login + 2FA |
| Worker | (bg) | Data ingestion: 1-min bars, intraday backfill, FinBERT sentiment |
| Runner | (bg) | Strategy execution, broker orders, flatten loop, snapshots |

## Key Design Decisions

- **Broker is source of truth**: Positions are fetched from Alpaca each run cycle. The orders table is a log for deployment attribution, not state.
- **asyncpg binary protocol**: TimescaleDB writes use Python datetime objects, not SQL CAST strings. The `_parse_ts()` helper in db_writer handles all timestamp conversion.
- **Independent coroutines**: The runner uses `asyncio.gather(return_exceptions=True)` so the flatten loop survives even if the run loop or VIX updater crashes.
- **Startup flatten**: If the runner starts outside market hours and finds day trading positions still open, it flattens them immediately as a safety net.

## Data Sources

| Source | Data | Update Frequency |
|---|---|---|
| Alpaca | 1-min and 5-min price bars, order execution | Real-time during market hours |
| Finnhub | News, fundamentals, economic calendar | 5 min (news), daily (calendar) |
| yfinance | VIX (^VIX), fallback price data | 5 min |
| FINRA ATS | Dark pool volume | Weekly (Saturday) |
| Quiver Quant | Congressional trades, short interest | Daily |
| SEC EDGAR | Insider Form 4 filings | Daily |
| Alpha Vantage | Fallback price data | 60 min |

## Tech Stack

- **Python 3.12** + FastAPI (async, asyncpg for DB)
- **PostgreSQL 16** + TimescaleDB (time-series hypertables)
- **Redis 7** (cache + streams + pub/sub)
- **React 19** + TypeScript + Vite
- **CVXPY** + CLARABEL for convex portfolio optimization (Mean-CVaR)
- **XGBoost / LightGBM** for ML models
- **FinBERT** (ProsusAI/finbert) for GPU sentiment analysis
- **Interactive Brokers** (read-only) + **Alpaca** (automated trading)
- **Docker Compose** for local dev

## License

Apache 2.0. See [LICENSE](LICENSE).
