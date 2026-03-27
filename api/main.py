from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import approvals, data, ml, portfolio, research, strategy


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to DB, Redis, IB
    yield
    # Shutdown: disconnect


app = FastAPI(
    title="Icarus",
    description="Quantitative trading platform",
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "icarus-api"}
