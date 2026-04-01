import asyncio
import json
import logging
from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from engines.strategy_engine import StrategyEngine
from routers import accounts, data, debate, notifications, portfolio, research, strategy, quantum
from services.account_registry import AccountRegistry
from services.broker_base import AccountMode

log = logging.getLogger("icarus.main")

# asyncpg needs a plain postgres:// URL (not postgresql+asyncpg://)
_PG_URL = settings.database_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql://", "postgresql://")


def _build_registry() -> AccountRegistry:
    """Parse BROKER_ACCOUNTS config and instantiate broker instances."""
    registry = AccountRegistry()

    try:
        account_configs = json.loads(settings.broker_accounts)
    except (json.JSONDecodeError, TypeError):
        account_configs = []

    if not account_configs:
        # Backward compat: auto-create default IB account from legacy config
        from services.ib_client import IBClient
        broker = IBClient(
            account_id="ib-default",
            mode=AccountMode.PAPER if settings.trading_mode == "paper" else AccountMode.LIVE,
            host=settings.ib_host,
            port=settings.ib_port,
        )
        registry.register(broker)
        return registry

    for cfg in account_configs:
        broker_type = cfg.get("broker")
        account_id = cfg.get("id")
        mode = AccountMode.LIVE if cfg.get("mode") == "live" else AccountMode.PAPER

        if broker_type == "ib":
            from services.ib_client import IBClient
            broker = IBClient(
                account_id=account_id,
                mode=mode,
                host=cfg.get("host", settings.ib_host),
                port=cfg.get("port", settings.ib_port),
                client_id=cfg.get("client_id", 1),
            )
            registry.register(broker)

        elif broker_type == "alpaca":
            from services.alpaca_broker import AlpacaBroker
            key_field = cfg.get("key_field", "")
            secret_field = cfg.get("secret_field", "")
            api_key = getattr(settings, key_field, "") if key_field else ""
            api_secret = getattr(settings, secret_field, "") if secret_field else ""
            broker = AlpacaBroker(
                account_id=account_id,
                mode=mode,
                api_key=api_key,
                api_secret=api_secret,
            )
            registry.register(broker)
        else:
            log.warning("Unknown broker type: %s (account: %s)", broker_type, account_id)

    return registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: DB pool
    app.state.db_pool = await asyncpg.create_pool(_PG_URL, min_size=2, max_size=10)
    log.info("DB pool created")

    # Startup: Redis
    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    log.info("Redis connected")

    # Startup: notifier
    from services.notifier import Notifier
    app.state.notifier = Notifier(app.state.db_pool, app.state.redis)

    # Startup: strategy engine
    engine = StrategyEngine()
    engine.load_strategies()
    app.state.strategy_engine = engine

    # Startup: debate engine
    from engines.debate_engine import DebateEngine
    app.state.debate_engine = DebateEngine(app.state.redis, app.state.db_pool)

    # Startup: build registry and connect all brokers
    registry = _build_registry()
    results = await registry.connect_all()
    for account_id, ok in results.items():
        status = "connected" if ok else "FAILED"
        log.info("Broker %s: %s", account_id, status)
    app.state.account_registry = registry

    yield

    # Shutdown
    await registry.disconnect_all()
    await app.state.redis.close()
    await app.state.db_pool.close()


ws_clients: list[WebSocket] = []

app = FastAPI(
    title="Icarus",
    description="Quantitative trading platform with multi-broker orchestration, pluggable strategies, and real-time risk controls.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router, prefix="/data", tags=["data"])
app.include_router(research.router, prefix="/research", tags=["research"])
app.include_router(strategy.router, prefix="/strategies", tags=["strategies"])
app.include_router(portfolio.router, prefix="/portfolio", tags=["portfolio"])
app.include_router(quantum.router, prefix="/quantum", tags=["quantum"])
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
app.include_router(debate.router, prefix="/debate", tags=["debate"])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket for Control Room real-time updates."""
    await websocket.accept()
    ws_clients.append(websocket)

    pubsub = websocket.app.state.redis.pubsub()
    await pubsub.subscribe("icarus:notifications")

    async def _forward_notifications():
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    await websocket.send_text(message["data"])
                except Exception:
                    break

    forward_task = asyncio.create_task(_forward_notifications())

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        await pubsub.unsubscribe("icarus:notifications")
        await pubsub.close()
        if websocket in ws_clients:
            ws_clients.remove(websocket)


@app.get("/health")
async def health():
    import asyncpg
    import redis.asyncio as aioredis

    result = {
        "status": "ok",
        "service": "icarus-api",
        "timescaledb": "offline",
        "redis": "offline",
        "data_feeds": "offline",
    }

    conn = None

    # Check TimescaleDB
    try:
        conn = await asyncpg.connect(
            "postgresql://icarus:icarus@timescaledb:5432/icarus",
            timeout=2,
        )
        await conn.execute("SELECT 1")
        result["timescaledb"] = "online"
    except Exception:
        pass

    # Check data feeds: use 24h window so outside market hours doesn't show offline
    if conn:
        try:
            row = await conn.fetchval(
                "SELECT COUNT(*) FROM market_data WHERE time > NOW() - INTERVAL '24 hours'"
            )
            if row and row > 0:
                result["data_feeds"] = "online"
            else:
                # No data at all yet (fresh install)
                result["data_feeds"] = "no data"
        except Exception:
            pass
        await conn.close()

    # Check Redis
    try:
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.close()
        result["redis"] = "online"
    except Exception:
        pass

    if result["timescaledb"] == "offline" or result["redis"] == "offline":
        result["status"] = "degraded"

    return result
