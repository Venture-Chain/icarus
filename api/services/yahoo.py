"""Yahoo Finance data service via yfinance. Prices, fundamentals, and corporate actions."""
import logging
from datetime import datetime
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)


class YahooService:

    def get_prices(self, ticker: str, period: str = "1y", interval: str = "1d") -> list[dict]:
        """Get price history as list of dicts. Returns empty list on failure."""
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period=period, interval=interval)
            if df.empty:
                return []
            df = df.reset_index()
            records = []
            for _, row in df.iterrows():
                date_val = row.get("Date") or row.get("Datetime")
                records.append({
                    "date": str(date_val),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            return records
        except Exception as e:
            logger.error("Yahoo get_prices failed for %s: %s", ticker, str(e))
            return []

    def get_historical(self, ticker: str, start: str, end: str) -> list[dict]:
        """Get historical data for a date range. Dates as YYYY-MM-DD strings."""
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(start=start, end=end)
            if df.empty:
                return []
            df = df.reset_index()
            records = []
            for _, row in df.iterrows():
                date_val = row.get("Date") or row.get("Datetime")
                records.append({
                    "date": str(date_val),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": int(row["Volume"]),
                })
            return records
        except Exception as e:
            logger.error("Yahoo get_historical failed for %s: %s", ticker, str(e))
            return []

    def get_info(self, ticker: str) -> dict:
        """Get ticker info: sector, market cap, PE, etc."""
        try:
            stock = yf.Ticker(ticker)
            return dict(stock.info)
        except Exception as e:
            logger.error("Yahoo get_info failed for %s: %s", ticker, str(e))
            return {}

    def get_news(self, ticker: str) -> list:
        """Get recent news for a ticker."""
        try:
            stock = yf.Ticker(ticker)
            return stock.news or []
        except Exception as e:
            logger.error("Yahoo get_news failed for %s: %s", ticker, str(e))
            return []

    def get_financials(self, ticker: str) -> dict:
        """Get income statement, balance sheet, and cash flow as dict of lists."""
        try:
            stock = yf.Ticker(ticker)
            result: dict[str, list[dict]] = {}

            for name, df in [
                ("income_statement", stock.financials),
                ("balance_sheet", stock.balance_sheet),
                ("cashflow", stock.cashflow),
            ]:
                if df is not None and not df.empty:
                    records = []
                    for col in df.columns:
                        period_data = {"period": str(col)}
                        for idx in df.index:
                            val = df.loc[idx, col]
                            period_data[str(idx)] = float(val) if val == val else None
                        records.append(period_data)
                    result[name] = records
                else:
                    result[name] = []

            return result
        except Exception as e:
            logger.error("Yahoo get_financials failed for %s: %s", ticker, str(e))
            return {}

    def get_actions(self, ticker: str) -> dict[str, list[dict]]:
        """Get stock splits and dividends. Useful for survivorship bias adjustment."""
        try:
            stock = yf.Ticker(ticker)
            result: dict[str, list[dict]] = {"dividends": [], "splits": []}

            divs = stock.dividends
            if divs is not None and not divs.empty:
                for date, amount in divs.items():
                    result["dividends"].append({
                        "date": str(date),
                        "amount": float(amount),
                    })

            splits = stock.splits
            if splits is not None and not splits.empty:
                for date, ratio in splits.items():
                    result["splits"].append({
                        "date": str(date),
                        "ratio": float(ratio),
                    })

            return result
        except Exception as e:
            logger.error("Yahoo get_actions failed for %s: %s", ticker, str(e))
            return {"dividends": [], "splits": []}
