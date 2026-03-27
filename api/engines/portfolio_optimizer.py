"""
Portfolio optimization engine.
Mean-variance, risk parity, Black-Litterman, with constraints.
"""
import logging
from dataclasses import dataclass, field

import numpy as np

log = logging.getLogger("icarus.optimizer")


@dataclass
class OptimizationConstraints:
    min_weight: float = -0.10        # allow 10% short per position
    max_weight: float = 0.10         # max 10% per position
    max_sector_weight: float = 0.30  # max 30% per sector
    max_gross_exposure: float = 2.0  # max 200% gross
    max_net_exposure: float = 0.50   # max 50% net
    max_turnover: float = 0.50       # max 50% turnover per rebalance
    min_positions: int = 5
    max_positions: int = 30


@dataclass
class OptimizationResult:
    weights: dict[str, float] = field(default_factory=dict)
    expected_return: float = 0
    expected_risk: float = 0
    sharpe_ratio: float = 0
    gross_exposure: float = 0
    net_exposure: float = 0
    turnover: float = 0
    method: str = ""

    def to_dict(self) -> dict:
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items() if abs(v) > 0.001},
            "expected_return": round(self.expected_return * 100, 2),
            "expected_risk": round(self.expected_risk * 100, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "gross_exposure": round(self.gross_exposure * 100, 1),
            "net_exposure": round(self.net_exposure * 100, 1),
            "turnover": round(self.turnover * 100, 1),
            "method": self.method,
            "long_positions": sum(1 for v in self.weights.values() if v > 0.001),
            "short_positions": sum(1 for v in self.weights.values() if v < -0.001),
        }


