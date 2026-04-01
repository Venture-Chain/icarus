# Icarus

Open-source quantitative trading framework. Monitor your portfolio, automate day trading strategies, and research markets with smart money data, sentiment analysis, and AI-assisted workflows.

Built by [Venture Chain](https://venture-chain.com). Apache 2.0.

## What Icarus Does

- **Portfolio Monitoring**: Connect Interactive Brokers for read-only portfolio tracking, P&L, and risk metrics
- **Automated Day Trading**: Deploy strategies to Alpaca (zero commission) with paper and live modes
- **Three-Layer Algorithm**: Pattern scanner + ML confidence filter (XGBoost) + context check (news, sentiment, smart money rules)
- **Smart Money Data**: Dark pool volume (FINRA ATS), congressional trades, insider Form 4 purchases, short interest
- **Sentiment Analysis**: FinBERT GPU-accelerated scoring on every news headline
- **Confluence Scoring**: 0-100 conviction score combining all smart money signals
- **Risk Controls**: No overnight positions (hard flatten at 3:55 PM ET), 2% daily loss limit, max 3 concurrent positions, emergency kill switch
- **Research Tools**: Walk-forward backtesting, Monte Carlo projections, scenario analysis (bull/bear/recession/rate hike)
- **AI Skills**: 16 Claude agent skills for market reports, portfolio status, risk checks, research workflows, and more
- **Control Room**: React dashboard with real-time WebSocket updates, terminal aesthetic

## What Icarus Does NOT Do

Icarus is a framework, not a strategy. It does not ship with strategies that make money.
The example strategies (MA crossover, mean reversion) are educational.
You bring the alpha. Proprietary strategies go in `research/` (gitignored).

## Architecture

```
┌─────────────────────────────────────────────┐
│           Control Room (React + Vite)        │
└──────────────────┬──────────────────────────┘
                   │ REST + WebSocket
┌──────────────────┴──────────────────────────┐
│             Icarus API (FastAPI)              │
│  Data · Strategy · Risk · Notifications      │
└──┬─────┬─────┬──────┬──────┬───────┬────────┘
   │     │     │      │      │       │
┌──▼──┐ ┌▼───┐ ┌▼────┐ ┌▼────┐ ┌▼──────┐ ┌▼──────┐
│ IB  │ │Time│ │Redis│ │Work-│ │Runner │ │News & │
│ GW  │ │scal│ │     │ │er   │ │       │ │Smart$ │
│     │ │eDB │ │     │ │+Fin │ │Strat  │ │Monit- │
│read │ │    │ │pub/ │ │BERT │ │exec + │ │ors    │
│only │ │24  │ │sub  │ │GPU  │ │paper  │ │       │
└─────┘ │tbl │ └─────┘ └─────┘ └───────┘ └───────┘
        └────┘
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

Place it in `api/strategies/` for auto-discovery. Private strategies go in `research/strategies/` (gitignored).

## Deploying a Strategy

```bash
# List available strategies
curl http://localhost:5100/strategies/

# Deploy to paper trading
curl -X PUT http://localhost:5100/strategies/my_strategy/deploy \
  -H "Content-Type: application/json" \
  -d '{"mode": "paper", "account_id": "alpaca-paper", "universe": ["RKLB", "LUNR", "ASTS"], "capital": 10000}'
```

The runner executes during market hours, flattens all positions at 3:55 PM ET, and saves performance snapshots every 5 minutes.

## Services

| Service | Port | Purpose |
|---|---|---|
| Icarus API | 5100 | FastAPI REST + WebSocket |
| Control Room | 5101 | React dashboard |
| TimescaleDB | 5102 | Time-series database (24 tables) |
| Redis | 5103 | Cache + streams + pub/sub |
| IB Gateway | 5104 | Interactive Brokers API |
| IB Gateway VNC | 5105 | Browser UI for IB login + 2FA |
| Worker | (bg) | Data ingestion + FinBERT sentiment |
| Runner | (bg) | Strategy execution + paper trading |
| News Monitor | (bg) | 24/7 news alert generation |
| Smart Money Monitor | (bg) | Dark pool + congressional trade alerts |

## Data Sources

| Source | Data | Update Frequency |
|---|---|---|
| Alpaca | 1-min and 5-min price bars | Real-time during market hours |
| Finnhub | News, fundamentals, economic calendar | 5 min (news), daily (calendar) |
| FINRA ATS | Dark pool volume | Weekly (Saturday) |
| Quiver Quant | Congressional trades, short interest | Daily |
| SEC EDGAR | Insider Form 4 filings | Daily |
| Alpha Vantage | Fallback price data | 60 min |

## AI Agent Skills

Icarus ships with 16 Claude agent skills for AI-assisted workflows:

| Skill | What it does |
|---|---|
| `/market-open` | Morning briefing: overnight news, pre-market, smart money alerts |
| `/market-close` | End-of-day wrap: P&L, trades, flatten confirmation |
| `/market-report` | 10-section comprehensive market analysis |
| `/portfolio-status` | Positions, risk metrics, news on holdings |
| `/risk-check` | Limit utilization, VaR, stress scenarios |
| `/strategies` | Algorithm status, deployments, performance |
| `/smart-money` | Dark pool, congressional, insider, confluence review |
| `/notifications` | Triage alerts by severity and type |
| `/backtest` | Run and analyze a backtest |
| `/projection` | Monte Carlo and scenario analysis |
| `/research` | Full stock research with smart money confluence |
| `/hypothesis` | Test a trading hypothesis with data |
| `/deploy-strategy` | Deploy a strategy to paper or live |
| `/regime` | Market regime analysis (VIX, sectors, breadth) |
| `/universe` | Manage the algorithm's ticker universe |
| `/weekly-review` | Weekly performance and pattern analysis |

## Tech Stack

- **Python 3.12** + FastAPI (async, asyncpg for DB)
- **PostgreSQL 16** + TimescaleDB (time-series hypertables)
- **Redis 7** (cache + streams + pub/sub)
- **React 19** + TypeScript + Vite
- **XGBoost / LightGBM** for ML models
- **FinBERT** (ProsusAI/finbert) for GPU sentiment analysis
- **Interactive Brokers** (read-only) + **Alpaca** (automated trading)
- **Docker Compose** for local dev

## License

Apache 2.0. See [LICENSE](LICENSE).
