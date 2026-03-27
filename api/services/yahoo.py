"""Yahoo Finance data service via yfinance. Prices and basic fundamentals."""
import yfinance as yf


class YahooService:
    def get_prices(self, ticker: str, period: str = "1y", interval: str = "1d"):
        stock = yf.Ticker(ticker)
        return stock.history(period=period, interval=interval)

    def get_info(self, ticker: str) -> dict:
        stock = yf.Ticker(ticker)
        return stock.info

    def get_news(self, ticker: str) -> list:
        stock = yf.Ticker(ticker)
        return stock.news
