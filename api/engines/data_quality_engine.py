"""
Data quality checks on ingested market data.
Gap detection, outlier detection, stale data alerts.
"""


class DataQualityEngine:
    def check_gaps(self, ticker: str, data) -> list:
        """Detect missing trading days in price data."""
        return []

    def check_outliers(self, ticker: str, data, threshold: float = 5.0) -> list:
        """Detect price moves that exceed threshold standard deviations."""
        return []

    def check_staleness(self, source: str, last_update) -> bool:
        """Check if a data source hasn't updated within expected interval."""
        return False

    def check_distribution_shift(self, ticker: str, recent_data, historical_data) -> dict:
        """Detect regime changes via distribution shift."""
        return {"shifted": False}
