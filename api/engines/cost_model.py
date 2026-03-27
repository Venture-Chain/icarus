"""
IBKR transaction cost model.
Commission, spread, slippage, regulatory fees.
"""
from dataclasses import dataclass


@dataclass
class TransactionCost:
    commission: float = 0
    spread_cost: float = 0
    slippage: float = 0
    sec_fee: float = 0
    taf_fee: float = 0
    total: float = 0


class CostModel:
    # IBKR tiered pricing
    COMMISSION_PER_SHARE = 0.005
    MIN_COMMISSION = 1.00
    MAX_COMMISSION_PCT = 0.005
    SEC_FEE_RATE = 0.0000278  # per dollar on sells
    TAF_FEE_RATE = 0.000166  # per share on sells

    def estimate(self, ticker: str, quantity: float, price: float, side: str) -> TransactionCost:
        """Estimate total transaction cost for a trade."""
        commission = max(
            self.MIN_COMMISSION,
            abs(quantity) * self.COMMISSION_PER_SHARE,
        )
        commission = min(commission, abs(quantity) * price * self.MAX_COMMISSION_PCT)

        sec_fee = 0
        taf_fee = 0
        if side == "sell":
            sec_fee = abs(quantity) * price * self.SEC_FEE_RATE
            taf_fee = abs(quantity) * self.TAF_FEE_RATE

        total = commission + sec_fee + taf_fee
        return TransactionCost(
            commission=commission,
            sec_fee=sec_fee,
            taf_fee=taf_fee,
            total=total,
        )
