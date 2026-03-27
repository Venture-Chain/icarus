"""
DCF valuation engine.
Adapted from Venture Chain financial modeling toolkit.
"""
import numpy as np


class ValuationEngine:
    def __init__(self):
        self.results = {}

    def dcf(
        self,
        revenue: float,
        growth_rates: list[float],
        ebitda_margins: list[float],
        wacc: float,
        terminal_growth: float = 0.03,
        tax_rate: float = 0.25,
        capex_pct: float = 0.05,
        nwc_pct: float = 0.10,
    ) -> dict:
        """Run DCF valuation. Returns enterprise value and components."""
        years = len(growth_rates)
        fcfs = []
        current_revenue = revenue
        prev_nwc = revenue * nwc_pct

        for i in range(years):
            current_revenue *= (1 + growth_rates[i])
            ebitda = current_revenue * ebitda_margins[i]
            depreciation = current_revenue * capex_pct
            ebit = ebitda - depreciation
            nopat = ebit * (1 - tax_rate)
            capex = current_revenue * capex_pct
            nwc = current_revenue * nwc_pct
            nwc_change = nwc - prev_nwc
            fcf = nopat + depreciation - capex - nwc_change
            fcfs.append(fcf)
            prev_nwc = nwc

        pv_fcfs = [fcf / (1 + wacc) ** (i + 1) for i, fcf in enumerate(fcfs)]
        terminal_fcf = fcfs[-1] * (1 + terminal_growth)
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        pv_terminal = terminal_value / (1 + wacc) ** years
        enterprise_value = sum(pv_fcfs) + pv_terminal

        self.results = {
            "enterprise_value": enterprise_value,
            "pv_fcfs": sum(pv_fcfs),
            "pv_terminal": pv_terminal,
            "terminal_pct": pv_terminal / enterprise_value * 100,
            "fcfs": fcfs,
        }
        return self.results

    def fair_value_score(self, enterprise_value: float, market_cap: float) -> float:
        """Score: >1 means undervalued, <1 means overvalued."""
        if market_cap <= 0:
            return 0
        return enterprise_value / market_cap
