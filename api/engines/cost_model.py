"""
IBKR transaction cost model.
Commission (tiered + fixed), spread, slippage, regulatory fees, short borrow.
"""
from dataclasses import dataclass, field
from enum import Enum


class CommissionModel(str, Enum):
    TIERED = "tiered"
    FIXED = "fixed"


@dataclass
class TransactionCost:
    commission: float = 0
    spread_cost: float = 0
    slippage: float = 0
    sec_fee: float = 0
    taf_fee: float = 0
    short_borrow: float = 0
    total: float = 0

    def __post_init__(self):
        self.total = (
            self.commission + self.spread_cost + self.slippage
            + self.sec_fee + self.taf_fee + self.short_borrow
        )


@dataclass
class TickerCostProfile:
    """Per-ticker cost characteristics."""
    avg_spread_bps: float = 5.0
    avg_daily_volume: int = 1_000_000
    short_borrow_rate_annual: float = 0.005
    volatility: float = 0.02


class CostModel:
    """Estimate full transaction costs for trades."""

    # IBKR Tiered pricing (US stocks)
    TIERED_RATE = 0.0035  # per share
    TIERED_MIN = 0.35
    TIERED_MAX_PCT = 0.01

    # IBKR Fixed pricing
    FIXED_RATE = 0.005  # per share
    FIXED_MIN = 1.00
    FIXED_MAX_PCT = 0.005

    # Regulatory fees (approximate, updated periodically)
    SEC_FEE_RATE = 0.0000278  # per dollar, sell only
    TAF_FEE_RATE = 0.000166  # per share, sell only, max $8.30
    FINRA_FEE = 0.000119  # per share, sell only

    def __init__(self, model: CommissionModel = CommissionModel.TIERED):
        self.model = model
        self.ticker_profiles: dict[str, TickerCostProfile] = {}

    def set_profile(self, ticker: str, profile: TickerCostProfile):
        self.ticker_profiles[ticker] = profile

    def estimate(
        self,
        ticker: str,
        quantity: float,
        price: float,
        side: str,
        holding_days: int = 0,
    ) -> TransactionCost:
        """Estimate total cost for a trade."""
        abs_qty = abs(quantity)
        notional = abs_qty * price
        profile = self.ticker_profiles.get(ticker, TickerCostProfile())

        # Commission
        if self.model == CommissionModel.TIERED:
            commission = max(self.TIERED_MIN, abs_qty * self.TIERED_RATE)
            commission = min(commission, notional * self.TIERED_MAX_PCT)
        else:
            commission = max(self.FIXED_MIN, abs_qty * self.FIXED_RATE)
            commission = min(commission, notional * self.FIXED_MAX_PCT)

        # Spread cost (half spread, we cross it)
        spread_cost = notional * (profile.avg_spread_bps / 10000) / 2

        # Slippage: linear market impact model
        # Impact = volatility * sqrt(quantity / adv)
        if profile.avg_daily_volume > 0:
            participation = abs_qty / profile.avg_daily_volume
            slippage = price * profile.volatility * (participation ** 0.5) * abs_qty
        else:
            slippage = notional * 0.001  # fallback 10bps

        # Regulatory fees (sell side only)
        sec_fee = 0
        taf_fee = 0
        if side.lower() in ("sell", "short"):
            sec_fee = notional * self.SEC_FEE_RATE
            taf_fee = min(abs_qty * self.TAF_FEE_RATE, 8.30)

        # Short borrow cost
        short_borrow = 0
        if side.lower() == "short" and holding_days > 0:
            annual_cost = notional * profile.short_borrow_rate_annual
            short_borrow = annual_cost * (holding_days / 365)

        return TransactionCost(
            commission=round(commission, 4),
            spread_cost=round(spread_cost, 4),
            slippage=round(slippage, 4),
            sec_fee=round(sec_fee, 4),
            taf_fee=round(taf_fee, 4),
            short_borrow=round(short_borrow, 4),
        )

    def estimate_roundtrip(
        self,
        ticker: str,
        quantity: float,
        entry_price: float,
        exit_price: float,
        holding_days: int = 30,
        is_short: bool = False,
    ) -> TransactionCost:
        """Estimate full round-trip cost (entry + exit)."""
        entry_side = "short" if is_short else "buy"
        exit_side = "buy" if is_short else "sell"

        entry_cost = self.estimate(ticker, quantity, entry_price, entry_side, holding_days if is_short else 0)
        exit_cost = self.estimate(ticker, quantity, exit_price, exit_side)

        return TransactionCost(
            commission=entry_cost.commission + exit_cost.commission,
            spread_cost=entry_cost.spread_cost + exit_cost.spread_cost,
            slippage=entry_cost.slippage + exit_cost.slippage,
            sec_fee=entry_cost.sec_fee + exit_cost.sec_fee,
            taf_fee=entry_cost.taf_fee + exit_cost.taf_fee,
            short_borrow=entry_cost.short_borrow,
        )
