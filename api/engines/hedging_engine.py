"""
Hedging framework.
Beta hedging, sector hedging, pair trading, hedge ratio calculation.
"""
import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger("icarus.hedging")


# Common hedge instruments
INDEX_ETFS = {
    "market": "SPY",
    "nasdaq": "QQQ",
    "small_cap": "IWM",
    "dow": "DIA",
}

SECTOR_ETFS = {
    "technology": "XLK",
    "healthcare": "XLV",
    "financials": "XLF",
    "energy": "XLE",
    "consumer_discretionary": "XLY",
    "consumer_staples": "XLP",
    "industrials": "XLI",
    "materials": "XLB",
    "utilities": "XLU",
    "real_estate": "XLRE",
    "communication": "XLC",
}


@dataclass
class HedgeRecommendation:
    hedge_type: str          # beta, sector, pair
    instrument: str          # ticker to trade
    direction: str           # short or long
    quantity: float          # shares
    notional: float          # dollar value
    hedge_ratio: float       # ratio of hedge to underlying
    target_metric: str       # what this hedge targets (beta, sector_exposure)
    current_value: float     # current metric value
    target_value: float      # target after hedge
    estimated_cost: float = 0
    reasoning: str = ""

    def to_dict(self) -> dict:
        return {
            "type": self.hedge_type,
            "instrument": self.instrument,
            "direction": self.direction,
            "quantity": round(self.quantity),
            "notional": round(self.notional, 2),
            "hedge_ratio": round(self.hedge_ratio, 3),
            "target_metric": self.target_metric,
            "current": round(self.current_value, 3),
            "target": round(self.target_value, 3),
            "reasoning": self.reasoning,
        }


@dataclass
class HedgeStatus:
    portfolio_beta: float = 0
    net_beta_after_hedge: float = 0
    sector_exposures: dict[str, float] = field(default_factory=dict)
    active_hedges: list[HedgeRecommendation] = field(default_factory=list)
    hedge_cost_annual: float = 0
    hedge_drag_pct: float = 0


