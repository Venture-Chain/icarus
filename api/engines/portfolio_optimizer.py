"""
Portfolio optimization engine.
Mean-variance, risk parity, Black-Litterman, CVaR, with constraints.
Signal-level constraint enforcement for sector rotation deployments.
"""
import logging
from dataclasses import dataclass, field

import cvxpy as cp
import numpy as np

from strategies.base import Signal

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
    cvar: float = 0
    gross_exposure: float = 0
    net_exposure: float = 0
    turnover: float = 0
    method: str = ""

    def to_dict(self) -> dict:
        d = {
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
        if self.cvar != 0:
            d["cvar"] = round(self.cvar * 100, 2)
        return d


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

    def cvar(
        self,
        tickers: list[str],
        returns: np.ndarray,
        constraints: OptimizationConstraints | None = None,
        confidence: float = 0.95,
        risk_aversion: float = 1.0,
    ) -> OptimizationResult:
        """
        Mean-CVaR optimization using the Rockafellar-Uryasev LP formulation.

        Minimizes: lambda * CVaR(alpha) - expected_return
        where CVaR is the expected loss in the worst (1-alpha) scenarios.

        Args:
            tickers: asset ticker symbols
            returns: (n_scenarios, n_assets) matrix of return scenarios
            constraints: weight bounds and exposure limits
            confidence: CVaR confidence level (0.95 = worst 5% of scenarios)
            risk_aversion: tradeoff between return and tail risk (higher = more conservative)
        """
        constraints = constraints or OptimizationConstraints()
        n = len(tickers)

        if n == 0 or returns.shape[0] == 0:
            return OptimizationResult(method="cvar")

        if returns.shape[1] != n:
            log.error("returns matrix columns (%d) != tickers (%d)", returns.shape[1], n)
            return OptimizationResult(method="cvar")

        n_scenarios = returns.shape[0]
        mu = np.mean(returns, axis=0)

        # Auto-scale risk aversion so lambda is comparable across different universes.
        # Scale by max(single-asset return / single-asset CVaR).
        alpha_idx = int(np.floor((1 - confidence) * n_scenarios))
        if alpha_idx < 1:
            alpha_idx = 1
        scalar = 0.0
        for i in range(n):
            sorted_losses = np.sort(-returns[:, i])
            asset_cvar = float(np.mean(sorted_losses[:alpha_idx]))
            if asset_cvar > 1e-8:
                scalar = max(scalar, abs(mu[i]) / asset_cvar)
        if scalar > 0:
            risk_aversion *= scalar

        # Decision variables
        w = cp.Variable(n, name="w")            # portfolio weights
        t = cp.Variable(name="t")               # VaR threshold
        u = cp.Variable(n_scenarios, name="u")   # excess losses per scenario

        # Uniform scenario probabilities
        p = np.ones(n_scenarios) / n_scenarios

        # Objective: minimize lambda * CVaR - expected return
        # CVaR = t + 1/(1-alpha) * sum(p_j * u_j)
        cvar_expr = t + (1.0 / (1.0 - confidence)) * (p @ u)
        objective = cp.Minimize(risk_aversion * cvar_expr - mu @ w)

        # Feasibility check: sum(w) == 1 requires max_weight >= 1/n.
        # If the caller's limit is too tight, relax to the exact minimum and warn.
        w_max = constraints.max_weight
        w_min = constraints.min_weight
        min_feasible = 1.0 / n
        if w_max < min_feasible:
            log.warning(
                "max_weight=%.2f is infeasible for %d assets (need >= %.2f), relaxing to %.2f",
                w_max, n, min_feasible, min_feasible,
            )
            w_max = min_feasible

        # Constraints
        cons = [
            # Scenario loss constraints: u_j >= -(returns[j,:] @ w) - t
            # Vectorized: u >= -returns @ w - t
            u >= -(returns @ w) - t,
            u >= 0,
            # Budget: weights sum to 1 (fully invested)
            cp.sum(w) == 1,
            # Weight bounds
            w >= w_min,
            w <= w_max,
        ]

        # Leverage constraint (L1 norm of weights)
        if constraints.max_gross_exposure < 10:
            cons.append(cp.norm(w, 1) <= constraints.max_gross_exposure)

        try:
            problem = cp.Problem(objective, cons)
            problem.solve(solver=cp.CLARABEL, warm_start=True)

            if problem.status not in ("optimal", "optimal_inaccurate"):
                log.warning("CVaR solver status: %s, falling back to equal weight", problem.status)
                return self.equal_weight(tickers)

            weights_arr = w.value
            if weights_arr is None:
                log.warning("CVaR solver returned None weights, falling back to equal weight")
                return self.equal_weight(tickers)

            # Zero out tiny weights
            weights_arr[np.abs(weights_arr) < 1e-4] = 0

            weights = {tickers[i]: float(weights_arr[i]) for i in range(n)}
            result = self._build_result(weights, "cvar")

            # Compute portfolio metrics
            port_return = float(weights_arr @ mu)
            port_losses = -returns @ weights_arr
            sorted_losses = np.sort(port_losses)
            cvar_value = float(np.mean(sorted_losses[-alpha_idx:]))
            port_risk = float(np.std(returns @ weights_arr))

            result.expected_return = port_return
            result.expected_risk = port_risk
            result.cvar = cvar_value
            if port_risk > 0:
                result.sharpe_ratio = (port_return - self.risk_free_rate / 252) / port_risk

            return result

        except cp.error.SolverError as e:
            log.warning("CVaR solver error: %s, falling back to equal weight", e)
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

    def optimize(
        self,
        signals: list[Signal],
        capital: float,
        current_positions: dict[str, float] | None = None,
    ) -> list[Signal]:
        """
        Apply position and sector constraints to a set of signals before execution.

        Returns signals with updated metadata containing adjusted quantity and position_size_pct.
        close/hedge direction signals pass through unchanged.
        """
        current_positions = current_positions or {}

        MAX_POSITION_PCT = 0.05
        MAX_SECTOR_PCT = 0.35
        MAX_POSITIONS = 15

        long_signals = [s for s in signals if s.direction == "long"]
        passthrough = [s for s in signals if s.direction != "long"]

        # Keep top MAX_POSITIONS by confidence
        long_signals.sort(key=lambda s: s.confidence, reverse=True)
        long_signals = long_signals[:MAX_POSITIONS]

        # First pass: assign base allocation (confidence-weighted, capped at 5%)
        total_confidence = sum(s.confidence for s in long_signals) or 1.0
        allocations: dict[str, float] = {}
        for s in long_signals:
            raw_pct = (s.confidence / total_confidence)
            allocations[s.ticker] = min(raw_pct, MAX_POSITION_PCT)

        # Sector enforcement: cap each sector at 35%
        sector_totals: dict[str, float] = {}
        for s in long_signals:
            sector = s.metadata.get("sector", "unknown")
            sector_totals[sector] = sector_totals.get(sector, 0.0) + allocations[s.ticker]

        for sector, total in sector_totals.items():
            if total > MAX_SECTOR_PCT:
                scale = MAX_SECTOR_PCT / total
                for s in long_signals:
                    if s.metadata.get("sector") == sector:
                        allocations[s.ticker] *= scale

        # Renormalize so allocations sum to <= 1.0
        total_alloc = sum(allocations.values())
        if total_alloc > 1.0:
            scale = 1.0 / total_alloc
            allocations = {t: v * scale for t, v in allocations.items()}

        result: list[Signal] = []
        for s in long_signals:
            pct = allocations[s.ticker]
            position_value = capital * pct
            entry_price = s.metadata.get("entry_price", 0.0)
            quantity = int(position_value / entry_price) if entry_price > 0 else 0

            updated_meta = {**s.metadata, "position_size_pct": round(pct, 4), "quantity": quantity}
            result.append(Signal(
                ticker=s.ticker,
                direction=s.direction,
                instrument=s.instrument,
                confidence=s.confidence,
                hedge_for=s.hedge_for,
                sizing_method=s.sizing_method,
                metadata=updated_meta,
            ))

        return result + passthrough

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
