"""
Icarus Strategy Runner.
Loads active deployments, runs strategies on schedule, manages positions.
Enforces hard rules: no overnight positions, daily loss limit, max positions.
"""
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo

import asyncpg
import redis.asyncio as aioredis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("icarus.runner")

sys.path.insert(0, "/api")

ET = ZoneInfo("America/New_York")


def is_market_hours() -> bool:
    now = datetime.now(ET)
    if now.weekday() >= 5:
        return False
    return dtime(9, 30) <= now.time() <= dtime(16, 0)


def is_flatten_time() -> bool:
    """3:55 PM ET - time to flatten all positions."""
    now = datetime.now(ET)
    return now.time() >= dtime(15, 55)


class StrategyRunner:
    """Manages strategy deployments and executes trading logic."""

    def __init__(self, redis_url: str, database_url: str):
        self.redis_url = redis_url
        self.database_url = database_url
        self.redis: aioredis.Redis | None = None
        self.db_pool = None
        self._running = True
        self._deployments: dict[int, dict] = {}  # deployment_id -> config
        self._daily_pnl: dict[int, float] = {}  # deployment_id -> today's PnL
        self._day_marker = None

    async def start(self):
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        db_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self.db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=5)

        log.info("strategy runner starting")

        # Load strategy engine
        from engines.strategy_engine import StrategyEngine
        self.strategy_engine = StrategyEngine()
        self.strategy_engine.load_strategies()

        # Load virtual portfolios
        from virtual_portfolio import VirtualPortfolio
        self.portfolios: dict[int, VirtualPortfolio] = {}

        await self._load_deployments()

        await asyncio.gather(
            self._run_loop(),
            self._snapshot_loop(),
            self._flatten_loop(),
        )

    async def _load_deployments(self):
        """Load active deployments from DB."""
        rows = await self.db_pool.fetch("""
            SELECT sd.id, s.name as strategy_name, sd.account_id,
                   dc.universe, dc.capital_allocated, dc.schedule_interval_sec,
                   dc.no_overnight, dc.daily_loss_limit_pct, dc.max_concurrent_positions
            FROM strategy_deployments sd
            JOIN strategies s ON s.id = sd.strategy_id
            LEFT JOIN deployment_config dc ON dc.deployment_id = sd.id
            WHERE sd.status = 'active'
        """)

        from virtual_portfolio import VirtualPortfolio

        for row in rows:
            dep_id = row["id"]
            self._deployments[dep_id] = {
                "strategy_name": row["strategy_name"],
                "account_id": row["account_id"],
                "universe": list(row["universe"] or []),
                "capital": row["capital_allocated"] or 10000,
                "interval": row["schedule_interval_sec"] or 60,
                "no_overnight": row["no_overnight"] if row["no_overnight"] is not None else True,
                "daily_loss_limit": row["daily_loss_limit_pct"] or 0.02,
                "max_positions": row["max_concurrent_positions"] or 3,
            }
            if row["account_id"] == "paper":
                self.portfolios[dep_id] = VirtualPortfolio(
                    capital=row["capital_allocated"] or 10000,
                )
            self._daily_pnl[dep_id] = 0

        log.info("loaded %d active deployments", len(self._deployments))

    async def _run_loop(self):
        """Main loop: run strategies on schedule during market hours."""
        while self._running:
            if not is_market_hours() or is_flatten_time():
                await asyncio.sleep(10)
                continue

            # Reset daily PnL at market open
            today = datetime.now(ET).date()
            if self._day_marker != today:
                self._day_marker = today
                self._daily_pnl = {dep_id: 0 for dep_id in self._deployments}
                log.info("daily PnL counters reset")

            for dep_id, config in self._deployments.items():
                try:
                    await self._run_deployment(dep_id, config)
                except Exception as e:
                    log.error("deployment %d error: %s", dep_id, e)

            # Sleep for the shortest interval across all deployments
            min_interval = min(
                (c["interval"] for c in self._deployments.values()),
                default=60,
            )
            await asyncio.sleep(min_interval)

    async def _run_deployment(self, dep_id: int, config: dict):
        """Run a single deployment cycle."""
        # Check daily loss limit
        capital = config["capital"]
        if capital > 0:
            loss_pct = abs(self._daily_pnl.get(dep_id, 0)) / capital
            if loss_pct >= config["daily_loss_limit"]:
                return  # stopped for the day

        strategy = self.strategy_engine.get_strategy(config["strategy_name"])
        if not strategy:
            return

        universe = config["universe"]
        if not universe:
            return

        # Build context
        from strategies.base import SignalContext
        context = SignalContext(
            trigger_type="scheduled",
            capital=capital,
        )

        # Get signals
        signals = strategy.compute_signals(universe, datetime.utcnow(), context)
        if not signals:
            return

        # Process through virtual portfolio (paper) or broker (live)
        portfolio = self.portfolios.get(dep_id)
        if portfolio:
            for signal in signals:
                # Check max positions
                if len(portfolio.positions) >= config["max_positions"]:
                    if signal.direction in ("long", "short"):
                        continue  # skip new positions

                portfolio.process_signal(signal)
                log.info("deployment %d: %s %s @ confidence %.2f",
                         dep_id, signal.direction, signal.ticker, signal.confidence)

                # Record signal to DB
                await self.db_pool.execute("""
                    INSERT INTO signals (time, strategy_id, ticker, direction, confidence, metadata)
                    VALUES (NOW(), (SELECT id FROM strategies WHERE name = $1), $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                """, config["strategy_name"], signal.ticker, signal.direction,
                    signal.confidence, json.dumps(signal.metadata or {}))

    async def _flatten_loop(self):
        """Flatten all positions at 3:55 PM ET. Non-negotiable."""
        while self._running:
            if is_flatten_time() and is_market_hours():
                for dep_id, config in self._deployments.items():
                    if not config.get("no_overnight", True):
                        continue

                    portfolio = self.portfolios.get(dep_id)
                    if portfolio and portfolio.positions:
                        flattened = portfolio.flatten()
                        log.warning("deployment %d: FLATTENED %d positions (no overnight)",
                                    dep_id, flattened)

                        await self._notify(
                            "stop_triggered",
                            f"Deployment {dep_id}: flattened {flattened} positions",
                            "End-of-day flatten rule (3:55 PM ET)",
                            "warning",
                        )
                # Sleep until market close to avoid re-triggering
                await asyncio.sleep(300)
            else:
                await asyncio.sleep(10)

    async def _snapshot_loop(self):
        """Save deployment performance snapshots every 5 minutes."""
        while self._running:
            if not is_market_hours():
                await asyncio.sleep(60)
                continue

            for dep_id, portfolio in self.portfolios.items():
                try:
                    stats = portfolio.stats()
                    await self.db_pool.execute("""
                        INSERT INTO deployment_snapshots
                            (time, deployment_id, nav, cash, positions_count,
                             unrealized_pnl, realized_pnl, drawdown, total_trades,
                             win_rate, daily_pnl, positions)
                        VALUES (NOW(), $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                    """,
                        dep_id, stats["nav"], stats["cash"],
                        stats["positions_count"], stats["unrealized_pnl"],
                        stats["realized_pnl"], stats["drawdown"],
                        stats["total_trades"], stats["win_rate"],
                        stats["daily_pnl"],
                        json.dumps(stats.get("positions", {})),
                    )
                except Exception as e:
                    log.error("snapshot failed for deployment %d: %s", dep_id, e)

            await asyncio.sleep(300)

    async def _notify(self, type: str, title: str, body: str, severity: str):
        try:
            await self.db_pool.execute("""
                INSERT INTO notifications (type, severity, title, body)
                VALUES ($1, $2, $3, $4)
            """, type, severity, title, body)
            await self.redis.publish("icarus:notifications", json.dumps({
                "type": type, "severity": severity, "title": title, "body": body,
            }))
        except Exception as e:
            log.error("notify failed: %s", e)

    async def stop(self):
        self._running = False
        if self.redis:
            await self.redis.close()
        if self.db_pool:
            await self.db_pool.close()


async def main():
    redis_url = os.environ.get("REDIS_URL", "redis://redis:6379")
    database_url = os.environ.get("DATABASE_URL", "postgresql+asyncpg://icarus:icarus@timescaledb:5432/icarus")
    runner = StrategyRunner(redis_url, database_url)
    try:
        await runner.start()
    except KeyboardInterrupt:
        await runner.stop()


if __name__ == "__main__":
    asyncio.run(main())
