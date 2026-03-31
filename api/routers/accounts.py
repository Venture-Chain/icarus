"""Broker accounts API. Multi-broker orchestration endpoints."""
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
async def list_accounts(request: Request):
    """List all registered broker accounts with connection status."""
    registry = request.app.state.account_registry
    return registry.list_accounts()


@router.get("/{account_id}")
async def get_account(account_id: str, request: Request):
    """Get detailed info for a specific broker account."""
    registry = request.app.state.account_registry
    broker = registry.get(account_id)
    if not broker:
        return {"error": f"account {account_id} not found"}
    summary = await broker.get_account_summary()
    return {
        **broker.health_check(),
        "net_liquidation": summary.net_liquidation,
        "buying_power": summary.buying_power,
        "cash": summary.cash,
        "unrealized_pnl": summary.unrealized_pnl,
    }


@router.get("/{account_id}/positions")
async def get_account_positions(account_id: str, request: Request):
    """Get positions for a specific broker account."""
    registry = request.app.state.account_registry
    broker = registry.get(account_id)
    if not broker:
        return {"error": f"account {account_id} not found"}
    positions = await broker.get_positions()
    return [
        {
            "ticker": p.ticker,
            "quantity": p.quantity,
            "avg_cost": p.avg_cost,
            "current_price": p.current_price,
            "market_value": p.market_value,
            "unrealized_pnl": p.unrealized_pnl,
        }
        for p in positions
    ]


@router.get("/{account_id}/health")
async def account_health(account_id: str, request: Request):
    """Health check for a specific broker account."""
    registry = request.app.state.account_registry
    broker = registry.get(account_id)
    if not broker:
        return {"error": f"account {account_id} not found"}
    return broker.health_check()


@router.post("/{account_id}/reconnect")
async def reconnect_account(account_id: str, request: Request):
    """Disconnect and reconnect a broker account."""
    registry = request.app.state.account_registry
    broker = registry.get(account_id)
    if not broker:
        return {"error": f"account {account_id} not found"}
    await broker.disconnect()
    success = await broker.connect()
    return {"account_id": account_id, "connected": success}


