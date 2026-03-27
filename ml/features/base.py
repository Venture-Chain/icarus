"""
Feature engineering base and common features.
All features must be point-in-time computable.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass
class Feature:
    name: str
    values: np.ndarray
    lookback: int


class BaseFeatureBuilder(ABC):
    """All feature builders implement this interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def compute(self, prices: np.ndarray, volumes: np.ndarray | None = None) -> Feature:
        ...


class ReturnsFeature(BaseFeatureBuilder):
    """Simple returns over various horizons."""

    def __init__(self, period: int = 1):
        self.period = period

    @property
    def name(self) -> str:
        return f"returns_{self.period}d"

    def compute(self, prices: np.ndarray, volumes: np.ndarray | None = None) -> Feature:
        returns = np.zeros(len(prices))
        returns[self.period:] = (prices[self.period:] - prices[:-self.period]) / prices[:-self.period]
        return Feature(name=self.name, values=returns, lookback=self.period)


class VolatilityFeature(BaseFeatureBuilder):
    """Rolling realized volatility."""

    def __init__(self, window: int = 20):
        self.window = window

    @property
    def name(self) -> str:
        return f"volatility_{self.window}d"

    def compute(self, prices: np.ndarray, volumes: np.ndarray | None = None) -> Feature:
        returns = np.diff(prices) / prices[:-1]
        vol = np.zeros(len(prices))
        for i in range(self.window, len(returns)):
            vol[i + 1] = np.std(returns[i - self.window:i]) * np.sqrt(252)
        return Feature(name=self.name, values=vol, lookback=self.window)


class MomentumFeature(BaseFeatureBuilder):
    """Price momentum (rate of change)."""

    def __init__(self, period: int = 20):
        self.period = period

    @property
    def name(self) -> str:
        return f"momentum_{self.period}d"

    def compute(self, prices: np.ndarray, volumes: np.ndarray | None = None) -> Feature:
        mom = np.zeros(len(prices))
        mom[self.period:] = (prices[self.period:] / prices[:-self.period]) - 1
        return Feature(name=self.name, values=mom, lookback=self.period)


class RSIFeature(BaseFeatureBuilder):
    """Relative Strength Index."""

    def __init__(self, period: int = 14):
        self.period = period

    @property
    def name(self) -> str:
        return f"rsi_{self.period}"

    def compute(self, prices: np.ndarray, volumes: np.ndarray | None = None) -> Feature:
        returns = np.diff(prices)
        rsi = np.full(len(prices), 50.0)

        for i in range(self.period + 1, len(prices)):
            window = returns[i - self.period:i]
            gains = window[window > 0]
            losses = -window[window < 0]
            avg_gain = np.mean(gains) if len(gains) > 0 else 0
            avg_loss = np.mean(losses) if len(losses) > 0 else 0
            if avg_loss == 0:
                rsi[i] = 100
            else:
                rs = avg_gain / avg_loss
                rsi[i] = 100 - (100 / (1 + rs))

        return Feature(name=self.name, values=rsi, lookback=self.period)


class VolumeRatioFeature(BaseFeatureBuilder):
    """Volume relative to rolling average."""

    def __init__(self, window: int = 20):
        self.window = window

    @property
    def name(self) -> str:
        return f"volume_ratio_{self.window}d"

    def compute(self, prices: np.ndarray, volumes: np.ndarray | None = None) -> Feature:
        if volumes is None:
            return Feature(name=self.name, values=np.ones(len(prices)), lookback=self.window)

        ratio = np.ones(len(volumes))
        for i in range(self.window, len(volumes)):
            avg_vol = np.mean(volumes[i - self.window:i])
            if avg_vol > 0:
                ratio[i] = volumes[i] / avg_vol

        return Feature(name=self.name, values=ratio, lookback=self.window)


# Default feature set for most models
DEFAULT_FEATURES = [
    ReturnsFeature(1),
    ReturnsFeature(5),
    ReturnsFeature(20),
    VolatilityFeature(20),
    MomentumFeature(10),
    MomentumFeature(20),
    RSIFeature(14),
    VolumeRatioFeature(20),
]
