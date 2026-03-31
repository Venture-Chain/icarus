"""
Base strategy interface. All strategies implement this.
Public framework: strategies in research/ extend this.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class Signal:
    ticker: str
    direction: str  # long, short, hedge, close
    instrument: str = "stock"  # stock, option, future, etf
    confidence: float = 0.0
    hedge_for: str | None = None
    sizing_method: str = "fixed_fractional"
    metadata: dict = field(default_factory=dict)


@dataclass
class DataRequirement:
    data_type: str  # prices, fundamentals, sentiment, filings, social
    lookback_days: int = 252
    sources: list[str] = field(default_factory=list)


class BaseStrategy(ABC):
    """All strategies must implement this interface."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @abstractmethod
    def required_data(self) -> list[DataRequirement]:
        """Declare what data this strategy needs."""
        ...

    @abstractmethod
    def compute_signals(self, universe: list[str], as_of: date) -> list[Signal]:
        """Generate signals for the given universe on the given date."""
        ...

    def parameters(self) -> dict:
        """Return current parameter values."""
        return {}
