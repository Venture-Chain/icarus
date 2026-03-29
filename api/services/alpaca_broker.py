"""
Alpaca Markets trading client.
Implements BaseBroker for order execution, positions, and account data.
Separate from alpaca.py (data-only service using data.alpaca.markets).
"""
import logging
from typing import Any

import httpx

from services.broker_base import (
    AccountMode,
    AccountSummary,
    BaseBroker,
    BrokerOrder,
    BrokerPosition,
    BrokerType,
)

log = logging.getLogger("icarus.alpaca_broker")

PAPER_URL = "https://paper-api.alpaca.markets"
LIVE_URL = "https://api.alpaca.markets"


class AlpacaBroker(BaseBroker):
    """Alpaca Markets trading client. Supports paper and live accounts."""

    def __init__(
        self,
        account_id: str,
        mode: AccountMode,
        api_key: str,
        api_secret: str,
    ) -> None:
        self._account_id = account_id
        self._mode = mode
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = PAPER_URL if mode == AccountMode.PAPER else LIVE_URL
        self._connected = False
        self._headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
        }

    @property
    def broker_type(self) -> BrokerType:
        return BrokerType.ALPACA

    @property
    def account_id(self) -> str:
        return self._account_id

    @property
    def mode(self) -> AccountMode:
        return self._mode

    @property
    def connected(self) -> bool:
        return self._connected

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict | list | None:
        url = f"{self._base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.request(
                    method, url, headers=self._headers,
                    json=json, params=params,
                )
                resp.raise_for_status()
                if resp.status_code == 204:
                    return {}
                return resp.json()
        except httpx.HTTPStatusError as e:
            log.error("Alpaca %s %d: %s", path, e.response.status_code, e.response.text[:200])
            return None
        except httpx.RequestError as e:
            log.error("Alpaca request failed: %s", str(e))
            return None

    async def connect(self) -> bool:
        """Verify credentials by fetching account info."""
        result = await self._request("GET", "/v2/account")
        if result and isinstance(result, dict) and "id" in result:
            self._connected = True
            log.info("Connected to Alpaca [%s] (%s)", self._account_id, self._mode.value)
            return True
        self._connected = False
        log.error("Failed to connect Alpaca account %s", self._account_id)
        return False

    async def disconnect(self) -> None:
        self._connected = False

    async def place_order(
        self,
        ticker: str,
        action: str,
        quantity: float,
        order_type: str = "MKT",
        limit_price: float | None = None,
    ) -> BrokerOrder:
        """Place an order via Alpaca REST API."""
        body: dict[str, Any] = {
            "symbol": ticker,
            "qty": str(abs(quantity)),
            "side": "sell" if action.upper() == "SELL" else "buy",
            "type": "limit" if order_type.upper() == "LMT" else "market",
            "time_in_force": "day",
        }
        if limit_price and order_type.upper() == "LMT":
            body["limit_price"] = str(limit_price)

        result = await self._request("POST", "/v2/orders", json=body)
        if not result or not isinstance(result, dict):
            return BrokerOrder(
                broker_order_id="",
                status="rejected",
                ticker=ticker,
                action=action.upper(),
                quantity=abs(quantity),
                account_id=self._account_id,
            )

        return BrokerOrder(
            broker_order_id=result.get("id", ""),
            status=self._map_status(result.get("status", "")),
            ticker=ticker,
            action=action.upper(),
            quantity=abs(quantity),
            filled_quantity=float(result.get("filled_qty", 0)),
            avg_fill_price=float(result.get("filled_avg_price") or 0),
            account_id=self._account_id,
        )

    async def cancel_order(self, broker_order_id: str) -> BrokerOrder:
        await self._request("DELETE", f"/v2/orders/{broker_order_id}")
        return BrokerOrder(
            broker_order_id=broker_order_id,
            status="cancel_requested",
            account_id=self._account_id,
        )

    async def get_positions(self) -> list[BrokerPosition]:
        result = await self._request("GET", "/v2/positions")
        if not result or not isinstance(result, list):
            return []
        return [
            BrokerPosition(
                ticker=p.get("symbol", ""),
                quantity=float(p.get("qty", 0)),
                avg_cost=float(p.get("avg_entry_price", 0)),
                current_price=float(p.get("current_price", 0)),
                market_value=float(p.get("market_value", 0)),
                unrealized_pnl=float(p.get("unrealized_pl", 0)),
                account_id=self._account_id,
            )
            for p in result
        ]

    async def get_account_summary(self) -> AccountSummary:
        result = await self._request("GET", "/v2/account")
        if not result or not isinstance(result, dict):
            return AccountSummary(account_id=self._account_id)
        return AccountSummary(
            account_id=self._account_id,
            net_liquidation=float(result.get("equity", 0)),
            buying_power=float(result.get("buying_power", 0)),
            cash=float(result.get("cash", 0)),
            unrealized_pnl=float(result.get("unrealized_pl", 0)),
            realized_pnl=float(result.get("realized_pl", 0) or 0),
            gross_position_value=float(result.get("long_market_value", 0))
            + float(result.get("short_market_value", 0)),
        )

    async def get_order_status(self, broker_order_id: str) -> BrokerOrder:
        result = await self._request("GET", f"/v2/orders/{broker_order_id}")
        if not result or not isinstance(result, dict):
            return BrokerOrder(
                broker_order_id=broker_order_id,
                status="unknown",
                account_id=self._account_id,
            )
        return BrokerOrder(
            broker_order_id=broker_order_id,
            status=self._map_status(result.get("status", "")),
            ticker=result.get("symbol", ""),
            action=result.get("side", "").upper(),
            quantity=float(result.get("qty", 0)),
            filled_quantity=float(result.get("filled_qty", 0)),
            avg_fill_price=float(result.get("filled_avg_price") or 0),
            account_id=self._account_id,
        )

    @staticmethod
    def _map_status(alpaca_status: str) -> str:
        """Map Alpaca order statuses to normalized statuses."""
        mapping = {
            "new": "submitted",
            "accepted": "submitted",
            "pending_new": "submitted",
            "partially_filled": "partial",
            "filled": "filled",
            "canceled": "cancelled",
            "expired": "cancelled",
            "rejected": "rejected",
            "pending_cancel": "cancel_requested",
            "pending_replace": "submitted",
        }
        return mapping.get(alpaca_status, alpaca_status)
