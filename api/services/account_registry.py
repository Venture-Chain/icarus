"""
Account registry. Central store of all broker instances keyed by account ID.
Instantiated once at startup, stored on app.state.
"""
import logging

from services.broker_base import BaseBroker, BrokerType

log = logging.getLogger("icarus.registry")


class AccountRegistry:
    """Holds all registered broker accounts."""

    def __init__(self) -> None:
        self._accounts: dict[str, BaseBroker] = {}

    def register(self, broker: BaseBroker) -> None:
        self._accounts[broker.account_id] = broker
        log.info(
            "Registered account: %s (%s, %s)",
            broker.account_id, broker.broker_type.value, broker.mode.value,
        )

    def get(self, account_id: str) -> BaseBroker | None:
        return self._accounts.get(account_id)

    def list_accounts(self) -> list[dict]:
        return [broker.health_check() for broker in self._accounts.values()]

    def get_by_type(self, broker_type: BrokerType) -> list[BaseBroker]:
        return [b for b in self._accounts.values() if b.broker_type == broker_type]

    def all(self) -> list[BaseBroker]:
        return list(self._accounts.values())

    async def connect_all(self) -> dict[str, bool]:
        results = {}
        for account_id, broker in self._accounts.items():
            try:
                results[account_id] = await broker.connect()
            except Exception as e:
                log.error("Failed to connect %s: %s", account_id, e)
                results[account_id] = False
        return results

    async def disconnect_all(self) -> None:
        for broker in self._accounts.values():
            try:
                await broker.disconnect()
            except Exception as e:
                log.error("Error disconnecting %s: %s", broker.account_id, e)

    async def health_check_all(self) -> list[dict]:
        return [broker.health_check() for broker in self._accounts.values()]
