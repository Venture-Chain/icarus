"""
Order execution engine.
Converts signals to IB orders after risk engine approval.
Handles position sizing and order lifecycle.
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
    order_id: int | None = None
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
        ib_client=None,
        risk_engine: RiskEngine | None = None,
        cost_model: CostModel | None = None,
    ):
        self.ib_client = ib_client
        self.risk_engine = risk_engine or RiskEngine()
        self.cost_model = cost_model or CostModel()
        self.live_trading = False

    async def execute_signal(
        self,
        signal,
        positions: list[Position],
        portfolio_value: float,
        current_price: float,
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

        # Execute via IB
        if self.ib_client and self.ib_client.connected:
            action = "SELL" if signal.direction in ("short", "close") else "BUY"
            order_result = await self.ib_client.place_order(
                ticker=signal.ticker,
                action=action,
                quantity=quantity,
                order_type="MKT",
            )
            result.order_id = order_result.get("order_id")
            result.status = "submitted"
            log.info(f"order submitted: {action} {quantity} {signal.ticker}")
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

    async def flatten_all(self, positions: list[Position]) -> list[OrderResult]:
        """Emergency: close all positions. Used by kill switch."""
        results = []
        for pos in positions:
            if pos.quantity == 0:
                continue

            action = "SELL" if pos.quantity > 0 else "BUY"
            quantity = abs(pos.quantity)

            result = OrderResult(
                ticker=pos.ticker,
                direction="close",
                quantity=quantity,
            )

            if self.ib_client and self.ib_client.connected:
                order_result = await self.ib_client.place_order(
                    ticker=pos.ticker,
                    action=action,
                    quantity=quantity,
                    order_type="MKT",
                )
                result.order_id = order_result.get("order_id")
                result.status = "submitted"
            else:
                result.status = "simulated"

            results.append(result)
            log.warning(f"flatten: {action} {quantity} {pos.ticker}")

        return results
