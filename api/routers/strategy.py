from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class StrategyCreate(BaseModel):
    name: str
    description: str = ""
    module_path: str
    parameters: dict = {}
    risk_budget: float = 0.05


class StrategyDeploy(BaseModel):
    mode: str  # backtest, paper, live
    account_id: str = ""  # broker account to deploy to


@router.get("/")
async def list_strategies():
    """List all registered strategies."""
    return {"strategies": []}


@router.post("/")
async def register_strategy(strategy: StrategyCreate):
    """Register a new strategy."""
    return {"id": 0, "name": strategy.name, "status": "registered"}


@router.get("/{strategy_id}")
async def get_strategy(strategy_id: int):
    """Get strategy details and performance."""
    return {"id": strategy_id}


@router.get("/{strategy_id}/performance")
async def get_strategy_performance(strategy_id: int):
    """Get strategy performance metrics."""
    return {"id": strategy_id, "performance": {}}


@router.put("/{strategy_id}/deploy")
async def deploy_strategy(strategy_id: int, deploy: StrategyDeploy):
    """Deploy strategy to a broker account (requires CIO approval for live)."""
    return {
        "id": strategy_id,
        "mode": deploy.mode,
        "account_id": deploy.account_id,
        "status": "pending_approval",
    }


@router.get("/{strategy_id}/deployments")
async def get_deployments(strategy_id: int):
    """List all broker accounts this strategy is deployed to."""
    return {"strategy_id": strategy_id, "deployments": []}


@router.delete("/{strategy_id}/deployments/{account_id}")
async def stop_deployment(strategy_id: int, account_id: str):
    """Stop a strategy deployment on a specific broker account."""
    return {
        "strategy_id": strategy_id,
        "account_id": account_id,
        "status": "stopped",
    }