class PortfolioOptimizer:
    """Portfolio construction with multiple optimization methods."""

    def __init__(self, risk_free_rate: float = 0.045):
        self.risk_free_rate = risk_free_rate

    def equal_weight(
        self,
        tickers: list[str],
        signals: dict[str, float] | None = None,
    ) -> OptimizationResult:
        """Equal weight across all tickers. Simplest baseline."""
        n = len(tickers)
        if n == 0:
            return OptimizationResult(method="equal_weight")

        weight = 1.0 / n
        weights = {}
        for ticker in tickers:
            if signals and ticker in signals:
                weights[ticker] = weight if signals[ticker] > 0 else -weight
            else:
                weights[ticker] = weight

        return self._build_result(weights, "equal_weight")

    def risk_parity(
        self,
        tickers: list[str],
        volatilities: dict[str, float],
        constraints: OptimizationConstraints | None = None,
    ) -> OptimizationResult:
        """
        Risk parity: weight inversely proportional to volatility.
        Each position contributes equal risk.
        """
        constraints = constraints or OptimizationConstraints()

        if not tickers or not volatilities:
            return OptimizationResult(method="risk_parity")

        # Inverse volatility weighting
        inv_vols = {}
        for ticker in tickers:
            vol = volatilities.get(ticker, 0.20)
            if vol > 0:
                inv_vols[ticker] = 1.0 / vol

        total_inv_vol = sum(inv_vols.values())
        if total_inv_vol == 0:
            return self.equal_weight(tickers)

        weights = {}
        for ticker in tickers:
            raw_weight = inv_vols.get(ticker, 0) / total_inv_vol
            weights[ticker] = np.clip(raw_weight, constraints.min_weight, constraints.max_weight)

        # Renormalize
        total = sum(abs(v) for v in weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return self._build_result(weights, "risk_parity")

    def mean_variance(
        self,
        tickers: list[str],
        expected_returns: dict[str, float],
        covariance_matrix: np.ndarray,
        constraints: OptimizationConstraints | None = None,
        target_return: float | None = None,
    ) -> OptimizationResult:
        """
        Mean-variance optimization (Markowitz).
        Finds weights that maximize Sharpe ratio or hit target return.

        Uses analytical solution for unconstrained case,
        iterative approach for constrained.
        """
        constraints = constraints or OptimizationConstraints()
        n = len(tickers)

        if n == 0 or covariance_matrix.shape != (n, n):
            return OptimizationResult(method="mean_variance")

        mu = np.array([expected_returns.get(t, 0) for t in tickers])
        cov = covariance_matrix

        try:
            # Unconstrained max Sharpe (tangency portfolio)
            cov_inv = np.linalg.inv(cov)
            excess_returns = mu - self.risk_free_rate
            raw_weights = cov_inv @ excess_returns
            total = np.sum(raw_weights)

            if total != 0:
                raw_weights = raw_weights / total
            else:
                raw_weights = np.ones(n) / n

            # Apply constraints
            for i in range(n):
                raw_weights[i] = np.clip(
                    raw_weights[i],
                    constraints.min_weight,
                    constraints.max_weight,
                )

            # Renormalize after clipping
            total = np.sum(np.abs(raw_weights))
            if total > 0:
                raw_weights = raw_weights / total

            weights = {tickers[i]: float(raw_weights[i]) for i in range(n)}

            # Calculate expected portfolio metrics
            port_return = float(raw_weights @ mu)
            port_risk = float(np.sqrt(raw_weights @ cov @ raw_weights))

            result = self._build_result(weights, "mean_variance")
            result.expected_return = port_return
            result.expected_risk = port_risk
            if port_risk > 0:
                result.sharpe_ratio = (port_return - self.risk_free_rate) / port_risk

            return result

        except np.linalg.LinAlgError:
            log.warning("covariance matrix singular, falling back to equal weight")
            return self.equal_weight(tickers)

    def black_litterman(
        self,
        tickers: list[str],
        market_caps: dict[str, float],
        covariance_matrix: np.ndarray,
        views: dict[str, float],
        view_confidences: dict[str, float] | None = None,
        tau: float = 0.05,
        constraints: OptimizationConstraints | None = None,
    ) -> OptimizationResult:
        """
        Black-Litterman model.
        Combines market equilibrium with investor views (from Icarus signals).

        views: {"AAPL": 0.10} means "I believe AAPL will return 10%"
        view_confidences: {"AAPL": 0.8} means 80% confident
        """
        constraints = constraints or OptimizationConstraints()
        n = len(tickers)

        if n == 0:
            return OptimizationResult(method="black_litterman")

        cov = covariance_matrix

        # Market equilibrium weights (from market caps)
        total_cap = sum(market_caps.get(t, 1) for t in tickers)
        market_weights = np.array([market_caps.get(t, 1) / total_cap for t in tickers])

        # Implied equilibrium returns
        risk_aversion = 2.5  # standard assumption
        pi = risk_aversion * cov @ market_weights

        # Build view matrices
        view_tickers = [t for t in tickers if t in views]
        k = len(view_tickers)

        if k == 0:
            # No views: return market weights
            weights = {tickers[i]: float(market_weights[i]) for i in range(n)}
            return self._build_result(weights, "black_litterman")

        P = np.zeros((k, n))
        Q = np.zeros(k)
        omega_diag = np.zeros(k)

        for j, ticker in enumerate(view_tickers):
            i = tickers.index(ticker)
            P[j, i] = 1.0
            Q[j] = views[ticker]
            confidence = (view_confidences or {}).get(ticker, 0.5)
            # Omega: uncertainty of view. Lower confidence = higher uncertainty.
            omega_diag[j] = (1 - confidence) * tau * cov[i, i]

        Omega = np.diag(omega_diag)

        try:
            # BL posterior expected returns
            tau_cov = tau * cov
            tau_cov_inv = np.linalg.inv(tau_cov)
            omega_inv = np.linalg.inv(Omega)

            posterior_cov = np.linalg.inv(tau_cov_inv + P.T @ omega_inv @ P)
            posterior_mean = posterior_cov @ (tau_cov_inv @ pi + P.T @ omega_inv @ Q)

            # Optimize using posterior
            expected_returns = {tickers[i]: float(posterior_mean[i]) for i in range(n)}
            return self.mean_variance(tickers, expected_returns, cov, constraints)

        except np.linalg.LinAlgError:
            log.warning("BL matrix inversion failed, using market weights")
            weights = {tickers[i]: float(market_weights[i]) for i in range(n)}
            result = self._build_result(weights, "black_litterman")
            return result

    def minimum_variance(
        self,
        tickers: list[str],
        covariance_matrix: np.ndarray,
        constraints: OptimizationConstraints | None = None,
    ) -> OptimizationResult:
        """Global minimum variance portfolio."""
        constraints = constraints or OptimizationConstraints()
        n = len(tickers)

        try:
            cov_inv = np.linalg.inv(covariance_matrix)
            ones = np.ones(n)
            raw = cov_inv @ ones
            weights_arr = raw / (ones @ cov_inv @ ones)

            for i in range(n):
                weights_arr[i] = np.clip(
                    weights_arr[i],
                    constraints.min_weight,
                    constraints.max_weight,
                )

            total = np.sum(np.abs(weights_arr))
            if total > 0:
                weights_arr /= total

            weights = {tickers[i]: float(weights_arr[i]) for i in range(n)}
            result = self._build_result(weights, "minimum_variance")
            result.expected_risk = float(np.sqrt(weights_arr @ covariance_matrix @ weights_arr))
            return result

        except np.linalg.LinAlgError:
            return self.equal_weight(tickers)

    def _build_result(self, weights: dict[str, float], method: str) -> OptimizationResult:
        """Build result with exposure metrics."""
        long_sum = sum(v for v in weights.values() if v > 0)
        short_sum = sum(abs(v) for v in weights.values() if v < 0)

        return OptimizationResult(
            weights=weights,
            gross_exposure=long_sum + short_sum,
            net_exposure=long_sum - short_sum,
            method=method,
        )

    def calculate_turnover(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
    ) -> float:
        """Calculate one-way turnover between current and target portfolios."""
        all_tickers = set(current_weights) | set(target_weights)
        turnover = sum(
            abs(target_weights.get(t, 0) - current_weights.get(t, 0))
            for t in all_tickers
        )
        return turnover / 2  # one-way
