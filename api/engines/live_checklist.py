"""
Live trading readiness checklist.
All conditions must pass before live mode can be activated.
"""
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

log = logging.getLogger("icarus.live-checklist")


@dataclass
class ChecklistItem:
    name: str
    passed: bool
    message: str
    required: bool = True


class LiveChecklist:
    """Validates readiness for live trading."""

    def run(
        self,
        live_enabled_flag: bool,
        risk_limits_set: bool,
        kill_switch_last_tested: datetime | None,
        paper_trading_days: int,
        strategy_paper_days: dict[str, int],
        ib_connected: bool,
        data_feeds_healthy: bool,
        pending_approvals: int,
    ) -> list[ChecklistItem]:
        """Run all live readiness checks."""
        checks = []

        # Explicit opt-in
        checks.append(ChecklistItem(
            name="LIVE_TRADING_ENABLED flag",
            passed=live_enabled_flag,
            message="set to true" if live_enabled_flag else "must set LIVE_TRADING_ENABLED=true",
        ))

        # Risk limits configured
        checks.append(ChecklistItem(
            name="Risk limits configured",
            passed=risk_limits_set,
            message="risk limits are set" if risk_limits_set else "must configure risk limits before going live",
        ))

        # Kill switch tested recently
        if kill_switch_last_tested:
            days_since = (datetime.utcnow() - kill_switch_last_tested).days
            tested_recently = days_since <= 7
        else:
            days_since = -1
            tested_recently = False

        checks.append(ChecklistItem(
            name="Kill switch tested within 7 days",
            passed=tested_recently,
            message=f"last tested {days_since} days ago" if days_since >= 0 else "never tested",
        ))

        # Paper trading history
        min_paper_days = 30
        checks.append(ChecklistItem(
            name=f"Paper trading for {min_paper_days}+ days",
            passed=paper_trading_days >= min_paper_days,
            message=f"{paper_trading_days} days of paper trading",
        ))

        # Per-strategy paper history
        for strategy_name, days in strategy_paper_days.items():
            checks.append(ChecklistItem(
                name=f"Strategy '{strategy_name}' paper tested",
                passed=days >= min_paper_days,
                message=f"{days} days on paper" if days > 0 else "no paper trading history",
            ))

        # IB connection
        checks.append(ChecklistItem(
            name="IB Gateway connected",
            passed=ib_connected,
            message="connected" if ib_connected else "not connected",
        ))

        # Data feeds
        checks.append(ChecklistItem(
            name="Data feeds healthy",
            passed=data_feeds_healthy,
            message="all feeds operational" if data_feeds_healthy else "one or more feeds down",
        ))

        # No pending approvals
        checks.append(ChecklistItem(
            name="No pending approvals",
            passed=pending_approvals == 0,
            message=f"{pending_approvals} pending" if pending_approvals > 0 else "all clear",
        ))

        return checks

    def is_ready(self, checks: list[ChecklistItem]) -> tuple[bool, list[str]]:
        """Check if all required items pass."""
        failures = [c for c in checks if c.required and not c.passed]
        return len(failures) == 0, [f"{c.name}: {c.message}" for c in failures]


class LiveSafeguards:
    """Additional safeguards for live trading mode."""

    def __init__(self):
        self.max_order_rate = 10  # max orders per minute
        self.order_timestamps: list[datetime] = []
        self.position_size_multiplier = 0.5  # start at 50% of paper sizes
        self.reconciliation_interval_sec = 300  # reconcile with IB every 5 min

    def check_order_rate(self) -> bool:
        """Enforce order rate limit."""
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        self.order_timestamps = [t for t in self.order_timestamps if t > cutoff]

        if len(self.order_timestamps) >= self.max_order_rate:
            log.warning(f"order rate limit reached: {len(self.order_timestamps)}/{self.max_order_rate} per minute")
            return False

        self.order_timestamps.append(now)
        return True

    def adjust_size_for_live(self, paper_quantity: float) -> float:
        """Scale down position sizes for initial live period."""
        return int(paper_quantity * self.position_size_multiplier)

    def reconcile_positions(self, our_positions: dict, ib_positions: dict) -> list[dict]:
        """Compare our position records with IB account data."""
        discrepancies = []

        all_tickers = set(our_positions) | set(ib_positions)
        for ticker in all_tickers:
            our_qty = our_positions.get(ticker, {}).get("quantity", 0)
            ib_qty = ib_positions.get(ticker, {}).get("quantity", 0)

            if abs(our_qty - ib_qty) > 0.01:
                discrepancies.append({
                    "ticker": ticker,
                    "our_quantity": our_qty,
                    "ib_quantity": ib_qty,
                    "difference": our_qty - ib_qty,
                })

        if discrepancies:
            log.warning(f"position reconciliation found {len(discrepancies)} discrepancies")

        return discrepancies
