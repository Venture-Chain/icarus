# Icarus

Open-source quantitative trading framework with Interactive Brokers integration.

Built by [Venture Chain](https://venturechain.co).

## What Icarus Does

Icarus is the infrastructure for running a systematic trading operation:

- **Strategy Framework**: Plugin system for creating and testing trading strategies
- **Backtesting Engine**: Walk-forward testing with point-in-time data, survivorship bias handling, and full IBKR cost modeling
- **Risk Engine**: VaR, CVaR, stress testing, position limits, and an automatic kill switch
- **Portfolio Optimizer**: Mean-variance, risk parity, Black-Litterman, minimum variance
- **Hedging**: Beta hedging, sector hedging, pair trading
- **ML Pipeline**: PyTorch + CUDA for price prediction, volatility forecasting, regime detection
- **Data Connectors**: Finnhub, Alpha Vantage, yfinance, SEC EDGAR, Reddit, StockTwits
- **Execution**: IB Gateway integration for paper and live trading
- **Control Room**: React dashboard for monitoring, risk limits, kill switch, and CIO approvals
- **AI Integration**: Built-in Claude skill definitions for AI-driven research workflows

## What Icarus Does NOT Do

Icarus is a framework, not a strategy. It does not ship with strategies that make money.
The example strategies (MA crossover, mean reversion) are educational.
You bring the alpha.

## Architecture

```
┌──────────────────────────────────────┐
│          Control Room (React)         │
└──────────────┬───────────────────────┘
               │ REST + WebSocket
┌──────────────┴───────────────────────┐
│            Icarus API (FastAPI)        │
│  Strategy · Risk · Execution · ML     │
└──┬────────┬────────┬────────┬────────┘
   │        │        │        │
┌──▼──┐ ┌──▼──┐ ┌───▼──┐ ┌──▼───┐
│ IB  │ │Time-│ │Redis │ │Worker│
│ GW  │ │scale│ │      │ │      │
└─────┘ └─────┘ └──────┘ └──────┘
```

## Quick Start

1. Copy `.env.example` to `.env` and fill in your API keys
2. Start the stack:

```bash
docker compose up
```

3. Open the Control Room: http://localhost:5101
4. API docs: http://localhost:5100/docs

## Creating a Strategy

```python
from strategies.base import BaseStrategy, Signal, DataRequirement

class MyStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "my_strategy"

    @property
    def description(self) -> str:
        return "My custom strategy"

    def required_data(self) -> list[DataRequirement]:
        return [DataRequirement(data_type="prices", lookback_days=200)]

    def compute_signals(self, universe, as_of) -> list[Signal]:
        # Your logic here
        return []
```

Place it in `api/strategies/` and it will be auto-discovered.

## Ports

| Service | Port |
|---|---|
| Icarus API | 5100 |
| Control Room | 5101 |
| TimescaleDB | 5102 |
| Redis | 5103 |
| IB Gateway | 5104 |

## Tech Stack

- **Python 3.12** + FastAPI
- **PostgreSQL** + TimescaleDB
- **Redis** 7 (cache + streams)
- **React** + TypeScript + Vite
- **PyTorch** + CUDA
- **Interactive Brokers** (official ibapi)
- **Docker Compose**

## License

Apache 2.0. See [LICENSE](LICENSE).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
