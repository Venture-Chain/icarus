"""
DCF valuation engine.
Adapted from Venture Chain financial modeling toolkit.
Supports auto-pull of fundamentals for hands-off valuation.
"""
import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger("icarus.valuation")


@dataclass
class WACCInputs:
    risk_free_rate: float = 0.045
    beta: float = 1.0
    market_premium: float = 0.065
    cost_of_debt: float = 0.05
    debt_to_equity: float = 0.5
    tax_rate: float = 0.25


@dataclass
class DCFAssumptions:
    projection_years: int = 5
    revenue_growth: list[float] = field(default_factory=lambda: [0.10, 0.08, 0.06, 0.05, 0.04])
    ebitda_margins: list[float] = field(default_factory=lambda: [0.20] * 5)
    capex_pct: float = 0.05
    nwc_pct: float = 0.10
    terminal_growth: float = 0.03
    tax_rate: float = 0.25


@dataclass
class DCFResult:
    enterprise_value: float = 0
    equity_value: float = 0
    value_per_share: float = 0
    pv_fcfs: float = 0
    pv_terminal: float = 0
    terminal_pct: float = 0
    wacc: float = 0
    projected_fcfs: list[float] = field(default_factory=list)
    projected_revenue: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "enterprise_value": round(self.enterprise_value, 2),
            "equity_value": round(self.equity_value, 2),
            "value_per_share": round(self.value_per_share, 2),
            "pv_fcfs": round(self.pv_fcfs, 2),
            "pv_terminal": round(self.pv_terminal, 2),
            "terminal_pct": round(self.terminal_pct, 1),
            "wacc": round(self.wacc * 100, 2),
            "projected_fcfs": [round(f, 2) for f in self.projected_fcfs],
        }


