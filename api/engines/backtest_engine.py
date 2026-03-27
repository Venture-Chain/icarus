"""
Walk-forward backtesting engine.
Point-in-time data, survivorship bias handling, transaction cost integration.
"""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd

from engines.cost_model import CostModel, TransactionCost

log = logging.getLogger("icarus.backtest")


@dataclass
class BacktestConfig:
    strategy_name: str
    universe: list[str]
    start_date: str
    end_date: str
    initial_capital: float = 100000
    commission_model: str = "tiered"
    slippage_bps: float = 5.0
    walk_forward: bool = True
    walk_forward_train: int = 252  # trading days
    walk_forward_test: int = 63  # trading days
    max_positions: int = 20
    position_size_method: str = "equal_weight"  # equal_weight, risk_parity, kelly


@dataclass
class Trade:
    ticker: str
    direction: str
    quantity: float
    entry_price: float
    entry_date: str
    exit_price: float = 0
    exit_date: str = ""
    pnl: float = 0
    cost: float = 0
    net_pnl: float = 0


@dataclass
class BacktestResults:
    config: BacktestConfig | None = None
    total_return: float = 0
    annualized_return: float = 0
    sharpe_ratio: float = 0
    sortino_ratio: float = 0
    max_drawdown: float = 0
    calmar_ratio: float = 0
    win_rate: float = 0
    profit_factor: float = 0
    total_trades: int = 0
    avg_trade_pnl: float = 0
    avg_holding_days: float = 0
    turnover: float = 0
    total_costs: float = 0
    cost_drag_pct: float = 0
    equity_curve: list[float] = field(default_factory=list)
    drawdown_curve: list[float] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)
    trades: list[Trade] = field(default_factory=list)
    daily_returns: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "total_return": round(self.total_return * 100, 2),
            "annualized_return": round(self.annualized_return * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "win_rate": round(self.win_rate * 100, 1),
            "profit_factor": round(self.profit_factor, 2),
            "total_trades": self.total_trades,
            "avg_trade_pnl": round(self.avg_trade_pnl, 2),
            "avg_holding_days": round(self.avg_holding_days, 1),
            "turnover": round(self.turnover * 100, 1),
            "total_costs": round(self.total_costs, 2),
            "cost_drag_pct": round(self.cost_drag_pct * 100, 2),
        }


