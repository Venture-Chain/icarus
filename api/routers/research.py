"""Research endpoints: backtesting, projections, research logging."""
import json
from concurrent.futures import ProcessPoolExecutor
from datetime import date

import numpy as np
from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class BacktestRequest(BaseModel):
    strategy_name: str
    universe: list[str] = []
    start_date: str = ""
    end_date: str = ""
    initial_capital: float = 100000
    parameters: dict = {}


class MonteCarloRequest(BaseModel):
    ticker: str = ""
    portfolio: list[str] = []
    years: int = 10
    iterations: int = 5000
    initial_value: float = 100000
    annual_contribution: float = 0


class ScenarioRequest(BaseModel):
    portfolio: list[str] = []
    portfolio_value: float = 100000
    scenarios: list[str] = ["base", "bull", "bear", "recession", "rate_hike"]


class ResearchLogEntry(BaseModel):
    hypothesis: str
    methodology: str = ""
    findings: str = ""
    data_sources: list[str] = []


# Pre-defined scenario parameters (annual return adjustments)
SCENARIOS = {
    "base": {"label": "Base Case", "return_mult": 1.0, "vol_mult": 1.0, "prob": 0.40},
    "bull": {"label": "Bull Market", "return_mult": 1.5, "vol_mult": 0.8, "prob": 0.20},
    "bear": {"label": "Bear Market", "return_mult": -0.5, "vol_mult": 1.3, "prob": 0.15},
    "recession": {"label": "Recession", "return_mult": -1.0, "vol_mult": 1.8, "prob": 0.10},
    "rate_hike": {"label": "Rate Hike", "return_mult": 0.3, "vol_mult": 1.4, "prob": 0.15},
}


@router.post("/backtest/run")
async def run_backtest(body: BacktestRequest, request: Request):
    """Run a backtest using historical data from TimescaleDB."""
    pool = request.app.state.db_pool

    # Fetch price data
    import pandas as pd
    from engines.backtest_engine import BacktestConfig, BacktestEngine

    config = BacktestConfig(
        strategy_name=body.strategy_name,
        universe=body.universe,
        start_date=body.start_date,
        end_date=body.end_date,
        initial_capital=body.initial_capital,
    )

    price_data = {}
    for ticker in body.universe:
        rows = await pool.fetch("""
            SELECT time::date as date, open, high, low, close, volume
            FROM market_data
            WHERE ticker = $1 AND time >= $2::date AND time <= $3::date
            ORDER BY time
        """, ticker, body.start_date, body.end_date)

        if rows:
            price_data[ticker] = pd.DataFrame([dict(r) for r in rows])

    if not price_data:
        return {"error": "no price data found for the given universe and date range"}

    engine = BacktestEngine()
    results = await engine.run(config, price_data)

    # Store run in DB
    run_id = await pool.fetchval("""
        INSERT INTO backtest_runs (strategy_name, config, results, status)
        VALUES ($1, $2, $3, 'completed')
        RETURNING id
    """, body.strategy_name, json.dumps({
        "universe": body.universe,
        "start_date": body.start_date,
        "end_date": body.end_date,
        "initial_capital": body.initial_capital,
        "parameters": body.parameters,
    }), json.dumps(results.to_dict()))

    return {
        "id": run_id,
        "status": "completed",
        "strategy": body.strategy_name,
        "results": results.to_dict(),
        "equity_curve": results.equity_curve[-20:] if results.equity_curve else [],
        "dates": results.dates[-20:] if results.dates else [],
    }


@router.get("/backtest/{backtest_id}")
async def get_backtest_results(backtest_id: int, request: Request):
    """Get results of a backtest run."""
    pool = request.app.state.db_pool
    row = await pool.fetchrow(
        "SELECT id, strategy_name, config, results, status, created_at FROM backtest_runs WHERE id = $1",
        backtest_id,
    )
    if not row:
        return {"error": "backtest not found"}
    return {
        "id": row["id"],
        "strategy": row["strategy_name"],
        "config": json.loads(row["config"]) if row["config"] else {},
        "results": json.loads(row["results"]) if row["results"] else {},
        "status": row["status"],
        "created_at": str(row["created_at"]),
    }


