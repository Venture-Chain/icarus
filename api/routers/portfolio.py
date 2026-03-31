from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class KillSwitchRequest(BaseModel):
    account_id: str | None = None  # None = flatten all accounts


@router.get("/positions")
async def get_positions(account_id: str | None = None, request: Request = None):
    """Get current portfolio positions. Filter by account_id if provided."""
    if account_id and request:
        registry = request.app.state.account_registry
        broker = registry.get(account_id)
        if broker and broker.connected:
            positions = await broker.get_positions()
            return {
                "account_id": account_id,
                "positions": [
                    {
                        "ticker": p.ticker,
                        "quantity": p.quantity,
                        "avg_cost": p.avg_cost,
                        "current_price": p.current_price,
                        "market_value": p.market_value,
                        "unrealized_pnl": p.unrealized_pnl,
                    }
                    for p in positions
                ],
            }
    return {"positions": []}


@router.get("/risk")
async def get_risk_metrics(account_id: str | None = None, request: Request = None):
    """Get current portfolio risk metrics from broker positions."""
    if not request:
        return {"error": "no request context"}

    registry = request.app.state.account_registry
    all_positions = []

    if account_id:
        broker = registry.get(account_id)
        if broker and broker.connected:
            all_positions = await broker.get_positions()
    else:
        for broker in registry.all():
            if broker.connected:
                positions = await broker.get_positions()
                all_positions.extend(positions)

    total_value = sum(p.market_value for p in all_positions if p.market_value)
    total_pnl = sum(p.unrealized_pnl for p in all_positions if p.unrealized_pnl)
    long_exposure = sum(p.market_value for p in all_positions if p.quantity and p.quantity > 0 and p.market_value)
    short_exposure = sum(abs(p.market_value) for p in all_positions if p.quantity and p.quantity < 0 and p.market_value)
    largest_pct = 0
    if total_value > 0:
        largest_pct = max(
            (abs(p.market_value) / total_value * 100 for p in all_positions if p.market_value),
            default=0,
        )

    return {
        "account_id": account_id,
        "positions_count": len(all_positions),
        "portfolio_value": total_value,
        "unrealized_pnl": total_pnl,
        "long_exposure": long_exposure,
        "short_exposure": short_exposure,
        "net_exposure": long_exposure - short_exposure,
        "gross_exposure": long_exposure + short_exposure,
        "largest_position_pct": round(largest_pct, 2),
    }


@router.post("/optimize")
async def optimize_portfolio():
    """Run portfolio optimizer, return suggested trades."""
    return {"suggestions": []}


@router.post("/kill-switch")
async def activate_kill_switch(body: KillSwitchRequest = KillSwitchRequest(), request: Request = None):
    """Emergency: flatten positions. Specify account_id for single account, omit for all."""
    if not request:
        return {"status": "error", "message": "no request context"}

    registry = request.app.state.account_registry

    if body.account_id:
        broker = registry.get(body.account_id)
        if not broker:
            return {"status": "error", "message": f"account {body.account_id} not found"}
        if not broker.connected:
            return {"status": "error", "message": f"account {body.account_id} not connected"}

        positions = await broker.get_positions()
        flattened = 0
        for pos in positions:
            if pos.quantity == 0:
                continue
            action = "SELL" if pos.quantity > 0 else "BUY"
            await broker.place_order(
                ticker=pos.ticker, action=action,
                quantity=abs(pos.quantity), order_type="MKT",
            )
            flattened += 1
        return {
            "status": "activated",
            "account_id": body.account_id,
            "positions_flattened": flattened,
        }

    # Flatten all accounts
    total = 0
    account_results = {}
    for broker in registry.all():
        if not broker.connected:
            continue
        positions = await broker.get_positions()
        count = 0
        for pos in positions:
            if pos.quantity == 0:
                continue
            action = "SELL" if pos.quantity > 0 else "BUY"
            await broker.place_order(
                ticker=pos.ticker, action=action,
                quantity=abs(pos.quantity), order_type="MKT",
            )
            count += 1
        account_results[broker.account_id] = count
        total += count

    return {
        "status": "activated",
        "positions_flattened": total,
        "per_account": account_results,
    }


