"""
Interactive Brokers client service.
Wraps official ibapi in async interface using threading bridge.
"""
import asyncio
import threading
from datetime import datetime
from typing import Any

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.execution import ExecutionFilter
from ibapi.order import Order
from ibapi.wrapper import EWrapper

from config import settings


class IBWrapper(EWrapper):
    """Receives callbacks from IB Gateway."""

    def __init__(self):
        super().__init__()
        self._account_summary: dict[str, Any] = {}
        self._positions: list[dict] = []
        self._historical_data: list[dict] = []
        self._order_status: dict[int, dict] = {}
        self._next_order_id: int = 0
        self._events: dict[str, asyncio.Event] = {}
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _set_event(self, name: str) -> None:
        if self._loop and name in self._events:
            self._loop.call_soon_threadsafe(self._events[name].set)

    def nextValidId(self, orderId: int) -> None:
        self._next_order_id = orderId
        self._set_event("connected")

    def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:
        # Codes 2104, 2106, 2158 are info messages, not errors
        if errorCode in (2104, 2106, 2158):
            return
        print(f"IB Error {errorCode}: {errorString}")

    def accountSummary(self, reqId: int, account: str, tag: str, value: str, currency: str) -> None:
        self._account_summary[tag] = {"value": value, "currency": currency}

    def accountSummaryEnd(self, reqId: int) -> None:
        self._set_event("account_summary")

    def position(self, account: str, contract: Contract, pos: float, avgCost: float) -> None:
        self._positions.append({
            "account": account,
            "ticker": contract.symbol,
            "sec_type": contract.secType,
            "exchange": contract.exchange,
            "quantity": pos,
            "avg_cost": avgCost,
        })

    def positionEnd(self) -> None:
        self._set_event("positions")

    def historicalData(self, reqId: int, bar: Any) -> None:
        self._historical_data.append({
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": int(bar.volume),
            "wap": bar.wap,
            "count": bar.barCount,
        })

    def historicalDataEnd(self, reqId: int, start: str, end: str) -> None:
        self._set_event("historical_data")

    def orderStatus(self, orderId: int, status: str, filled: float,
                    remaining: float, avgFillPrice: float, permId: int,
                    parentId: int, lastFillPrice: float, clientId: int,
                    whyHeld: str, mktCapPrice: float) -> None:
        self._order_status[orderId] = {
            "order_id": orderId,
            "status": status,
            "filled": filled,
            "remaining": remaining,
            "avg_fill_price": avgFillPrice,
        }
        self._set_event(f"order_{orderId}")

    def openOrder(self, orderId: int, contract: Contract, order: Order, orderState: Any) -> None:
        pass

    def execDetails(self, reqId: int, contract: Contract, execution: Any) -> None:
        pass


class IBClient:
    """Async interface to Interactive Brokers."""

    def __init__(self) -> None:
        self.host: str = settings.ib_host
        self.port: int = settings.ib_port
        self.client_id: int = 1
        self.connected: bool = False
        self._wrapper: IBWrapper = IBWrapper()
        self._client: EClient = EClient(self._wrapper)
        self._thread: threading.Thread | None = None

    async def connect(self) -> bool:
        """Connect to IB Gateway. Returns True on success."""
        loop = asyncio.get_event_loop()
        self._wrapper.set_loop(loop)
        event = asyncio.Event()
        self._wrapper._events["connected"] = event

        self._client.connect(self.host, self.port, self.client_id)
        self._thread = threading.Thread(target=self._client.run, daemon=True)
        self._thread.start()

        try:
            await asyncio.wait_for(event.wait(), timeout=10)
            self.connected = True
            return True
        except asyncio.TimeoutError:
            self.connected = False
            return False

    async def disconnect(self) -> None:
        """Disconnect from IB Gateway."""
        if self.connected:
            self._client.disconnect()
            self.connected = False

    async def get_account_summary(self) -> dict[str, Any]:
        """Get account balance, buying power, P&L."""
        self._wrapper._account_summary = {}
        event = asyncio.Event()
        self._wrapper._events["account_summary"] = event

        self._client.reqAccountSummary(
            9001, "All",
            "NetLiquidation,TotalCashValue,BuyingPower,UnrealizedPnL,RealizedPnL,GrossPositionValue"
        )

        try:
            await asyncio.wait_for(event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass

        self._client.cancelAccountSummary(9001)
        return self._wrapper._account_summary

    async def get_positions(self) -> list[dict]:
        """Get current positions from IB."""
        self._wrapper._positions = []
        event = asyncio.Event()
        self._wrapper._events["positions"] = event

        self._client.reqPositions()

        try:
            await asyncio.wait_for(event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass

        self._client.cancelPositions()
        return self._wrapper._positions

    async def get_historical_data(
        self,
        ticker: str,
        duration: str = "1 Y",
        bar_size: str = "1 day",
        what_to_show: str = "MIDPOINT",
        use_rth: bool = True,
    ) -> list[dict]:
        """Get historical OHLCV from IB."""
        self._wrapper._historical_data = []
        event = asyncio.Event()
        self._wrapper._events["historical_data"] = event

        contract = self._make_stock_contract(ticker)
        end_dt = datetime.now().strftime("%Y%m%d-%H:%M:%S")

        self._client.reqHistoricalData(
            reqId=4001,
            contract=contract,
            endDateTime=end_dt,
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow=what_to_show,
            useRTH=1 if use_rth else 0,
            formatDate=1,
            keepUpToDate=False,
            chartOptions=[],
        )

        try:
            await asyncio.wait_for(event.wait(), timeout=30)
        except asyncio.TimeoutError:
            pass

        return self._wrapper._historical_data

    async def place_order(
        self,
        ticker: str,
        action: str,
        quantity: float,
        order_type: str = "MKT",
        limit_price: float | None = None,
    ) -> dict:
        """Place an order. Returns order ID and initial status."""
        contract = self._make_stock_contract(ticker)

        order = Order()
        order.action = action.upper()
        order.totalQuantity = abs(quantity)
        order.orderType = order_type.upper()
        if limit_price and order_type.upper() == "LMT":
            order.lmtPrice = limit_price

        order_id = self._wrapper._next_order_id
        self._wrapper._next_order_id += 1

        event = asyncio.Event()
        self._wrapper._events[f"order_{order_id}"] = event

        self._client.placeOrder(order_id, contract, order)

        try:
            await asyncio.wait_for(event.wait(), timeout=10)
        except asyncio.TimeoutError:
            pass

        status = self._wrapper._order_status.get(order_id, {"status": "submitted"})
        return {"order_id": order_id, **status}

    async def cancel_order(self, order_id: int) -> dict:
        """Cancel a pending order."""
        self._client.cancelOrder(order_id, "")
        return {"order_id": order_id, "status": "cancel_requested"}

    def _make_stock_contract(self, ticker: str) -> Contract:
        """Create a US stock contract."""
        contract = Contract()
        contract.symbol = ticker
        contract.secType = "STK"
        contract.exchange = "SMART"
        contract.currency = "USD"
        return contract