@router.post("/projections/monte-carlo")
async def monte_carlo_projection(body: MonteCarloRequest, request: Request):
    """Run Monte Carlo simulation for portfolio projection over N years."""
    pool = request.app.state.db_pool

    tickers = body.portfolio if body.portfolio else ([body.ticker] if body.ticker else [])
    if not tickers:
        return {"error": "provide ticker or portfolio"}

    # Fetch historical returns to estimate parameters
    rows = await pool.fetch("""
        SELECT ticker,
               AVG(daily_return) as avg_return,
               STDDEV(daily_return) as std_return,
               COUNT(*) as days
        FROM (
            SELECT ticker, close,
                   (close - LAG(close) OVER (PARTITION BY ticker ORDER BY time)) /
                   NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY time), 0) as daily_return
            FROM market_data
            WHERE ticker = ANY($1)
              AND time > NOW() - INTERVAL '1 year'
        ) sub
        WHERE daily_return IS NOT NULL
        GROUP BY ticker
    """, tickers)

    if not rows:
        return {"error": "no historical data for the given tickers"}

    # Aggregate portfolio-level stats (equal weight)
    avg_daily = float(np.mean([r["avg_return"] for r in rows if r["avg_return"]]))
    std_daily = float(np.mean([r["std_return"] for r in rows if r["std_return"]]))

    annual_return = avg_daily * 252
    annual_vol = std_daily * np.sqrt(252)

    # Run simulation
    iterations = min(body.iterations, 10000)
    years = min(body.years, 30)
    months = years * 12
    monthly_return = annual_return / 12
    monthly_vol = annual_vol / np.sqrt(12)
    monthly_contribution = body.annual_contribution / 12

    rng = np.random.default_rng(42)
    paths = np.zeros((iterations, months + 1))
    paths[:, 0] = body.initial_value

    for m in range(1, months + 1):
        returns = rng.normal(monthly_return, monthly_vol, iterations)
        paths[:, m] = paths[:, m - 1] * (1 + returns) + monthly_contribution

    # Extract percentile curves (yearly)
    yearly_indices = [0] + [i * 12 for i in range(1, years + 1)]
    yearly_paths = paths[:, yearly_indices]

    percentiles = {}
    for p in [5, 10, 25, 50, 75, 90, 95]:
        percentiles[f"p{p}"] = [round(float(v), 2) for v in np.percentile(yearly_paths, p, axis=0)]

    final_values = paths[:, -1]

    return {
        "tickers": tickers,
        "years": years,
        "iterations": iterations,
        "initial_value": body.initial_value,
        "annual_contribution": body.annual_contribution,
        "estimated_annual_return": round(annual_return * 100, 2),
        "estimated_annual_volatility": round(annual_vol * 100, 2),
        "percentile_curves": percentiles,
        "year_labels": list(range(years + 1)),
        "final_value": {
            "mean": round(float(np.mean(final_values)), 2),
            "median": round(float(np.median(final_values)), 2),
            "p5": round(float(np.percentile(final_values, 5)), 2),
            "p95": round(float(np.percentile(final_values, 95)), 2),
            "prob_positive": round(float(np.mean(final_values > body.initial_value) * 100), 1),
        },
    }


@router.post("/projections/scenario")
async def scenario_projection(body: ScenarioRequest, request: Request):
    """Run named scenarios (recession, bull, bear, rate hike) against a portfolio."""
    pool = request.app.state.db_pool

    tickers = body.portfolio
    if not tickers:
        return {"error": "provide portfolio tickers"}

    # Get base historical stats
    rows = await pool.fetch("""
        SELECT ticker,
               AVG(daily_return) as avg_return,
               STDDEV(daily_return) as std_return
        FROM (
            SELECT ticker, close,
                   (close - LAG(close) OVER (PARTITION BY ticker ORDER BY time)) /
                   NULLIF(LAG(close) OVER (PARTITION BY ticker ORDER BY time), 0) as daily_return
            FROM market_data
            WHERE ticker = ANY($1)
              AND time > NOW() - INTERVAL '1 year'
        ) sub
        WHERE daily_return IS NOT NULL
        GROUP BY ticker
    """, tickers)

    if not rows:
        return {"error": "no historical data"}

    base_annual_return = float(np.mean([r["avg_return"] for r in rows if r["avg_return"]])) * 252
    base_annual_vol = float(np.mean([r["std_return"] for r in rows if r["std_return"]])) * np.sqrt(252)

    results = []
    for scenario_name in body.scenarios:
        s = SCENARIOS.get(scenario_name)
        if not s:
            continue

        adj_return = base_annual_return * s["return_mult"]
        adj_vol = base_annual_vol * s["vol_mult"]

        # 1-year projection
        projected_value = body.portfolio_value * (1 + adj_return)
        worst_1y = body.portfolio_value * (1 + adj_return - 1.96 * adj_vol)
        best_1y = body.portfolio_value * (1 + adj_return + 1.96 * adj_vol)

        results.append({
            "scenario": scenario_name,
            "label": s["label"],
            "probability": round(s["prob"] * 100, 1),
            "annual_return": round(adj_return * 100, 2),
            "annual_volatility": round(adj_vol * 100, 2),
            "projected_1y_value": round(projected_value, 2),
            "projected_1y_range": [round(worst_1y, 2), round(best_1y, 2)],
            "pnl": round(projected_value - body.portfolio_value, 2),
        })

    expected_value = sum(
        r["projected_1y_value"] * (SCENARIOS[r["scenario"]]["prob"])
        for r in results
    )

    return {
        "portfolio": tickers,
        "portfolio_value": body.portfolio_value,
        "base_annual_return": round(base_annual_return * 100, 2),
        "base_annual_volatility": round(base_annual_vol * 100, 2),
        "scenarios": results,
        "expected_value": round(expected_value, 2),
    }


@router.post("/log")
async def log_research(entry: ResearchLogEntry, request: Request):
    """Save a research log entry."""
    pool = request.app.state.db_pool
    row_id = await pool.fetchval("""
        INSERT INTO research_log (hypothesis, methodology, findings, data_sources)
        VALUES ($1, $2, $3, $4)
        RETURNING id
    """, entry.hypothesis, entry.methodology, entry.findings, entry.data_sources)
    return {"id": row_id, "status": "saved"}


@router.get("/log")
async def get_research_log(request: Request, limit: int = 50):
    """Get all research log entries."""
    pool = request.app.state.db_pool
    rows = await pool.fetch("""
        SELECT id, hypothesis, methodology, findings, data_sources, created_at
        FROM research_log
        ORDER BY created_at DESC
        LIMIT $1
    """, limit)
    return {
        "entries": [
            {
                "id": r["id"],
                "hypothesis": r["hypothesis"],
                "methodology": r["methodology"],
                "findings": r["findings"],
                "data_sources": r["data_sources"],
                "created_at": str(r["created_at"]),
            }
            for r in rows
        ],
    }
