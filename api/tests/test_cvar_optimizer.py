"""Tests for CVaR portfolio optimization."""
import numpy as np
import pytest

from engines.portfolio_optimizer import OptimizationConstraints, PortfolioOptimizer


@pytest.fixture
def optimizer():
    return PortfolioOptimizer(risk_free_rate=0.045)


@pytest.fixture
def sample_returns():
    """Generate 252 days of returns for 5 assets with known characteristics."""
    rng = np.random.default_rng(42)
    n_days, n_assets = 252, 5
    # Asset 0: high return, high vol. Asset 4: low return, low vol.
    means = np.array([0.001, 0.0005, 0.0003, 0.0002, 0.0001])
    vols = np.array([0.03, 0.02, 0.015, 0.01, 0.005])
    returns = rng.normal(means, vols, size=(n_days, n_assets))
    return returns


@pytest.fixture
def tickers():
    return ["AAPL", "MSFT", "GOOG", "AMZN", "BRK"]


class TestCvarOptimizer:
    def test_basic_optimization(self, optimizer, tickers, sample_returns):
        result = optimizer.cvar(tickers, sample_returns)
        assert result.method == "cvar"
        assert len(result.weights) > 0
        # Weights should sum to ~1
        assert abs(sum(result.weights.values()) - 1.0) < 0.01

    def test_returns_optimization_result(self, optimizer, tickers, sample_returns):
        result = optimizer.cvar(tickers, sample_returns)
        assert result.expected_return != 0 or result.cvar != 0
        assert result.gross_exposure > 0

    def test_weight_bounds_respected(self, optimizer, tickers, sample_returns):
        constraints = OptimizationConstraints(min_weight=0.0, max_weight=0.30)
        result = optimizer.cvar(tickers, sample_returns, constraints=constraints)
        for w in result.weights.values():
            assert w >= -0.001  # small tolerance
            assert w <= 0.301

    def test_long_only(self, optimizer, tickers, sample_returns):
        constraints = OptimizationConstraints(min_weight=0.0, max_weight=0.50)
        result = optimizer.cvar(tickers, sample_returns, constraints=constraints)
        for w in result.weights.values():
            assert w >= -0.001

    def test_high_risk_aversion_favors_safety(self, optimizer, tickers, sample_returns):
        low_ra = optimizer.cvar(tickers, sample_returns, risk_aversion=0.1)
        high_ra = optimizer.cvar(tickers, sample_returns, risk_aversion=10.0)
        # Higher risk aversion should produce lower CVaR (less tail risk)
        assert high_ra.cvar <= low_ra.cvar + 0.001

    def test_confidence_levels(self, optimizer, tickers, sample_returns):
        r95 = optimizer.cvar(tickers, sample_returns, confidence=0.95)
        r99 = optimizer.cvar(tickers, sample_returns, confidence=0.99)
        assert r95.method == "cvar"
        assert r99.method == "cvar"

    def test_empty_tickers(self, optimizer, sample_returns):
        result = optimizer.cvar([], sample_returns)
        assert result.method == "cvar"
        assert len(result.weights) == 0

    def test_empty_returns(self, optimizer, tickers):
        result = optimizer.cvar(tickers, np.empty((0, 5)))
        assert result.method == "cvar"
        assert len(result.weights) == 0

    def test_mismatched_dimensions(self, optimizer, tickers, sample_returns):
        # 5 tickers but 3-column returns
        result = optimizer.cvar(tickers, sample_returns[:, :3])
        assert len(result.weights) == 0

    def test_to_dict_includes_cvar(self, optimizer, tickers, sample_returns):
        result = optimizer.cvar(tickers, sample_returns)
        d = result.to_dict()
        assert "cvar" in d
        assert "method" in d
        assert d["method"] == "cvar"

    def test_two_assets(self, optimizer):
        rng = np.random.default_rng(123)
        returns = rng.normal([0.001, 0.0005], [0.02, 0.01], size=(100, 2))
        result = optimizer.cvar(["A", "B"], returns)
        assert result.method == "cvar"
        assert abs(sum(result.weights.values()) - 1.0) < 0.01
