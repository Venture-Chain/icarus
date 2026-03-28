from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from config import settings
from engines.quantum_engine import QuantumEngine, HLQ_AVAILABLE, HLQ_VERSION

router = APIRouter()


def _check_enabled():
    if not settings.quantum_enabled:
        raise HTTPException(status_code=404, detail="quantum module disabled")


# ── Request models ───────────────────────────────────────────────────────────


class OptimizeRequest(BaseModel):
    tickers: list[str] = ["AAPL", "GOOGL", "MSFT", "AMZN"]
    expected_returns: dict[str, float] = {
        "AAPL": 0.12, "GOOGL": 0.10, "MSFT": 0.11, "AMZN": 0.14,
    }
    covariance_matrix: list[list[float]] = [
        [0.04, 0.006, 0.008, 0.010],
        [0.006, 0.05, 0.009, 0.007],
        [0.008, 0.009, 0.03, 0.008],
        [0.010, 0.007, 0.008, 0.06],
    ]


class RiskRequest(BaseModel):
    portfolio_weights: dict[str, float] = {
        "AAPL": 0.30, "GOOGL": 0.25, "MSFT": 0.25, "AMZN": 0.20,
    }
    volatilities: dict[str, float] = {
        "AAPL": 0.22, "GOOGL": 0.25, "MSFT": 0.20, "AMZN": 0.28,
    }
    confidence_level: float = 0.95
    horizon_days: int = 1


class PriceRequest(BaseModel):
    spot: float = 150.0
    strike: float = 155.0
    volatility: float = 0.25
    risk_free_rate: float = 0.045
    time_to_expiry: float = 0.25


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/status")
async def quantum_status():
    """Check quantum module availability."""
    return {
        "enabled": settings.quantum_enabled,
        "hlquantum_installed": HLQ_AVAILABLE,
        "hlquantum_version": HLQ_VERSION,
        "backend": settings.quantum_backend,
        "shots": settings.quantum_shots,
        "available_models": [
            "portfolio_optimization",
            "risk_analysis",
            "option_pricing",
        ],
    }


@router.post("/optimize")
async def quantum_optimize(request: OptimizeRequest):
    """QAOA portfolio optimization vs classical mean-variance."""
    _check_enabled()

    import numpy as np

    engine = QuantumEngine(shots=settings.quantum_shots, backend=settings.quantum_backend)
    cov = np.array(request.covariance_matrix)
    result = engine.optimize_portfolio(
        tickers=request.tickers,
        expected_returns=request.expected_returns,
        covariance_matrix=cov,
    )
    return {"status": "success", "result": result.to_dict()}


@router.post("/risk")
async def quantum_risk(request: RiskRequest):
    """Quantum amplitude estimation for VaR vs classical parametric VaR."""
    _check_enabled()

    engine = QuantumEngine(shots=settings.quantum_shots, backend=settings.quantum_backend)
    result = engine.analyze_risk(
        portfolio_weights=request.portfolio_weights,
        volatilities=request.volatilities,
        confidence_level=request.confidence_level,
        horizon_days=request.horizon_days,
    )
    return {"status": "success", "result": result.to_dict()}


@router.post("/price")
async def quantum_price(request: PriceRequest):
    """Quantum option pricing vs Black-Scholes."""
    _check_enabled()

    engine = QuantumEngine(shots=settings.quantum_shots, backend=settings.quantum_backend)
    result = engine.price_option(
        spot=request.spot,
        strike=request.strike,
        volatility=request.volatility,
        risk_free_rate=request.risk_free_rate,
        time_to_expiry=request.time_to_expiry,
    )
    return {"status": "success", "result": result.to_dict()}
