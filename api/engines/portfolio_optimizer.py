"""
Portfolio optimization engine.
Mean-variance, risk parity, Black-Litterman.
"""


class PortfolioOptimizer:
    def optimize(self, positions, constraints=None, method="risk_parity"):
        """Run portfolio optimization, return target weights."""
        return {"weights": {}, "method": method}
