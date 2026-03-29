import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import accounts, approvals, data, ml, portfolio, research, strategy, quantum
from services.account_registry import AccountRegistry
from services.broker_base import AccountMode

log = logging.getLogger("icarus.main")


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
    # Startup: build registry and connect all brokers
    registry = _build_registry()
    results = await registry.connect_all()
    for account_id, ok in results.items():
        status = "connected" if ok else "FAILED"
        log.info("Broker %s: %s", account_id, status)
    app.state.account_registry = registry
    yield
    # Shutdown: disconnect all brokers
    await registry.disconnect_all()


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
app.include_router(ml.router, prefix="/ml", tags=["ml"])
app.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
app.include_router(quantum.router, prefix="/quantum", tags=["quantum"])
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket for Control Room real-time updates."""
    await websocket.accept()
    ws_clients.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in ws_clients:
            ws_clients.remove(websocket)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "icarus-api"}
