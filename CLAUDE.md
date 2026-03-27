# Icarus: Quantitative Trading Framework

Open-source quantitative trading platform with Interactive Brokers integration.
Built by Venture Chain.

## Stack

- **API**: Python 3.12, FastAPI, SQLAlchemy
- **Database**: PostgreSQL + TimescaleDB
- **Cache/Streams**: Redis 7
- **UI**: React + TypeScript + Vite (Control Room dashboard)
- **ML**: PyTorch + CUDA
- **Broker**: Interactive Brokers (via official ibapi)
- **Data Sources**: Alpaca, Finnhub, Alpha Vantage, yfinance, SEC EDGAR, Reddit (PRAW), StockTwits

## Local Dev

```
docker compose up
```

| Service | Port | URL |
|---|---|---|
| Icarus API | 5100 | http://localhost:5100 |
| Control Room UI | 5101 | http://localhost:5101 |
| TimescaleDB | 5102 | localhost:5102 |
| Redis | 5103 | localhost:5103 |
| IB Gateway | 5104 | localhost:5104 |

## Project Structure

```
icarus/
  api/                    # FastAPI application
    routers/              # API endpoints
    engines/              # Core engines (risk, strategy, execution, backtest, ML)
    services/             # Data source connectors
    strategies/           # Strategy plugins (base + examples)
    models/               # SQLAlchemy models
  worker/                 # Data ingestion worker
  ml/                     # ML training and inference
  ui/                     # React Control Room
  ib-gateway/             # Custom IB Gateway Docker image
  db/                     # Database init scripts
```

## Strategy Plugin Interface

All strategies extend `BaseStrategy` from `api/strategies/base.py`.
Strategies emit Signals (not orders). The execution engine converts signals to orders after risk engine approval.

## Testing

- **Python**: pytest
- **Frontend**: Vitest
- Tests must pass before opening a PR

## Conventions

- Python: type hints everywhere, async where possible
- No comments narrating what code obviously does
- One logical change per commit
- All work on `feat/` branches, never commit to main
- PR descriptions match change size (see .claude/writing-style.md)

## What to Avoid

- Do not over-engineer. Minimum change that works.
- Do not add error handling for scenarios that cannot happen.
- Do not touch .env files.
- Do not commit directly to main.
- Do not use em dashes in any written output.
