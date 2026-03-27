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


@router.get("/live-checklist")
async def get_live_checklist():
    """Check if the system is ready for live trading."""
    from engines.live_checklist import LiveChecklist
    checklist = LiveChecklist()
    # Placeholder values, will be wired to real state
    checks = checklist.run(
        live_enabled_flag=False,
        risk_limits_set=True,
        kill_switch_last_tested=None,
        paper_trading_days=0,
        strategy_paper_days={},
        ib_connected=False,
        data_feeds_healthy=False,
        pending_approvals=0,
    )
    ready, failures = checklist.is_ready(checks)
    return {
        "ready": ready,
        "checks": [{"name": c.name, "passed": c.passed, "message": c.message} for c in checks],
        "failures": failures,
    }
