from fastapi import APIRouter

router = APIRouter()


@router.get("/positions")
async def get_positions():
    """Get current portfolio positions."""
    return {"positions": []}


@router.get("/risk")
async def get_risk_metrics():
    """Get current portfolio risk metrics."""
    return {
        "var_95": 0,
        "cvar_95": 0,
        "max_drawdown": 0,
        "current_drawdown": 0,
        "net_exposure": 0,
        "gross_exposure": 0,
        "beta": 0,
        "sharpe": 0,
    }


@router.post("/optimize")
async def optimize_portfolio():
    """Run portfolio optimizer, return suggested trades."""
    return {"suggestions": []}


@router.post("/kill-switch")
async def activate_kill_switch():
    """Emergency: flatten all positions immediately."""
    return {"status": "activated", "positions_flattened": 0}
