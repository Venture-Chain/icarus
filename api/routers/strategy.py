from fastapi import APIRouter
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
    """Deploy strategy to paper or live (requires CIO approval for live)."""
    return {"id": strategy_id, "mode": deploy.mode, "status": "pending_approval"}
