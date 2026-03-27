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

    # Strategy loading
    strategy_dirs: list[str] = ["strategies"]
    research_path: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
