"""
Example: simple moving average crossover.
Educational only. Demonstrates the strategy interface.
"""
from datetime import date

import numpy as np

from .base import BaseStrategy, DataRequirement, Signal, SignalContext


class SimpleMomentumExample(BaseStrategy):
    """Long when fast MA > slow MA, close otherwise."""

    def __init__(self, fast_period: int = 50, slow_period: int = 200):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self._price_cache: dict[str, list[float]] = {}

    @property
    def name(self) -> str:
        return "example_momentum"

    @property
    def description(self) -> str:
        return f"MA crossover ({self.fast_period}/{self.slow_period})"

    def required_data(self) -> list[DataRequirement]:
        return [
            DataRequirement(data_type="prices", lookback_days=self.slow_period + 50)
        ]

    def set_price_data(self, ticker: str, closes: list[float]):
        """Inject historical close prices for backtesting."""
        self._price_cache[ticker] = closes

    def compute_signals(self, universe: list[str], as_of: date, context: SignalContext | None = None) -> list[Signal]:
        signals = []
        for ticker in universe:
            closes = self._price_cache.get(ticker, [])
            if len(closes) < self.slow_period:
                continue

            fast_ma = np.mean(closes[-self.fast_period:])
            slow_ma = np.mean(closes[-self.slow_period:])

            if fast_ma > slow_ma:
                spread = (fast_ma - slow_ma) / slow_ma
                signals.append(Signal(
                    ticker=ticker,
                    direction="long",
                    confidence=min(spread * 10, 1.0),
                    metadata={"fast_ma": float(fast_ma), "slow_ma": float(slow_ma)},
                ))
            elif fast_ma < slow_ma:
                signals.append(Signal(
                    ticker=ticker,
                    direction="close",
                    confidence=0.5,
                ))

        return signals

    def parameters(self) -> dict:
        return {"fast_period": self.fast_period, "slow_period": self.slow_period}