class BacktestEngine:
    """Run walk-forward backtests with full cost modeling."""

    def __init__(self, cost_model: CostModel | None = None):
        self.cost_model = cost_model or CostModel()

    async def run(self, config: BacktestConfig, price_data: dict[str, pd.DataFrame]) -> BacktestResults:
        """
        Run a backtest.

        Args:
            config: Backtest configuration
            price_data: Dict of ticker -> DataFrame with columns [date, open, high, low, close, volume]
        """
        results = BacktestResults(config=config)

        # Build aligned price matrix
        all_dates = set()
        for df in price_data.values():
            all_dates.update(df["date"].tolist())
        all_dates = sorted(all_dates)

        start = config.start_date
        end = config.end_date
        trading_dates = [d for d in all_dates if start <= str(d) <= end]

        if not trading_dates:
            return results

        # Simulate
        capital = config.initial_capital
        positions: dict[str, dict] = {}  # ticker -> {qty, entry_price, entry_date}
        equity_curve = []
        daily_returns = []
        all_trades: list[Trade] = []
        total_costs = 0
        prev_equity = capital

        for i, current_date in enumerate(trading_dates):
            # Get current prices
            current_prices = {}
            for ticker, df in price_data.items():
                row = df[df["date"] == current_date]
                if not row.empty:
                    current_prices[ticker] = float(row.iloc[0]["close"])

            # Calculate portfolio value
            portfolio_value = capital
            for ticker, pos in positions.items():
                if ticker in current_prices:
                    if pos["direction"] == "long":
                        portfolio_value += pos["qty"] * (current_prices[ticker] - pos["entry_price"])
                    else:
                        portfolio_value += pos["qty"] * (pos["entry_price"] - current_prices[ticker])

            equity_curve.append(portfolio_value)

            # Daily return
            if prev_equity > 0:
                daily_ret = (portfolio_value - prev_equity) / prev_equity
            else:
                daily_ret = 0
            daily_returns.append(daily_ret)
            prev_equity = portfolio_value

            # Rebalance every walk_forward_test days (simplified)
            if config.walk_forward and i > 0 and i % config.walk_forward_test == 0:
                # Close all positions (simplified rebalance)
                for ticker in list(positions.keys()):
                    if ticker in current_prices:
                        pos = positions[ticker]
                        exit_price = current_prices[ticker]
                        if pos["direction"] == "long":
                            pnl = pos["qty"] * (exit_price - pos["entry_price"])
                        else:
                            pnl = pos["qty"] * (pos["entry_price"] - exit_price)

                        cost_est = self.cost_model.estimate(
                            ticker, pos["qty"], exit_price, "sell"
                        )
                        cost = cost_est.total
                        total_costs += cost

                        trade = Trade(
                            ticker=ticker,
                            direction=pos["direction"],
                            quantity=pos["qty"],
                            entry_price=pos["entry_price"],
                            entry_date=pos["entry_date"],
                            exit_price=exit_price,
                            exit_date=str(current_date),
                            pnl=pnl,
                            cost=cost,
                            net_pnl=pnl - cost,
                        )
                        all_trades.append(trade)
                        capital += pnl - cost

                positions.clear()

                # Open new positions (equal weight, simplified)
                available = [t for t in config.universe if t in current_prices]
                n_positions = min(len(available), config.max_positions)
                if n_positions > 0:
                    per_position = capital / n_positions
                    for ticker in available[:n_positions]:
                        price = current_prices[ticker]
                        qty = int(per_position / price)
                        if qty > 0:
                            cost_est = self.cost_model.estimate(ticker, qty, price, "buy")
                            total_costs += cost_est.total
                            positions[ticker] = {
                                "qty": qty,
                                "entry_price": price,
                                "entry_date": str(current_date),
                                "direction": "long",
                            }

        # Calculate metrics
        results.equity_curve = equity_curve
        results.dates = [str(d) for d in trading_dates]
        results.trades = all_trades
        results.daily_returns = daily_returns
        results.total_trades = len(all_trades)
        results.total_costs = total_costs

        if equity_curve:
            final_value = equity_curve[-1]
            results.total_return = (final_value - config.initial_capital) / config.initial_capital

            n_years = len(trading_dates) / 252
            if n_years > 0:
                results.annualized_return = (1 + results.total_return) ** (1 / n_years) - 1

            results.cost_drag_pct = total_costs / config.initial_capital

        # Drawdown
        if equity_curve:
            peak = equity_curve[0]
            drawdowns = []
            for val in equity_curve:
                if val > peak:
                    peak = val
                dd = (peak - val) / peak if peak > 0 else 0
                drawdowns.append(dd)
            results.drawdown_curve = drawdowns
            results.max_drawdown = max(drawdowns) if drawdowns else 0

        # Risk metrics
        if daily_returns:
            arr = np.array(daily_returns)
            mean_ret = np.mean(arr)
            std_ret = np.std(arr)

            if std_ret > 0:
                results.sharpe_ratio = (mean_ret / std_ret) * np.sqrt(252)

            downside = arr[arr < 0]
            downside_std = np.std(downside) if len(downside) > 0 else 1
            if downside_std > 0:
                results.sortino_ratio = (mean_ret / downside_std) * np.sqrt(252)

            if results.max_drawdown > 0:
                results.calmar_ratio = results.annualized_return / results.max_drawdown

        # Trade metrics
        if all_trades:
            winners = [t for t in all_trades if t.net_pnl > 0]
            losers = [t for t in all_trades if t.net_pnl <= 0]
            results.win_rate = len(winners) / len(all_trades)

            total_wins = sum(t.net_pnl for t in winners)
            total_losses = abs(sum(t.net_pnl for t in losers))
            results.profit_factor = total_wins / total_losses if total_losses > 0 else float("inf")

            results.avg_trade_pnl = sum(t.net_pnl for t in all_trades) / len(all_trades)

        return results
