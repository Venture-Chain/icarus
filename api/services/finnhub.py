"""Finnhub data service. News and sentiment."""
import httpx

from config import settings


class FinnhubService:
    BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self):
        self.api_key = settings.finnhub_api_key

    async def get_news(self, ticker: str, from_date: str = None, to_date: str = None) -> list:
        async with httpx.AsyncClient() as client:
            params = {"symbol": ticker, "token": self.api_key}
            if from_date:
                params["from"] = from_date
            if to_date:
                params["to"] = to_date
            resp = await client.get(f"{self.BASE_URL}/company-news", params=params)
            return resp.json() if resp.status_code == 200 else []

    async def get_sentiment(self, ticker: str) -> dict:
        async with httpx.AsyncClient() as client:
            params = {"symbol": ticker, "token": self.api_key}
            resp = await client.get(f"{self.BASE_URL}/news-sentiment", params=params)
            return resp.json() if resp.status_code == 200 else {}
