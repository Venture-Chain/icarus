"""
Virtual portfolio for paper trading.
Simulates position management, P&L tracking, and performance metrics.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime

log = logging.getLogger("icarus.virtual-portfolio")


@dataclass
class VirtualPosition:
    ticker: str
    quantity: float
    entry_price: float
    current_price: float = 0
    direction: str = "long"
    opened_at: datetime = field(default_factory=datetime.utcnow)
    stop_price: float = 0
    target_price: float = 0

    @property
    def unrealized_pnl(self) -> float:
        if self.direction == "long":
            return (self.current_price - self.entry_price) * self.quantity
        return (self.entry_price - self.current_price) * self.quantity

    @property
    def market_value(self) -> float:
        return self.current_price * self.quantity


class VirtualPortfolio:
    """Simulates a trading account for paper trading."""

    def __init__(self, capital: float = 10000):
        self.initial_capital = capital
        self.cash = capital
        self.positions: dict[str, VirtualPosition] = {}
        self.realized_pnl = 0
        self.total_trades = 0
        self.winning_trades = 0
        self.peak_nav = capital
        self.daily_pnl = 0
        self._day_marker = None

    @property
    def nav(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    @property
    def drawdown(self) -> float:
        current_nav = self.nav
        if current_nav > self.peak_nav:
            self.peak_nav = current_nav
        if self.peak_nav == 0:
            return 0
        return (self.peak_nav - current_nav) / self.peak_nav

    def process_signal(self, signal) -> bool:
        """Process a trading signal. Returns True if action was taken."""
        ticker = signal.ticker
        direction = signal.direction
        metadata = signal.metadata or {}

        if direction == "close":
            return self._close_position(ticker)

        if direction in ("long", "short"):
            if ticker in self.positions:
                return False  # already in position

            entry = metadata.get("entry", 0)
            stop = metadata.get("stop", 0)
            target = metadata.get("target", 0)

            if not entry or entry <= 0:
                return False

            # Position sizing: use 5% of capital or confidence-based
            size_pct = 0.05
            position_value = self.cash * size_pct
            quantity = position_value / entry

            if quantity <= 0 or position_value > self.cash:
                return False

            self.positions[ticker] = VirtualPosition(
                ticker=ticker,
                quantity=quantity,
                entry_price=entry,
                current_price=entry,
                direction=direction,
                stop_price=stop,
                target_price=target,
            )
            self.cash -= position_value
            self.total_trades += 1
            return True

        return False

    def _close_position(self, ticker: str) -> bool:
        pos = self.positions.pop(ticker, None)
        if not pos:
            return False

        pnl = pos.unrealized_pnl
        self.realized_pnl += pnl
        self.daily_pnl += pnl
        self.cash += pos.market_value

        if pnl > 0:
            self.winning_trades += 1

        log.info("closed %s: PnL %.2f", ticker, pnl)
        return True

    def mark_to_market(self, prices: dict[str, float]):
        """Update current prices for all positions."""
        for ticker, pos in self.positions.items():
            if ticker in prices:
                pos.current_price = prices[ticker]

    def check_stops(self) -> list[str]:
        """Check if any positions hit stop or target. Returns tickers to close."""
        to_close = []
        for ticker, pos in self.positions.items():
            if pos.stop_price and pos.current_price <= pos.stop_price:
                to_close.append(ticker)
            elif pos.target_price and pos.current_price >= pos.target_price:
                to_close.append(ticker)
        return to_close

    def flatten(self) -> int:
        """Close all positions. Returns count of positions closed."""
        tickers = list(self.positions.keys())
        for ticker in tickers:
            self._close_position(ticker)
        return len(tickers)

    def stats(self) -> dict:
        """Current portfolio statistics."""
        today = datetime.utcnow().date()
        if self._day_marker != today:
            self._day_marker = today
            self.daily_pnl = 0

        return {
            "nav": self.nav,
            "cash": self.cash,
            "positions_count": len(self.positions),
            "unrealized_pnl": sum(p.unrealized_pnl for p in self.positions.values()),
            "realized_pnl": self.realized_pnl,
            "drawdown": self.drawdown,
            "total_trades": self.total_trades,
            "win_rate": self.winning_trades / self.total_trades if self.total_trades > 0 else 0,
            "daily_pnl": self.daily_pnl,
            "positions": {
                t: {
                    "quantity": p.quantity,
                    "entry": p.entry_price,
                    "current": p.current_price,
                    "pnl": p.unrealized_pnl,
                    "direction": p.direction,
                }
                for t, p in self.positions.items()
            },
        }
