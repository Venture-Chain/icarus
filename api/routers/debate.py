"""
Debate system endpoints.
Submit and retrieve structured bull/bear analysis results.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from engines.debate_engine import DebateResult

router = APIRouter()


class DebateResultRequest(BaseModel):
    ticker: str
    bull_thesis: str
    bull_catalysts: list[str]
    bull_conviction: int = Field(ge=0, le=100)
    bear_thesis: str
    bear_risks: list[str]
    bear_conviction: int = Field(ge=0, le=100)
    judge_direction: str = Field(pattern="^(long|short|skip)$")
    judge_conviction: int = Field(ge=0, le=100)
    price_targets: dict
    entry_price: float
    stop_price: float


@router.post("/result", status_code=201)
async def store_debate(body: DebateResultRequest, request: Request):
    engine = request.app.state.debate_engine
    result = DebateResult(
        ticker=body.ticker.upper(),
        bull_thesis=body.bull_thesis,
        bull_catalysts=body.bull_catalysts,
        bull_conviction=body.bull_conviction,
        bear_thesis=body.bear_thesis,
        bear_risks=body.bear_risks,
        bear_conviction=body.bear_conviction,
        judge_direction=body.judge_direction,
        judge_conviction=body.judge_conviction,
        price_targets=body.price_targets,
        entry_price=body.entry_price,
        stop_price=body.stop_price,
    )
    await engine.store_debate(result)
    return {"status": "stored", "ticker": result.ticker, "expires_at": result.expires_at.isoformat()}


@router.get("/active")
async def list_active_debates(request: Request):
    engine = request.app.state.debate_engine
    debates = await engine.get_all_debates()
    return [d.to_dict() for d in debates]


@router.get("/{ticker}")
async def get_debate(ticker: str, request: Request):
    engine = request.app.state.debate_engine
    debate = await engine.get_debate(ticker.upper())
    if not debate:
        raise HTTPException(status_code=404, detail=f"No active debate for {ticker.upper()}")
    return debate.to_dict()


@router.delete("/{ticker}", status_code=204)
async def invalidate_debate(ticker: str, request: Request):
    engine = request.app.state.debate_engine
    deleted = await engine.invalidate(ticker.upper())
    if not deleted:
        raise HTTPException(status_code=404, detail=f"No debate found for {ticker.upper()}")
