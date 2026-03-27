from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class BacktestRequest(BaseModel):
    strategy_name: str
    universe: list[str] = []
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 100000
    parameters: dict = {}


class FactorAnalysisRequest(BaseModel):
    factor_name: str
    universe: list[str] = []
    start_date: str = ""
    end_date: str = ""


class ResearchLogEntry(BaseModel):
    hypothesis: str
    methodology: str = ""
    findings: str = ""
    data_sources: list[str] = []


@router.post("/backtest/run")
async def run_backtest(request: BacktestRequest):
    """Run a walk-forward backtest."""
    return {"id": 0, "status": "queued", "strategy": request.strategy_name}


@router.get("/backtest/{backtest_id}")
async def get_backtest_results(backtest_id: int):
    """Get results of a backtest run."""
    return {"id": backtest_id, "status": "pending", "results": {}}


@router.post("/factor/analyze")
async def analyze_factor(request: FactorAnalysisRequest):
    """Run factor analysis: quintile spreads, IC, decay."""
    return {"factor": request.factor_name, "analysis": {}}


@router.post("/log")
async def log_research(entry: ResearchLogEntry):
    """Save a research log entry."""
    return {"id": 0, "status": "saved"}


@router.get("/log")
async def get_research_log():
    """Get all research log entries."""
    return {"entries": []}
