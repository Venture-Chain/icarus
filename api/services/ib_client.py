"""
Interactive Brokers client service.
Wraps the official ibapi in an async-friendly interface.
"""
from config import settings


class IBClient:
    def __init__(self):
        self.host = settings.ib_host
        self.port = settings.ib_port
        self.connected = False

    async def connect(self):
        """Connect to IB Gateway."""
        self.connected = True

    async def disconnect(self):
        """Disconnect from IB Gateway."""
        self.connected = False

    async def get_account_summary(self) -> dict:
        """Get account balance, buying power, etc."""
        return {}

    async def get_positions(self) -> list:
        """Get current positions from IB."""
        return []

    async def place_order(self, ticker: str, action: str, quantity: float, order_type: str = "MKT", limit_price: float = None):
        """Place an order through IB."""
        return {"status": "submitted"}

    async def cancel_order(self, order_id: int):
        """Cancel a pending order."""
        return {"status": "cancelled"}

    async def get_historical_data(self, ticker: str, duration: str = "1 Y", bar_size: str = "1 day"):
        """Get historical OHLCV data from IB."""
        return []
