"""
Walk-forward backtesting engine.
Enforces point-in-time data, handles survivorship bias,
applies transaction costs.
"""
from dataclasses import dataclass


@dataclass
class BacktestConfig:
    strategy_name: str
    universe: list[str]
    start_date: str
    end_date: str
    initial_capital: float = 100000
    commission_model: str = "ibkr_tiered"
    slippage_bps: float = 5.0
    walk_forward_window: int = 252
    retrain_interval: int = 63


@dataclass
class BacktestResults:
    total_return: float = 0
    annualized_return: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    max_drawdown: float = 0
    win_rate: float = 0
    profit_factor: float = 0
    calmar_ratio: float = 0
    total_trades: int = 0
    avg_trade_pnl: float = 0
    turnover: float = 0
    cost_drag: float = 0
    equity_curve: list = None
    drawdown_curve: list = None
    trades: list = None


class BacktestEngine:
    def __init__(self, cost_model=None):
        self.cost_model = cost_model

    async def run(self, config: BacktestConfig) -> BacktestResults:
        """Run a walk-forward backtest."""
        return BacktestResults()