class HedgingEngine:
    """Portfolio hedging: beta, sector, pairs."""

    def beta_hedge(
        self,
        portfolio_beta: float,
        portfolio_value: float,
        target_beta: float = 0.0,
        hedge_instrument: str = "SPY",
        instrument_price: float = 0,
        instrument_beta: float = 1.0,
    ) -> HedgeRecommendation | None:
        """
        Calculate hedge to achieve target portfolio beta.
        Typically short SPY to reduce market exposure.
        """
        if instrument_price <= 0 or instrument_beta == 0:
            return None

        beta_to_hedge = portfolio_beta - target_beta

        if abs(beta_to_hedge) < 0.05:
            return None  # close enough

        # Hedge notional = portfolio_value * beta_to_hedge / instrument_beta
        hedge_notional = portfolio_value * beta_to_hedge / instrument_beta
        hedge_shares = abs(hedge_notional / instrument_price)
        direction = "short" if beta_to_hedge > 0 else "long"

        return HedgeRecommendation(
            hedge_type="beta",
            instrument=hedge_instrument,
            direction=direction,
            quantity=hedge_shares,
            notional=abs(hedge_notional),
            hedge_ratio=abs(beta_to_hedge / instrument_beta),
            target_metric="portfolio_beta",
            current_value=portfolio_beta,
            target_value=target_beta,
            reasoning=f"{'short' if direction == 'short' else 'long'} {hedge_shares:.0f} shares of {hedge_instrument} to move beta from {portfolio_beta:.2f} to {target_beta:.2f}",
        )

    def sector_hedge(
        self,
        sector: str,
        sector_exposure: float,
        portfolio_value: float,
        target_exposure: float = 0.0,
        etf_price: float = 0,
    ) -> HedgeRecommendation | None:
        """Hedge sector exposure using sector ETFs."""
        etf = SECTOR_ETFS.get(sector.lower())
        if not etf or etf_price <= 0:
            return None

        exposure_to_hedge = sector_exposure - target_exposure
        if abs(exposure_to_hedge) < 0.02:
            return None

        hedge_notional = portfolio_value * exposure_to_hedge
        hedge_shares = abs(hedge_notional / etf_price)
        direction = "short" if exposure_to_hedge > 0 else "long"

        return HedgeRecommendation(
            hedge_type="sector",
            instrument=etf,
            direction=direction,
            quantity=hedge_shares,
            notional=abs(hedge_notional),
            hedge_ratio=abs(exposure_to_hedge),
            target_metric=f"sector_{sector}",
            current_value=sector_exposure,
            target_value=target_exposure,
            reasoning=f"{'short' if direction == 'short' else 'long'} {hedge_shares:.0f} shares of {etf} to reduce {sector} exposure from {sector_exposure:.1%} to {target_exposure:.1%}",
        )

    def pair_hedge(
        self,
        long_ticker: str,
        short_ticker: str,
        long_price: float,
        short_price: float,
        long_quantity: float,
        returns_long: list[float] | None = None,
        returns_short: list[float] | None = None,
    ) -> HedgeRecommendation:
        """
        Calculate pair trade hedge ratio.
        Uses beta-matching if return history is available, dollar-neutral otherwise.
        """
        if returns_long and returns_short and len(returns_long) > 20:
            # Regression-based hedge ratio
            min_len = min(len(returns_long), len(returns_short))
            y = np.array(returns_long[-min_len:])
            x = np.array(returns_short[-min_len:])
            beta = np.cov(y, x)[0, 1] / np.var(x) if np.var(x) > 0 else 1.0
        else:
            # Dollar-neutral
            beta = long_price / short_price if short_price > 0 else 1.0

        short_quantity = long_quantity * beta * (long_price / short_price) if short_price > 0 else long_quantity

        return HedgeRecommendation(
            hedge_type="pair",
            instrument=short_ticker,
            direction="short",
            quantity=short_quantity,
            notional=short_quantity * short_price,
            hedge_ratio=beta,
            target_metric="pair_spread",
            current_value=0,
            target_value=0,
            reasoning=f"short {short_quantity:.0f} shares of {short_ticker} against {long_quantity:.0f} {long_ticker} (ratio: {beta:.3f})",
        )

    def recommend_hedges(
        self,
        portfolio_beta: float,
        portfolio_value: float,
        sector_exposures: dict[str, float],
        prices: dict[str, float],
        target_beta: float = 0.0,
        max_sector_exposure: float = 0.15,
    ) -> list[HedgeRecommendation]:
        """
        Generate all recommended hedges for the portfolio.
        Returns list sorted by impact.
        """
        recommendations = []

        # Beta hedge
        spy_price = prices.get("SPY", 0)
        if spy_price > 0:
            beta_rec = self.beta_hedge(
                portfolio_beta, portfolio_value,
                target_beta, "SPY", spy_price,
            )
            if beta_rec:
                recommendations.append(beta_rec)

        # Sector hedges
        for sector, exposure in sector_exposures.items():
            if abs(exposure) > max_sector_exposure:
                etf = SECTOR_ETFS.get(sector.lower(), "")
                etf_price = prices.get(etf, 0)
                if etf_price > 0:
                    sector_rec = self.sector_hedge(
                        sector, exposure, portfolio_value,
                        max_sector_exposure if exposure > 0 else -max_sector_exposure,
                        etf_price,
                    )
                    if sector_rec:
                        recommendations.append(sector_rec)

        recommendations.sort(key=lambda r: r.notional, reverse=True)
        return recommendations

    def calculate_hedge_cost(
        self,
        hedges: list[HedgeRecommendation],
        short_borrow_rate: float = 0.005,
        spread_bps: float = 3.0,
    ) -> dict:
        """Estimate annual cost of maintaining hedges."""
        total_short_notional = sum(h.notional for h in hedges if h.direction == "short")
        annual_borrow = total_short_notional * short_borrow_rate
        spread_cost = sum(h.notional * spread_bps / 10000 for h in hedges)

        return {
            "annual_borrow_cost": round(annual_borrow, 2),
            "entry_spread_cost": round(spread_cost, 2),
            "total_hedge_notional": round(sum(h.notional for h in hedges), 2),
            "hedge_count": len(hedges),
        }
