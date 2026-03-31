from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class StrategyDeploy(BaseModel):
    mode: str = "paper"  # paper or live
    account_id: str = ""
    universe: list[str] = []
    capital: float = 0
    no_overnight: bool = True
    daily_loss_limit_pct: float = 0.02
    max_concurrent_positions: int = 3


@router.get("/")
async def list_strategies(request: Request):
    """List all loaded strategies from the plugin system."""
    engine = request.app.state.strategy_engine
    return {"strategies": engine.list_strategies()}


@router.get("/{strategy_name}")
async def get_strategy(strategy_name: str, request: Request):
    """Get strategy details."""
    engine = request.app.state.strategy_engine
    strategy = engine.get_strategy(strategy_name)
    if not strategy:
        return {"error": f"strategy '{strategy_name}' not found"}
    return {
        "name": strategy.name,
        "description": strategy.description,
        "parameters": strategy.parameters(),
        "required_data": [
            {"type": r.data_type, "lookback": r.lookback_days}
            for r in strategy.required_data()
        ],
    }


@router.put("/{strategy_name}/deploy")
async def deploy_strategy(strategy_name: str, deploy: StrategyDeploy, request: Request):
    """Deploy a strategy to paper or live."""
    engine = request.app.state.strategy_engine
    strategy = engine.get_strategy(strategy_name)
    if not strategy:
        return {"error": f"strategy '{strategy_name}' not found"}

    pool = request.app.state.db_pool

    # Get or create strategy record
    row = await pool.fetchrow(
        "SELECT id FROM strategies WHERE name = $1", strategy_name,
    )
    if not row:
        row = await pool.fetchrow(
            """
            INSERT INTO strategies (name, description, module_path, mode, status)
            VALUES ($1, $2, $3, $4, 'active')
            RETURNING id
            """,
            strategy_name, strategy.description, strategy_name, deploy.mode,
        )

    strategy_id = row["id"]

    # Create deployment
    dep = await pool.fetchrow(
        """
        INSERT INTO strategy_deployments (strategy_id, account_id, status)
        VALUES ($1, $2, 'active')
        ON CONFLICT (strategy_id, account_id) DO UPDATE SET status = 'active', stopped_at = NULL
        RETURNING id
        """,
        strategy_id, deploy.account_id or "paper",
    )

    # Create deployment config
    await pool.execute(
        """
        INSERT INTO deployment_config (
            deployment_id, universe, capital_allocated, no_overnight,
            daily_loss_limit_pct, max_concurrent_positions
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (deployment_id) DO UPDATE SET
            universe = EXCLUDED.universe,
            capital_allocated = EXCLUDED.capital_allocated,
            no_overnight = EXCLUDED.no_overnight,
            daily_loss_limit_pct = EXCLUDED.daily_loss_limit_pct,
            max_concurrent_positions = EXCLUDED.max_concurrent_positions
        """,
        dep["id"], deploy.universe, deploy.capital,
        deploy.no_overnight, deploy.daily_loss_limit_pct,
        deploy.max_concurrent_positions,
    )

    return {
        "strategy": strategy_name,
        "deployment_id": dep["id"],
        "mode": deploy.mode,
        "account_id": deploy.account_id or "paper",
        "status": "active",
    }


@router.get("/{strategy_name}/deployments")
async def get_deployments(strategy_name: str, request: Request):
    """List all deployments for a strategy."""
    pool = request.app.state.db_pool

    rows = await pool.fetch(
        """
        SELECT sd.id, sd.account_id, sd.status, sd.deployed_at, sd.stopped_at,
               dc.universe, dc.capital_allocated, dc.no_overnight,
               dc.daily_loss_limit_pct, dc.max_concurrent_positions
        FROM strategy_deployments sd
        JOIN strategies s ON s.id = sd.strategy_id
        LEFT JOIN deployment_config dc ON dc.deployment_id = sd.id
        WHERE s.name = $1
        ORDER BY sd.deployed_at DESC
        """,
        strategy_name,
    )
    return {
        "strategy": strategy_name,
        "deployments": [
            {
                "id": r["id"],
                "account_id": r["account_id"],
                "status": r["status"],
                "deployed_at": str(r["deployed_at"]),
                "stopped_at": str(r["stopped_at"]) if r["stopped_at"] else None,
                "universe": r["universe"] if r["universe"] else [],
                "capital": r["capital_allocated"],
                "no_overnight": r["no_overnight"],
            }
            for r in rows
        ],
    }


@router.delete("/{strategy_name}/deployments/{deployment_id}")
async def stop_deployment(strategy_name: str, deployment_id: int, request: Request):
    """Stop a strategy deployment."""
    pool = request.app.state.db_pool

    await pool.execute(
        """
        UPDATE strategy_deployments
        SET status = 'stopped', stopped_at = NOW()
        WHERE id = $1
        """,
        deployment_id,
    )
    return {"deployment_id": deployment_id, "status": "stopped"}
