"""
Example: Bollinger Band mean reversion strategy.
Educational only. Not intended for live trading.
"""
from datetime import date

from .base import BaseStrategy, DataRequirement, Signal


class MeanReversionExample(BaseStrategy):
    """Buy when price drops below lower Bollinger Band, sell at mean."""

    def __init__(self, period: int = 20, std_devs: float = 2.0):
        self.period = period
        self.std_devs = std_devs

    @property
    def name(self) -> str:
        return "example_mean_reversion"

    @property
    def description(self) -> str:
        return f"Bollinger mean reversion ({self.period}d, {self.std_devs}σ)"

    def required_data(self) -> list[DataRequirement]:
        return [
            DataRequirement(data_type="prices", lookback_days=self.period + 50)
        ]

    def compute_signals(self, universe: list[str], as_of: date) -> list[Signal]:
        signals = []
        return signals

    def parameters(self) -> dict:
        return {"period": self.period, "std_devs": self.std_devs}
