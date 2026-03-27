"""
Example: simple moving average crossover momentum strategy.
Educational only. Not intended for live trading.
"""
from datetime import date

from .base import BaseStrategy, DataRequirement, Signal


class SimpleMomentumExample(BaseStrategy):
    """50/200 day moving average crossover. Long when 50 > 200, close otherwise."""

    def __init__(self, fast_period: int = 50, slow_period: int = 200):
        self.fast_period = fast_period
        self.slow_period = slow_period

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

    def compute_signals(self, universe: list[str], as_of: date) -> list[Signal]:
        # Placeholder: real implementation would compute MAs from price data
        signals = []
        return signals

    def parameters(self) -> dict:
        return {"fast_period": self.fast_period, "slow_period": self.slow_period}
