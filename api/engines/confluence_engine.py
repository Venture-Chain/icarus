"""
Smart money confluence scoring engine.
Cross-references dark pool, congressional trades, insider purchases,
and short interest to produce a conviction score (0-100).
"""
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta

log = logging.getLogger("icarus.confluence")


@dataclass
class ConfluenceSignal:
    source: str
    direction: str  # "bullish" or "bearish"
    strength: float  # 0-1
    detail: str


@dataclass
class ConfluenceScore:
    ticker: str
    conviction: int  # 0-100
    direction: str  # "bullish", "bearish", or "neutral"
    signals: list[ConfluenceSignal] = field(default_factory=list)
    explanation: str = ""


class ConfluenceEngine:
    """Score smart money confluence for a ticker."""

    # Base conviction points per source
    DARK_POOL_POINTS = 30
    CONGRESS_POINTS = 25
    INSIDER_POINTS = 25
    SHORT_INTEREST_POINTS = 20

    async def score(self, ticker: str, pool) -> ConfluenceScore:
        """Compute confluence score from all smart money sources."""
        signals: list[ConfluenceSignal] = []
        today = date.today()

        # Dark pool Z-score
        dp = await pool.fetchrow(
            """
            SELECT MAX(z_score) as max_z, report_date
            FROM dark_pool_volume
            WHERE ticker = $1 AND report_date >= $2
            GROUP BY report_date
            ORDER BY report_date DESC
            LIMIT 1
            """,
            ticker, today - timedelta(days=14),
        )
        if dp and dp["max_z"] and dp["max_z"] >= 2.0:
            z = dp["max_z"]
            strength = min((z - 2.0) / 2.0, 1.0)  # 2.0 -> 0, 4.0 -> 1.0
            signals.append(ConfluenceSignal(
                source="dark_pool",
                direction="bullish",  # dark pool spikes typically indicate accumulation
                strength=strength,
                detail=f"Z-score {z:.1f} (report {dp['report_date']})",
            ))

        # Congressional trades (last 45 days)
        congress = await pool.fetch(
            """
            SELECT direction, COUNT(*) as cnt, SUM(amount_max) as total_max
            FROM congressional_trades
            WHERE ticker = $1 AND trade_date >= $2
            GROUP BY direction
            """,
            ticker, today - timedelta(days=45),
        )
        buy_count = 0
        sell_count = 0
        for row in congress:
            if row["direction"] == "buy":
                buy_count = row["cnt"]
            elif row["direction"] == "sell":
                sell_count = row["cnt"]

        if buy_count > 0 and buy_count > sell_count:
            signals.append(ConfluenceSignal(
                source="congressional",
                direction="bullish",
                strength=min(buy_count / 3.0, 1.0),
                detail=f"{buy_count} buy(s) vs {sell_count} sell(s) in last 45 days",
            ))
        elif sell_count > 0 and sell_count > buy_count:
            signals.append(ConfluenceSignal(
                source="congressional",
                direction="bearish",
                strength=min(sell_count / 3.0, 1.0),
                detail=f"{sell_count} sell(s) vs {buy_count} buy(s) in last 45 days",
            ))

        # Insider purchases (Form 4, last 30 days)
        insiders = await pool.fetchrow(
            """
            SELECT COUNT(*) as cnt
            FROM filings
            WHERE ticker = $1 AND filing_type = '4' AND filing_date >= $2
            """,
            ticker, (today - timedelta(days=30)).isoformat(),
        )
        if insiders and insiders["cnt"] > 0:
            signals.append(ConfluenceSignal(
                source="insider",
                direction="bullish",
                strength=min(insiders["cnt"] / 3.0, 1.0),
                detail=f"{insiders['cnt']} Form 4 filing(s) in last 30 days",
            ))

        # Short interest trend
        short_rows = await pool.fetch(
            """
            SELECT report_date, short_pct_float, change_pct
            FROM short_interest
            WHERE ticker = $1
            ORDER BY report_date DESC
            LIMIT 2
            """,
            ticker,
        )
        if len(short_rows) >= 1:
            latest = short_rows[0]
            change = latest["change_pct"] or 0
            if change < -5:  # short interest declining > 5%
                signals.append(ConfluenceSignal(
                    source="short_interest",
                    direction="bullish",
                    strength=min(abs(change) / 20.0, 1.0),
                    detail=f"Short interest down {change:.1f}%, float {latest['short_pct_float']:.1f}%",
                ))
            elif change > 10:  # short interest rising sharply
                signals.append(ConfluenceSignal(
                    source="short_interest",
                    direction="bearish",
                    strength=min(change / 30.0, 1.0),
                    detail=f"Short interest up {change:.1f}%, float {latest['short_pct_float']:.1f}%",
                ))

        # Compute conviction
        conviction = self._compute_conviction(signals)
        direction = self._net_direction(signals)
        explanation = self._explain(signals, conviction, direction)

        return ConfluenceScore(
            ticker=ticker,
            conviction=conviction,
            direction=direction,
            signals=signals,
            explanation=explanation,
        )

    def _compute_conviction(self, signals: list[ConfluenceSignal]) -> int:
        """Sum base points per source, weighted by strength and alignment."""
        if not signals:
            return 0

        points_map = {
            "dark_pool": self.DARK_POOL_POINTS,
            "congressional": self.CONGRESS_POINTS,
            "insider": self.INSIDER_POINTS,
            "short_interest": self.SHORT_INTEREST_POINTS,
        }

        # Check if all signals agree on direction
        bullish = [s for s in signals if s.direction == "bullish"]
        bearish = [s for s in signals if s.direction == "bearish"]
        aligned = len(bullish) == 0 or len(bearish) == 0

        total = 0
        for signal in signals:
            base = points_map.get(signal.source, 10)
            total += base * signal.strength

        # Bonus for alignment
        if aligned and len(signals) >= 2:
            total *= 1.15
        elif not aligned:
            total *= 0.7  # conflicting signals reduce conviction

        return min(int(total), 100)

    def _net_direction(self, signals: list[ConfluenceSignal]) -> str:
        if not signals:
            return "neutral"

        bullish_weight = sum(s.strength for s in signals if s.direction == "bullish")
        bearish_weight = sum(s.strength for s in signals if s.direction == "bearish")

        if bullish_weight > bearish_weight * 1.5:
            return "bullish"
        elif bearish_weight > bullish_weight * 1.5:
            return "bearish"
        return "neutral"

    def _explain(self, signals: list[ConfluenceSignal], conviction: int, direction: str) -> str:
        if not signals:
            return "No smart money signals detected."

        parts = [f"{s.source}: {s.detail}" for s in signals]
        label = "High conviction" if conviction >= 70 else "Moderate" if conviction >= 40 else "Low"
        return f"{label} {direction} ({conviction}/100). {'; '.join(parts)}"
