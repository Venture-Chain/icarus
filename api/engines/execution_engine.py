"""
Order execution engine. Converts signals to IB orders.
All orders pass through risk engine before submission.
"""


class ExecutionEngine:
    def __init__(self, ib_client=None, risk_engine=None):
        self.ib_client = ib_client
        self.risk_engine = risk_engine

    async def execute_signal(self, signal, portfolio_state):
        """Convert a signal to an order after risk check."""
        approved, reason = self.risk_engine.check_signal(signal, portfolio_state)
        if not approved:
            return {"status": "rejected", "reason": reason}
        return {"status": "submitted"}

    async def flatten_all(self):
        """Emergency: close all positions."""
        pass
