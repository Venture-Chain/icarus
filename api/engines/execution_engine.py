"""
Order execution engine.
Converts signals to orders after risk engine approval.
Handles position sizing and order lifecycle.
Routes orders to the correct broker via AccountRegistry.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from engines.cost_model import CostModel
from engines.risk_engine import Position, RiskEngine

log = logging.getLogger("icarus.execution")


class SizingMethod(str, Enum):
    FIXED_FRACTIONAL = "fixed_fractional"
    EQUAL_WEIGHT = "equal_weight"
    RISK_PARITY = "risk_parity"
    KELLY = "kelly"


@dataclass
class OrderRequest:
    ticker: str
    direction: str  # long, short, close
    order_type: str = "MKT"
    limit_price: float | None = None
    quantity: float | None = None  # if None, auto-size
    strategy_id: int | None = None


@dataclass
class OrderResult:
    order_id: str | None = None
    account_id: str = ""
    status: str = "pending"
    ticker: str = ""
    direction: str = ""
    quantity: float = 0
    estimated_cost: float = 0
    rejection_reason: str = ""


class ExecutionEngine:
    """Convert signals to orders with risk checks and position sizing."""

    def __init__(
        self,
        account_registry=None,
        risk_engine: RiskEngine | None = None,
        cost_model: CostModel | None = None,
        ib_client=None,
    ):
        self.registry = account_registry
        self.risk_engine = risk_engine or RiskEngine()
        self.cost_model = cost_model or CostModel()
        self.live_trading = False

        # Backward compat: wrap a bare ib_client in a registry
        if ib_client and not account_registry:
            from services.account_registry import AccountRegistry
            self.registry = AccountRegistry()
            self.registry.register(ib_client)

    def _resolve_broker(self, account_id: str | None = None):
        """Get broker by account_id, or first available."""
        if not self.registry:
            return None
        if account_id:
            return self.registry.get(account_id)
        # Default: first connected broker
        for broker in self.registry.all():
            if broker.connected:
                return broker
        return None

    async def execute_signal(
        self,
        signal,
        positions: list[Position],
        portfolio_value: float,
        current_price: float,
        account_id: str | None = None,
    ) -> OrderResult:
        """Process a signal through risk checks and execute."""
        result = OrderResult(ticker=signal.ticker, direction=signal.direction)

        # Calculate quantity if not specified
        quantity = self._size_position(
            signal, portfolio_value, current_price, len(positions)
        )
        if quantity == 0:
            result.status = "rejected"
            result.rejection_reason = "position size calculated as zero"
            return result

        result.quantity = quantity

        # Risk check
        approved, reason, checks = self.risk_engine.check_signal(
            signal_ticker=signal.ticker,
            signal_direction=signal.direction,
            signal_quantity=quantity,
            signal_price=current_price,
            positions=positions,
            portfolio_value=portfolio_value,
        )

        if not approved:
            result.status = "rejected"
            result.rejection_reason = reason
            log.info(f"signal rejected for {signal.ticker}: {reason}")
            return result

        # Estimate cost
        cost = self.cost_model.estimate(
            signal.ticker, quantity, current_price,
            "sell" if signal.direction == "short" else "buy",
        )
        result.estimated_cost = cost.total

        # Route to broker
        broker = self._resolve_broker(account_id)
        if broker and broker.connected:
            action = "SELL" if signal.direction in ("short", "close") else "BUY"
            order = await broker.place_order(
                ticker=signal.ticker,
                action=action,
                quantity=quantity,
                order_type="MKT",
            )
            result.order_id = order.broker_order_id
            result.account_id = broker.account_id
            result.status = "submitted"
            log.info(
                "order submitted: %s %s %s -> %s",
                action, quantity, signal.ticker, broker.account_id,
            )
        else:
            result.status = "simulated"
            log.info(f"simulated: {signal.direction} {quantity} {signal.ticker} @ {current_price}")

        return result

    def _size_position(
        self,
        signal,
        portfolio_value: float,
        price: float,
        current_positions: int,
        method: str = "fixed_fractional",
    ) -> float:
        """Calculate position size."""
        if portfolio_value <= 0 or price <= 0:
            return 0

        max_position = portfolio_value * self.risk_engine.limits.max_position_pct

        if method == "equal_weight":
            target_count = 20
            per_position = portfolio_value / target_count
            shares = int(min(per_position, max_position) / price)
        elif method == "kelly":
            # Simplified Kelly: f = confidence (bounded)
            kelly_fraction = min(signal.confidence * 0.5, 0.1)
            shares = int((portfolio_value * kelly_fraction) / price)
        else:
            # Fixed fractional: use risk budget
            risk_budget = getattr(signal, "risk_budget", 0.02)
            position_value = portfolio_value * risk_budget
            shares = int(min(position_value, max_position) / price)

        return max(shares, 0)

    async def flatten_account(self, account_id: str) -> list[OrderResult]:
        """Flatten all positions for a specific broker account."""
        broker = self._resolve_broker(account_id)
        if not broker or not broker.connected:
            return []

        positions = await broker.get_positions()
        results = []
        for pos in positions:
            if pos.quantity == 0:
                continue
            action = "SELL" if pos.quantity > 0 else "BUY"
            order = await broker.place_order(
                ticker=pos.ticker,
                action=action,
                quantity=abs(pos.quantity),
                order_type="MKT",
            )
            results.append(OrderResult(
                order_id=order.broker_order_id,
                account_id=account_id,
                ticker=pos.ticker,
                direction="close",
                quantity=abs(pos.quantity),
                status=order.status,
            ))
            log.warning("flatten %s: %s %s %s", account_id, action, abs(pos.quantity), pos.ticker)
        return results

    async def flatten_all(self) -> dict[str, list[OrderResult]]:
        """Emergency: flatten all positions across all broker accounts."""
        if not self.registry:
            return {}
        results = {}
        for broker in self.registry.all():
            account_results = await self.flatten_account(broker.account_id)
            if account_results:
                results[broker.account_id] = account_results
        return results
