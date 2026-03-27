"""
Data quality checks on ingested market data.
Gap detection, outlier detection, stale data, distribution shift.
"""
import logging
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

log = logging.getLogger("icarus.data-quality")


class DataQualityAlert:
    def __init__(self, alert_type: str, ticker: str, message: str, severity: str = "warning"):
        self.alert_type = alert_type
        self.ticker = ticker
        self.message = message
        self.severity = severity  # info, warning, critical
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "type": self.alert_type,
            "ticker": self.ticker,
            "message": self.message,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat(),
        }


class DataQualityEngine:
    """Validates market data integrity."""

    # US market holidays (simplified, add more as needed)
    WEEKDAY_MARKET_DAYS = {0, 1, 2, 3, 4}  # Mon-Fri

    def check_gaps(self, ticker: str, dates: list[datetime], expected_freq: str = "daily") -> list[DataQualityAlert]:
        """Detect missing trading days in price data."""
        if len(dates) < 2:
            return []

        alerts = []
        sorted_dates = sorted(dates)

        for i in range(1, len(sorted_dates)):
            prev = sorted_dates[i - 1]
            curr = sorted_dates[i]
            gap_days = (curr - prev).days

            if expected_freq == "daily" and gap_days > 4:
                # More than a long weekend gap
                alerts.append(DataQualityAlert(
                    alert_type="gap",
                    ticker=ticker,
                    message=f"gap of {gap_days} days between {prev.date()} and {curr.date()}",
                    severity="warning",
                ))

        return alerts

    def check_outliers(
        self,
        ticker: str,
        prices: list[float],
        dates: list[datetime],
        threshold: float = 5.0,
    ) -> list[DataQualityAlert]:
        """Detect price moves exceeding threshold standard deviations."""
        if len(prices) < 10:
            return []

        alerts = []
        arr = np.array(prices)
        returns = np.diff(arr) / arr[:-1]

        mean_ret = np.mean(returns)
        std_ret = np.std(returns)

        if std_ret == 0:
            return []

        for i, ret in enumerate(returns):
            z_score = abs(ret - mean_ret) / std_ret
            if z_score > threshold:
                pct_change = ret * 100
                alerts.append(DataQualityAlert(
                    alert_type="outlier",
                    ticker=ticker,
                    message=f"{pct_change:+.1f}% move on {dates[i+1].date()} (z={z_score:.1f}). Possible split or data error.",
                    severity="critical" if z_score > 10 else "warning",
                ))

        return alerts

    def check_staleness(
        self,
        source: str,
        last_update: datetime | None,
        max_age_hours: float = 24,
    ) -> DataQualityAlert | None:
        """Check if a data source is stale."""
        if last_update is None:
            return DataQualityAlert(
                alert_type="stale",
                ticker="",
                message=f"data source '{source}' has never reported data",
                severity="critical",
            )

        age = datetime.utcnow() - last_update
        if age > timedelta(hours=max_age_hours):
            return DataQualityAlert(
                alert_type="stale",
                ticker="",
                message=f"data source '{source}' last updated {age.total_seconds() / 3600:.1f}h ago",
                severity="warning" if age < timedelta(hours=max_age_hours * 2) else "critical",
            )

        return None

    def check_distribution_shift(
        self,
        ticker: str,
        recent_returns: list[float],
        historical_returns: list[float],
        window: int = 20,
    ) -> DataQualityAlert | None:
        """Detect regime changes via distribution shift (rolling vol comparison)."""
        if len(recent_returns) < window or len(historical_returns) < window:
            return None

        recent_vol = np.std(recent_returns[-window:])
        hist_vol = np.std(historical_returns)

        if hist_vol == 0:
            return None

        vol_ratio = recent_vol / hist_vol

        if vol_ratio > 2.0:
            return DataQualityAlert(
                alert_type="regime_shift",
                ticker=ticker,
                message=f"volatility {vol_ratio:.1f}x historical average. Possible regime change.",
                severity="warning" if vol_ratio < 3.0 else "critical",
            )
        elif vol_ratio < 0.3:
            return DataQualityAlert(
                alert_type="regime_shift",
                ticker=ticker,
                message=f"volatility {vol_ratio:.1f}x historical average. Unusually quiet.",
                severity="info",
            )

        return None

    def run_all_checks(
        self,
        ticker: str,
        prices: list[float],
        dates: list[datetime],
    ) -> list[DataQualityAlert]:
        """Run all quality checks on a ticker's data."""
        alerts = []
        alerts.extend(self.check_gaps(ticker, dates))
        alerts.extend(self.check_outliers(ticker, prices, dates))

        if len(prices) > 50:
            returns = list(np.diff(prices) / np.array(prices[:-1]))
            shift = self.check_distribution_shift(ticker, returns[-20:], returns)
            if shift:
                alerts.append(shift)

        return alerts
