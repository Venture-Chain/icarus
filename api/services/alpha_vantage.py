"""Alpha Vantage data service. News sentiment and fundamentals."""
import httpx

from config import settings


class AlphaVantageService:
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self):
        self.api_key = settings.alpha_vantage_api_key

    async def get_news_sentiment(self, ticker: str) -> dict:
        async with httpx.AsyncClient() as client:
            params = {
                "function": "NEWS_SENTIMENT",
                "tickers": ticker,
                "apikey": self.api_key,
            }
            resp = await client.get(self.BASE_URL, params=params)
            return resp.json() if resp.status_code == 200 else {}

    async def get_overview(self, ticker: str) -> dict:
        async with httpx.AsyncClient() as client:
            params = {
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": self.api_key,
            }
            resp = await client.get(self.BASE_URL, params=params)
            return resp.json() if resp.status_code == 200 else {}
