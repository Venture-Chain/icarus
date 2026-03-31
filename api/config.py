from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://icarus:icarus@timescaledb:5432/icarus"
    redis_url: str = "redis://redis:6379"
    ib_host: str = "ib-gateway"
    ib_port: int = 4003
    cors_origin: str = "http://localhost:5101"
    live_trading_enabled: bool = False
    trading_mode: str = "paper"

    # Data source API keys (loaded from env)
    finnhub_api_key: str = ""
    alpha_vantage_api_key: str = ""
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "icarus/1.0"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""

    # Multi-broker orchestration
    broker_accounts: str = "[]"  # JSON array of account configs
    alpaca_paper_api_key: str = ""
    alpaca_paper_api_secret: str = ""
    alpaca_live_api_key: str = ""
    alpaca_live_api_secret: str = ""

    # Strategy loading
    strategy_dirs: list[str] = ["strategies"]
    research_path: str = "research"

    # Quantum finance (requires hlquantum pip package)
    quantum_enabled: bool = False
    quantum_backend: str = "simulator"
    quantum_shots: int = 1024

    class Config:
        env_file = ".env"


settings = Settings()