class ValuationEngine:
    """DCF valuation with WACC, projections, and fair value scoring."""

    def calculate_wacc(self, inputs: WACCInputs) -> float:
        """CAPM-based WACC calculation."""
        cost_of_equity = inputs.risk_free_rate + inputs.beta * inputs.market_premium
        equity_weight = 1 / (1 + inputs.debt_to_equity)
        debt_weight = inputs.debt_to_equity / (1 + inputs.debt_to_equity)
        wacc = (
            equity_weight * cost_of_equity
            + debt_weight * inputs.cost_of_debt * (1 - inputs.tax_rate)
        )
        return wacc

    def dcf(
        self,
        base_revenue: float,
        assumptions: DCFAssumptions,
        wacc_inputs: WACCInputs,
        net_debt: float = 0,
        shares_outstanding: float = 1,
    ) -> DCFResult:
        """
        Full DCF valuation.

        Args:
            base_revenue: Last twelve months revenue
            assumptions: Projection assumptions
            wacc_inputs: WACC calculation inputs
            net_debt: Total debt minus cash
            shares_outstanding: Diluted shares outstanding
        """
        result = DCFResult()
        wacc = self.calculate_wacc(wacc_inputs)
        result.wacc = wacc
        years = assumptions.projection_years

        # Project cash flows
        revenue = base_revenue
        prev_nwc = base_revenue * assumptions.nwc_pct
        fcfs = []
        revenues = []

        for i in range(years):
            growth = assumptions.revenue_growth[i] if i < len(assumptions.revenue_growth) else assumptions.revenue_growth[-1]
            margin = assumptions.ebitda_margins[i] if i < len(assumptions.ebitda_margins) else assumptions.ebitda_margins[-1]

            revenue *= (1 + growth)
            revenues.append(revenue)

            ebitda = revenue * margin
            depreciation = revenue * assumptions.capex_pct
            ebit = ebitda - depreciation
            nopat = ebit * (1 - assumptions.tax_rate)
            capex = revenue * assumptions.capex_pct
            nwc = revenue * assumptions.nwc_pct
            nwc_change = nwc - prev_nwc
            fcf = nopat + depreciation - capex - nwc_change
            fcfs.append(fcf)
            prev_nwc = nwc

        result.projected_fcfs = fcfs
        result.projected_revenue = revenues

        # PV of projected FCFs
        pv_fcfs = [fcf / (1 + wacc) ** (i + 1) for i, fcf in enumerate(fcfs)]
        result.pv_fcfs = sum(pv_fcfs)

        # Terminal value (Gordon growth)
        if wacc > assumptions.terminal_growth:
            terminal_fcf = fcfs[-1] * (1 + assumptions.terminal_growth)
            terminal_value = terminal_fcf / (wacc - assumptions.terminal_growth)
            result.pv_terminal = terminal_value / (1 + wacc) ** years
        else:
            # Fallback: exit multiple
            result.pv_terminal = fcfs[-1] * 15 / (1 + wacc) ** years

        # Enterprise and equity value
        result.enterprise_value = result.pv_fcfs + result.pv_terminal
        result.equity_value = result.enterprise_value - net_debt

        if result.enterprise_value > 0:
            result.terminal_pct = (result.pv_terminal / result.enterprise_value) * 100

        if shares_outstanding > 0:
            result.value_per_share = result.equity_value / shares_outstanding

        return result

    def fair_value_score(self, intrinsic_value: float, market_price: float) -> dict:
        """
        Compare intrinsic value to market price.
        Score > 1 means undervalued, < 1 means overvalued.
        """
        if market_price <= 0:
            return {"score": 0, "upside_pct": 0, "assessment": "no data"}

        score = intrinsic_value / market_price
        upside = (intrinsic_value - market_price) / market_price

        if score > 1.3:
            assessment = "significantly undervalued"
        elif score > 1.1:
            assessment = "moderately undervalued"
        elif score > 0.9:
            assessment = "fairly valued"
        elif score > 0.7:
            assessment = "moderately overvalued"
        else:
            assessment = "significantly overvalued"

        return {
            "score": round(score, 3),
            "upside_pct": round(upside * 100, 1),
            "assessment": assessment,
        }

    def quick_valuation(
        self,
        ticker: str,
        revenue: float,
        ebitda_margin: float,
        growth_rate: float,
        beta: float = 1.0,
        net_debt: float = 0,
        shares: float = 1,
        market_price: float = 0,
    ) -> dict:
        """
        Quick valuation with minimal inputs.
        Uses sensible defaults for unspecified assumptions.
        """
        # Build assumptions from limited inputs
        growth_decay = [growth_rate * (0.9 ** i) for i in range(5)]
        margins = [ebitda_margin] * 5

        assumptions = DCFAssumptions(
            revenue_growth=growth_decay,
            ebitda_margins=margins,
        )
        wacc_inputs = WACCInputs(beta=beta)

        result = self.dcf(revenue, assumptions, wacc_inputs, net_debt, shares)

        output = result.to_dict()
        if market_price > 0:
            output["fair_value"] = self.fair_value_score(result.value_per_share, market_price)

        return output

    def comparable_valuation(
        self,
        target_ebitda: float,
        comparable_multiples: list[float],
        net_debt: float = 0,
        shares: float = 1,
    ) -> dict:
        """
        EV/EBITDA comparable company valuation.
        Uses median of comparable multiples.
        """
        if not comparable_multiples:
            return {"error": "no comparable multiples provided"}

        median_multiple = float(np.median(comparable_multiples))
        mean_multiple = float(np.mean(comparable_multiples))
        low_multiple = float(np.percentile(comparable_multiples, 25))
        high_multiple = float(np.percentile(comparable_multiples, 75))

        ev_median = target_ebitda * median_multiple
        ev_mean = target_ebitda * mean_multiple
        ev_low = target_ebitda * low_multiple
        ev_high = target_ebitda * high_multiple

        return {
            "ev_median": round(ev_median, 2),
            "ev_mean": round(ev_mean, 2),
            "ev_low": round(ev_low, 2),
            "ev_high": round(ev_high, 2),
            "equity_median": round(ev_median - net_debt, 2),
            "per_share_median": round((ev_median - net_debt) / shares, 2) if shares > 0 else 0,
            "multiples_used": {
                "median": round(median_multiple, 1),
                "mean": round(mean_multiple, 1),
                "p25": round(low_multiple, 1),
                "p75": round(high_multiple, 1),
            },
        }
