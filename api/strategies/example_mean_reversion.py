"""
Example: Bollinger Band mean reversion.
Educational only. Demonstrates the strategy interface.
"""
from datetime import date

import numpy as np

from .base import BaseStrategy, DataRequirement, Signal, SignalContext


class MeanReversionExample(BaseStrategy):
    """Buy below lower band, sell above upper band, close at mean."""

    def __init__(self, period: int = 20, std_devs: float = 2.0):
        self.period = period
        self.std_devs = std_devs
        self._price_cache: dict[str, list[float]] = {}

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

    def set_price_data(self, ticker: str, closes: list[float]):
        """Inject historical close prices for backtesting."""
        self._price_cache[ticker] = closes

    def compute_signals(self, universe: list[str], as_of: date, context: SignalContext | None = None) -> list[Signal]:
        signals = []
        for ticker in universe:
            closes = self._price_cache.get(ticker, [])
            if len(closes) < self.period:
                continue

            window = closes[-self.period:]
            mean = np.mean(window)
            std = np.std(window)

            if std == 0:
                continue

            current = closes[-1]
            z_score = (current - mean) / std
            lower = mean - self.std_devs * std
            upper = mean + self.std_devs * std

            if current < lower:
                confidence = min(abs(z_score) / (self.std_devs * 2), 1.0)
                signals.append(Signal(
                    ticker=ticker,
                    direction="long",
                    confidence=confidence,
                    metadata={"z_score": float(z_score), "mean": float(mean)},
                ))
            elif current > upper:
                confidence = min(abs(z_score) / (self.std_devs * 2), 1.0)
                signals.append(Signal(
                    ticker=ticker,
                    direction="close",
                    confidence=confidence,
                    metadata={"z_score": float(z_score), "mean": float(mean)},
                ))

        return signals

    def parameters(self) -> dict:
        return {"period": self.period, "std_devs": self.std_devs}
