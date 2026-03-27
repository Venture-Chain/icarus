"""StockTwits data service. Retail trader sentiment per ticker."""
import httpx


class StockTwitsService:
    BASE_URL = "https://api.stocktwits.com/api/2"

    async def get_sentiment(self, ticker: str) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.BASE_URL}/streams/symbol/{ticker}.json")
            if resp.status_code != 200:
                return {}
            data = resp.json()
            messages = data.get("messages", [])
            bullish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bullish")
            bearish = sum(1 for m in messages if m.get("entities", {}).get("sentiment", {}).get("basic") == "Bearish")
            total = bullish + bearish
            return {
                "ticker": ticker,
                "bullish": bullish,
                "bearish": bearish,
                "total_scored": total,
                "bull_ratio": bullish / total if total > 0 else 0.5,
                "messages_count": len(messages),
            }
