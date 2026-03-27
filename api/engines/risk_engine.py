"""
Portfolio risk management engine.
VaR, CVaR, stress tests, position limits, kill switch.
Has veto power over execution engine.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np

log = logging.getLogger("icarus.risk")


class KillSwitchReason(str, Enum):
    MAX_DRAWDOWN = "max_drawdown_breach"
    DAILY_LOSS = "daily_loss_breach"
    DATA_FAILURE = "data_feed_failure"
    IB_DISCONNECT = "ib_disconnection"
    MANUAL = "manual_activation"


@dataclass
class RiskLimits:
    max_position_pct: float = 0.10       # max 10% in single position
    max_sector_pct: float = 0.30         # max 30% in single sector
    max_gross_exposure: float = 2.0      # max 200% gross (long + short)
    max_net_exposure: float = 0.50       # max 50% net (long - short)
    max_daily_loss_pct: float = 0.02     # max 2% daily loss
    max_drawdown_pct: float = 0.10       # max 10% drawdown from peak
    max_var_95_pct: float = 0.03         # max 3% daily VaR
    max_correlation: float = 0.80        # warn if position correlation > 80%
    warning_threshold: float = 0.80      # alert at 80% of any limit


@dataclass
class Position:
    ticker: str
    quantity: float
    avg_cost: float
    current_price: float
    sector: str = ""
    strategy_id: int | None = None
    is_hedge: bool = False

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def unrealized_pnl(self) -> float:
        return self.quantity * (self.current_price - self.avg_cost)

    @property
    def direction(self) -> str:
        return "long" if self.quantity > 0 else "short"


@dataclass
class RiskMetrics:
    portfolio_value: float = 0
    var_95: float = 0
    var_99: float = 0
    cvar_95: float = 0
    max_drawdown: float = 0
    current_drawdown: float = 0
    net_exposure: float = 0
    gross_exposure: float = 0
    beta: float = 0
    sharpe: float = 0
    positions_count: int = 0
    long_value: float = 0
    short_value: float = 0
    largest_position_pct: float = 0
    correlation_max: float = 0

    def to_dict(self) -> dict:
        return {
            "portfolio_value": round(self.portfolio_value, 2),
            "var_95": round(self.var_95, 2),
            "var_99": round(self.var_99, 2),
            "cvar_95": round(self.cvar_95, 2),
            "max_drawdown": round(self.max_drawdown * 100, 2),
            "current_drawdown": round(self.current_drawdown * 100, 2),
            "net_exposure": round(self.net_exposure, 4),
            "gross_exposure": round(self.gross_exposure, 4),
            "beta": round(self.beta, 3),
            "sharpe": round(self.sharpe, 3),
            "positions_count": self.positions_count,
            "long_value": round(self.long_value, 2),
            "short_value": round(self.short_value, 2),
            "largest_position_pct": round(self.largest_position_pct * 100, 1),
            "correlation_max": round(self.correlation_max, 3),
        }


@dataclass
class LimitCheck:
    passed: bool
    limit_name: str
    current_value: float
    limit_value: float
    utilization: float  # 0 to 1
    severity: str = "ok"  # ok, warning, breach

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "limit": self.limit_name,
            "current": round(self.current_value, 4),
            "limit": round(self.limit_value, 4),
            "utilization": round(self.utilization * 100, 1),
            "severity": self.severity,
        }


@dataclass
class KillSwitchEvent:
    reason: KillSwitchReason
    triggered_at: datetime
    portfolio_value: float
    details: str = ""


class RiskEngine:
    """Portfolio risk management with veto power and kill switch."""

    def __init__(self, limits: RiskLimits | None = None):
        self.limits = limits or RiskLimits()
        self.kill_switch_active = False
        self.kill_switch_history: list[KillSwitchEvent] = []
        self.peak_value: float = 0
        self.daily_start_value: float = 0

    def compute_metrics(
        self,
        positions: list[Position],
        returns_history: dict[str, list[float]] | None = None,
        market_returns: list[float] | None = None,
    ) -> RiskMetrics:
        """Compute full portfolio risk metrics."""
        metrics = RiskMetrics()

        if not positions:
            return metrics

        # Basic portfolio metrics
        long_value = sum(abs(p.market_value) for p in positions if p.quantity > 0)
        short_value = sum(abs(p.market_value) for p in positions if p.quantity < 0)
        nav = long_value - short_value  # simplified NAV

        metrics.portfolio_value = nav
        metrics.long_value = long_value
        metrics.short_value = short_value
        metrics.positions_count = len(positions)

        if nav > 0:
            metrics.gross_exposure = (long_value + short_value) / nav
            metrics.net_exposure = (long_value - short_value) / nav
            metrics.largest_position_pct = max(abs(p.market_value) / nav for p in positions)

        # Track drawdown
        if nav > self.peak_value:
            self.peak_value = nav
        if self.peak_value > 0:
            metrics.current_drawdown = (self.peak_value - nav) / self.peak_value
            metrics.max_drawdown = max(metrics.current_drawdown, metrics.max_drawdown)

        # VaR calculation (historical method)
        if returns_history:
            portfolio_returns = self._compute_portfolio_returns(positions, returns_history, nav)
            if len(portfolio_returns) > 20:
                metrics.var_95 = self._compute_var(portfolio_returns, 0.95, nav)
                metrics.var_99 = self._compute_var(portfolio_returns, 0.99, nav)
                metrics.cvar_95 = self._compute_cvar(portfolio_returns, 0.95, nav)

                mean_ret = np.mean(portfolio_returns)
                std_ret = np.std(portfolio_returns)
                if std_ret > 0:
                    metrics.sharpe = (mean_ret / std_ret) * np.sqrt(252)

        # Beta
        if returns_history and market_returns:
            portfolio_returns = self._compute_portfolio_returns(positions, returns_history, nav)
            min_len = min(len(portfolio_returns), len(market_returns))
            if min_len > 20:
                port_r = np.array(portfolio_returns[-min_len:])
                mkt_r = np.array(market_returns[-min_len:])
                cov = np.cov(port_r, mkt_r)[0, 1]
                mkt_var = np.var(mkt_r)
                metrics.beta = cov / mkt_var if mkt_var > 0 else 0

        # Correlation
        if returns_history and len(positions) > 1:
            metrics.correlation_max = self._max_correlation(positions, returns_history)

        return metrics

    def _compute_portfolio_returns(
        self,
        positions: list[Position],
        returns_history: dict[str, list[float]],
        nav: float,
    ) -> list[float]:
        """Compute weighted portfolio return series."""
        if nav == 0:
            return []

        weights = {p.ticker: p.market_value / nav for p in positions}
        min_len = min(
            (len(r) for t, r in returns_history.items() if t in weights),
            default=0,
        )
        if min_len == 0:
            return []

        portfolio_returns = []
        for i in range(min_len):
            day_return = 0
            for ticker, weight in weights.items():
                if ticker in returns_history and i < len(returns_history[ticker]):
                    day_return += weight * returns_history[ticker][i]
            portfolio_returns.append(day_return)

        return portfolio_returns

    def _compute_var(self, returns: list[float], confidence: float, nav: float) -> float:
        """Historical VaR."""
        arr = np.array(returns)
        percentile = (1 - confidence) * 100
        var_return = np.percentile(arr, percentile)
        return abs(var_return * nav)

    def _compute_cvar(self, returns: list[float], confidence: float, nav: float) -> float:
        """Conditional VaR (Expected Shortfall)."""
        arr = np.array(returns)
        percentile = (1 - confidence) * 100
        var_return = np.percentile(arr, percentile)
        tail = arr[arr <= var_return]
        if len(tail) == 0:
            return self._compute_var(returns, confidence, nav)
        return abs(np.mean(tail) * nav)

    def _max_correlation(
        self,
        positions: list[Position],
        returns_history: dict[str, list[float]],
    ) -> float:
        """Find maximum pairwise correlation among positions."""
        tickers = [p.ticker for p in positions if p.ticker in returns_history]
        if len(tickers) < 2:
            return 0

        min_len = min(len(returns_history[t]) for t in tickers)
        if min_len < 20:
            return 0

        matrix = np.array([returns_history[t][-min_len:] for t in tickers])
        corr = np.corrcoef(matrix)
        np.fill_diagonal(corr, 0)
        return float(np.max(np.abs(corr)))

    def check_signal(
        self,
        signal_ticker: str,
        signal_direction: str,
        signal_quantity: float,
        signal_price: float,
        positions: list[Position],
        portfolio_value: float,
    ) -> tuple[bool, str, list[LimitCheck]]:
        """
        Check if a new signal passes all risk limits.
        Returns (approved, reason, checks).
        """
        checks = []

        if self.kill_switch_active:
            return False, "kill switch active", []

        # Position size check
        new_position_value = abs(signal_quantity * signal_price)
        if portfolio_value > 0:
            position_pct = new_position_value / portfolio_value
            utilization = position_pct / self.limits.max_position_pct
            checks.append(LimitCheck(
                passed=position_pct <= self.limits.max_position_pct,
                limit_name="max_position_pct",
                current_value=position_pct,
                limit_value=self.limits.max_position_pct,
                utilization=min(utilization, 1.0),
                severity="breach" if position_pct > self.limits.max_position_pct else (
                    "warning" if utilization > self.limits.warning_threshold else "ok"
                ),
            ))

        # Gross exposure check
        current_gross = sum(abs(p.market_value) for p in positions)
        new_gross = current_gross + new_position_value
        if portfolio_value > 0:
            gross_ratio = new_gross / portfolio_value
            utilization = gross_ratio / self.limits.max_gross_exposure
            checks.append(LimitCheck(
                passed=gross_ratio <= self.limits.max_gross_exposure,
                limit_name="max_gross_exposure",
                current_value=gross_ratio,
                limit_value=self.limits.max_gross_exposure,
                utilization=min(utilization, 1.0),
                severity="breach" if gross_ratio > self.limits.max_gross_exposure else (
                    "warning" if utilization > self.limits.warning_threshold else "ok"
                ),
            ))

        # Net exposure check
        long_val = sum(abs(p.market_value) for p in positions if p.quantity > 0)
        short_val = sum(abs(p.market_value) for p in positions if p.quantity < 0)
        if signal_direction == "long":
            long_val += new_position_value
        else:
            short_val += new_position_value

        if portfolio_value > 0:
            net_ratio = abs(long_val - short_val) / portfolio_value
            utilization = net_ratio / self.limits.max_net_exposure
            checks.append(LimitCheck(
                passed=net_ratio <= self.limits.max_net_exposure,
                limit_name="max_net_exposure",
                current_value=net_ratio,
                limit_value=self.limits.max_net_exposure,
                utilization=min(utilization, 1.0),
                severity="breach" if net_ratio > self.limits.max_net_exposure else (
                    "warning" if utilization > self.limits.warning_threshold else "ok"
                ),
            ))

        # Drawdown check
        current_dd = (self.peak_value - portfolio_value) / self.peak_value if self.peak_value > 0 else 0
        utilization = current_dd / self.limits.max_drawdown_pct if self.limits.max_drawdown_pct > 0 else 0
        checks.append(LimitCheck(
            passed=current_dd <= self.limits.max_drawdown_pct,
            limit_name="max_drawdown",
            current_value=current_dd,
            limit_value=self.limits.max_drawdown_pct,
            utilization=min(utilization, 1.0),
            severity="breach" if current_dd > self.limits.max_drawdown_pct else (
                "warning" if utilization > self.limits.warning_threshold else "ok"
            ),
        ))

        # Check for any breach
        breaches = [c for c in checks if not c.passed]
        if breaches:
            reasons = [f"{c.limit_name} ({c.current_value:.2%} > {c.limit_value:.2%})" for c in breaches]
            return False, f"rejected: {', '.join(reasons)}", checks

        return True, "passed", checks

    def stress_test(
        self,
        positions: list[Position],
        scenarios: dict[str, float] | None = None,
    ) -> dict[str, float]:
        """
        Run stress test scenarios.
        Returns dict of scenario name -> portfolio P&L.
        """
        if scenarios is None:
            scenarios = {
                "market_down_5pct": -0.05,
                "market_down_10pct": -0.10,
                "market_down_20pct": -0.20,
                "market_up_5pct": 0.05,
                "market_up_10pct": 0.10,
            }

        results = {}
        for name, shock in scenarios.items():
            pnl = 0
            for pos in positions:
                # Simplified: assume all positions have beta 1
                price_change = pos.current_price * shock
                pnl += pos.quantity * price_change
            results[name] = round(pnl, 2)

        return results

    def activate_kill_switch(self, reason: KillSwitchReason, portfolio_value: float = 0, details: str = ""):
        """Activate emergency kill switch. Auto-triggered, no approval needed."""
        self.kill_switch_active = True
        event = KillSwitchEvent(
            reason=reason,
            triggered_at=datetime.utcnow(),
            portfolio_value=portfolio_value,
            details=details,
        )
        self.kill_switch_history.append(event)
        log.critical(f"KILL SWITCH ACTIVATED: {reason.value} - {details}")

    def deactivate_kill_switch(self):
        """Deactivate kill switch. Only callable after CIO approval."""
        self.kill_switch_active = False
        log.info("kill switch deactivated (CIO approved)")

    def check_auto_triggers(self, portfolio_value: float, daily_pnl: float):
        """Check conditions that auto-trigger kill switch."""
        if self.kill_switch_active:
            return

        # Max drawdown
        if self.peak_value > 0:
            dd = (self.peak_value - portfolio_value) / self.peak_value
            if dd > self.limits.max_drawdown_pct:
                self.activate_kill_switch(
                    KillSwitchReason.MAX_DRAWDOWN,
                    portfolio_value,
                    f"drawdown {dd:.1%} exceeds limit {self.limits.max_drawdown_pct:.1%}",
                )
                return

        # Daily loss
        if self.daily_start_value > 0:
            daily_loss = (self.daily_start_value - portfolio_value) / self.daily_start_value
            if daily_loss > self.limits.max_daily_loss_pct:
                self.activate_kill_switch(
                    KillSwitchReason.DAILY_LOSS,
                    portfolio_value,
                    f"daily loss {daily_loss:.1%} exceeds limit {self.limits.max_daily_loss_pct:.1%}",
                )
                return

    def set_daily_start(self, value: float):
        """Set portfolio value at start of trading day."""
        self.daily_start_value = value
        if value > self.peak_value:
            self.peak_value = value
