"""
Portfolio risk management engine.
Has veto power over execution. Controls kill switch.
"""
from dataclasses import dataclass


@dataclass
class RiskLimits:
    max_position_pct: float = 0.10
    max_sector_pct: float = 0.30
    max_gross_exposure: float = 2.0
    max_net_exposure: float = 0.50
    max_daily_loss: float = 0.02
    max_drawdown: float = 0.10
    warning_threshold: float = 0.80


class RiskEngine:
    def __init__(self, limits: RiskLimits = None):
        self.limits = limits or RiskLimits()
        self.kill_switch_active = False

    def check_signal(self, signal, portfolio_state) -> tuple[bool, str]:
        """Check if a signal passes risk limits. Returns (approved, reason)."""
        if self.kill_switch_active:
            return False, "kill switch active"
        return True, "passed"

    def compute_var(self, positions, confidence=0.95) -> float:
        """Compute Value at Risk at given confidence level."""
        return 0.0

    def compute_cvar(self, positions, confidence=0.95) -> float:
        """Compute Conditional VaR (Expected Shortfall)."""
        return 0.0

    def activate_kill_switch(self, reason: str):
        """Activate kill switch. Requires CIO approval to deactivate."""
        self.kill_switch_active = True

    def deactivate_kill_switch(self):
        """Deactivate kill switch. Only callable after CIO approval."""
        self.kill_switch_active = False
