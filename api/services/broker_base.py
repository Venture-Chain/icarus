"""
Broker abstraction layer.
Common interface for all broker implementations (IB, Alpaca, etc.).
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


class BrokerType(str, Enum):
    IB = "ib"
    ALPACA = "alpaca"


class AccountMode(str, Enum):
    PAPER = "paper"
    LIVE = "live"


@dataclass
class BrokerOrder:
    broker_order_id: str
    status: str  # submitted, filled, partial, cancelled, rejected
    ticker: str = ""
    action: str = ""  # BUY or SELL
    quantity: float = 0
    filled_quantity: float = 0
    avg_fill_price: float = 0
    account_id: str = ""


@dataclass
class BrokerPosition:
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float = 0
    market_value: float = 0
    unrealized_pnl: float = 0
    account_id: str = ""


@dataclass
class AccountSummary:
    account_id: str
    net_liquidation: float = 0
    buying_power: float = 0
    cash: float = 0
    unrealized_pnl: float = 0
    realized_pnl: float = 0
    gross_position_value: float = 0


class BaseBroker(ABC):
    """Abstract base class for all broker implementations."""

    @property
    @abstractmethod
    def broker_type(self) -> BrokerType: ...

    @property
    @abstractmethod
    def account_id(self) -> str: ...

    @property
    @abstractmethod
    def mode(self) -> AccountMode: ...

    @property
    @abstractmethod
    def connected(self) -> bool: ...

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to broker. Returns True on success."""
        ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def place_order(
        self,
        ticker: str,
        action: str,
        quantity: float,
        order_type: str = "MKT",
        limit_price: float | None = None,
    ) -> BrokerOrder: ...

    @abstractmethod
    async def cancel_order(self, broker_order_id: str) -> BrokerOrder: ...

    @abstractmethod
    async def get_positions(self) -> list[BrokerPosition]: ...

    @abstractmethod
    async def get_account_summary(self) -> AccountSummary: ...

    @abstractmethod
    async def get_order_status(self, broker_order_id: str) -> BrokerOrder: ...

    def health_check(self) -> dict:
        return {
            "broker_type": self.broker_type.value,
            "account_id": self.account_id,
            "mode": self.mode.value,
            "connected": self.connected,
        }
