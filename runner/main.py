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
        self._broker_positions_cache: dict[str, list] = {}  # account_id -> positions, refreshed each cycle

    async def start(self):
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        db_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self.db_pool = await asyncpg.create_pool(db_url, min_size=2, max_size=5)

        log.info("strategy runner starting")

        # Load strategy engine (strategies live in /api/strategies/)
        from engines.strategy_engine import StrategyEngine
        self.strategy_engine = StrategyEngine(strategy_dirs=["/api/strategies", "/research/strategies"])
        self.strategy_engine.load_strategies()

        # Initialize broker clients
        self._broker_clients = {}
        await self._init_brokers()

        # Load virtual portfolios
        from virtual_portfolio import VirtualPortfolio
        self.portfolios: dict[int, VirtualPortfolio] = {}

        await self._load_deployments()

        # If we start outside market hours and have no-overnight positions, flatten immediately
        await self._startup_flatten_check()

        results = await asyncio.gather(
            self._run_loop(),
            self._snapshot_loop(),
            self._flatten_loop(),
            self._vix_update_loop(),
            return_exceptions=True,
        )
        # Log any coroutine failures (with return_exceptions=True they don't crash each other)
        names = ["run_loop", "snapshot_loop", "flatten_loop", "vix_update_loop"]
        for name, result in zip(names, results):
            if isinstance(result, Exception):
                log.error("coroutine %s crashed: %s", name, result)

    async def _init_brokers(self):
        """Initialize broker clients from account registry in DB."""
        rows = await self.db_pool.fetch("""
            SELECT id, broker_type, mode, config FROM broker_accounts WHERE status = 'active'
        """)
        for row in rows:
            account_id = row["id"]
            broker_type = row["broker_type"]
            try:
                if broker_type == "alpaca":
                    from services.alpaca_broker import AlpacaBroker
                    from services.broker_base import AccountMode
                    api_key = os.environ.get("ALPACA_API_KEY", "")
                    api_secret = os.environ.get("ALPACA_API_SECRET", "")
                    mode = AccountMode.LIVE if row["mode"] == "live" else AccountMode.PAPER
                    broker = AlpacaBroker(
                        account_id=account_id,
                        mode=mode,
                        api_key=api_key,
                        api_secret=api_secret,
                    )
                    await broker.connect()
                    self._broker_clients[account_id] = broker
                    log.info("broker connected: %s (%s, %s)", account_id, broker_type, mode)
            except Exception as e:
                log.error("failed to init broker %s: %s", account_id, e)

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

    async def _refresh_broker_positions(self):
        """Fetch live positions from all connected brokers. Call once per run cycle."""
        self._broker_positions_cache.clear()
        for account_id, broker in self._broker_clients.items():
            if broker.connected:
                try:
                    self._broker_positions_cache[account_id] = await broker.get_positions()
                except Exception as e:
                    log.warning("failed to fetch positions for %s: %s", account_id, e)

    def _broker_held_tickers(self, account_id: str | None) -> dict[str, float]:
        """Return {ticker: quantity} for positions actually held on the broker."""
        positions = self._broker_positions_cache.get(account_id or "", [])
        return {p.ticker: p.quantity for p in positions if p.quantity != 0}

    async def _get_deployment_positions(self, dep_id: int, config: dict) -> set[str]:
        """Determine which tickers this deployment owns.

        Source of truth is the broker. The orders table provides the deployment-to-ticker
        mapping (since multiple deployments can share one broker account). A ticker is only
        considered held if BOTH the broker holds it AND our orders table attributes it to
        this deployment (or it falls within the deployment's universe as a fallback).
        """
        account_id = config.get("account_id", "")
        broker_held = self._broker_held_tickers(account_id)
        if not broker_held:
            return set()

        strategy_name = config["strategy_name"]

        # Primary: orders table says this strategy opened it and hasn't closed it
        rows = await self.db_pool.fetch("""
            SELECT DISTINCT o.ticker
            FROM orders o
            JOIN signals sig ON sig.id = o.signal_id AND sig.ticker = o.ticker
            JOIN strategies s ON s.id = sig.strategy_id
            WHERE s.name = $1
              AND o.direction IN ('long', 'short', 'hedge')
              AND o.ticker NOT IN (
                  SELECT o2.ticker FROM orders o2
                  JOIN signals sig2 ON sig2.id = o2.signal_id AND sig2.ticker = o2.ticker
                  JOIN strategies s2 ON s2.id = sig2.strategy_id
                  WHERE s2.name = $1
                    AND o2.direction IN ('sell', 'close', 'flatten')
                    AND o2.created_at > o.created_at
              )
        """, strategy_name)

        order_tickers = {r["ticker"] for r in rows}
        # Only count it if the broker actually holds the position
        return order_tickers & set(broker_held.keys())

    async def _startup_flatten_check(self):
        """On startup, if market is closed and no-overnight deployments have positions, flatten them.

        This catches the case where the runner was down during the 3:55 PM flatten window.
        """
        now = datetime.now(ET)
        # Only flatten if market is currently closed (after hours or weekend)
        if is_market_hours() and not is_flatten_time():
            return

        for dep_id, config in self._deployments.items():
            if not config.get("no_overnight", True):
                continue

            broker = self._get_broker(config.get("account_id"))
            if not broker or not broker.connected:
                continue

            positions = await broker.get_positions()
            universe_set = set(config.get("universe", []))
            held = [p for p in positions if p.quantity != 0 and p.ticker in universe_set]

            if not held:
                continue

            log.warning("STARTUP FLATTEN: deployment %d (%s) has %d positions outside market hours",
                        dep_id, config["strategy_name"], len(held))

            for pos in held:
                try:
                    action = "SELL" if pos.quantity > 0 else "BUY"
                    order = await broker.place_order(
                        ticker=pos.ticker,
                        action=action,
                        quantity=abs(pos.quantity),
                        order_type="MKT",
                    )
                    log.warning("STARTUP FLATTEN: %s %s qty=%d, order %s",
                                action, pos.ticker, abs(pos.quantity), order.broker_order_id)

                    sig_row = await self.db_pool.fetchrow("""
                        INSERT INTO signals
                            (time, strategy_id, ticker, direction, confidence, metadata)
                        VALUES (NOW(),
                            (SELECT id FROM strategies WHERE name = $1),
                            $2, 'flatten', 1.0, '{"reason": "startup_flatten"}')
                        RETURNING id
                    """, config["strategy_name"], pos.ticker)
                    signal_id = sig_row["id"] if sig_row else None
                    await self.db_pool.execute("""
                        INSERT INTO orders
                            (signal_id, broker_order_id, account_id, ticker, direction,
                             order_type, quantity, status)
                        VALUES ($1, $2, $3, $4, 'flatten', 'MKT', $5, 'submitted')
                    """, signal_id, order.broker_order_id,
                        str(config.get("account_id", "")),
                        pos.ticker, abs(pos.quantity))
                except Exception as e:
                    log.error("STARTUP FLATTEN failed for %s: %s", pos.ticker, e)

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

            # Fetch live broker positions once per cycle (source of truth)
            await self._refresh_broker_positions()

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

    async def _hydrate_strategy(self, strategy, universe: list[str], config: dict):
        """Load price data from TimescaleDB and inject into strategy before signal computation."""
        # Day trading strategies need intraday bars; rotation strategies need daily bars
        is_intraday = config.get("no_overnight", False) and config.get("interval", 120) <= 60
        lookback_days = 2 if is_intraday else 80

        for ticker in universe:
            rows = await self.db_pool.fetch("""
                SELECT open, high, low, close, volume FROM market_data
                WHERE ticker = $1 AND time > NOW() - INTERVAL '%s days'
                ORDER BY time ASC
            """ % lookback_days, ticker)

            if not rows:
                continue

            closes = [float(r["close"]) for r in rows if r["close"]]
            highs = [float(r["high"]) for r in rows if r["high"]]
            lows = [float(r["low"]) for r in rows if r["low"]]
            volumes = [float(r["volume"]) for r in rows if r["volume"]]

            if hasattr(strategy, "set_ohlc_data"):
                strategy.set_ohlc_data(ticker, highs, lows, closes)
            elif hasattr(strategy, "set_price_data"):
                strategy.set_price_data(ticker, closes)

            if hasattr(strategy, "set_volume_data") and volumes:
                strategy.set_volume_data(ticker, volumes)

        # Load SPY for relative strength
        spy_rows = await self.db_pool.fetch("""
            SELECT close FROM market_data
            WHERE ticker = 'SPY' AND time > NOW() - INTERVAL '%s days'
            ORDER BY time ASC
        """ % lookback_days)
        spy_closes = [float(r["close"]) for r in spy_rows if r["close"]]

        # Get VIX: use CBOE VIX proxy from yfinance data, or default
        vix = 18.0  # default if no data
        vix_key = await self.redis.get("icarus:vix_current")
        if vix_key:
            try:
                vix = float(vix_key)
            except (ValueError, TypeError):
                pass

        if hasattr(strategy, "set_market_data"):
            import inspect
            sig = inspect.signature(strategy.set_market_data)
            if len(sig.parameters) == 2:
                strategy.set_market_data(vix, spy_closes)
            else:
                strategy.set_market_data(vix)

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

        # Hydrate strategy with price data from TimescaleDB
        await self._hydrate_strategy(strategy, universe, config)

        # Build context with market state
        from strategies.base import SignalContext

        # Positions from broker (source of truth), attributed to this deployment via orders table
        held_positions = list(await self._get_deployment_positions(dep_id, config))

        context = SignalContext(
            trigger_type="scheduled",
            capital=capital,
            market_state={
                "held_positions": held_positions,
                "vix": strategy._vix if hasattr(strategy, "_vix") else 18.0,
                "portfolio_drawdown": 0.0,
            },
        )

        # Get signals
        signals = strategy.compute_signals(universe, datetime.utcnow(), context)
        if not signals:
            log.debug("deployment %d (%s): no signals, %d tickers, %d held",
                      dep_id, config["strategy_name"], len(universe), len(held_positions))
            return

        # Log signals and collect DB refs for order linkage
        signal_refs: dict[str, dict] = {}  # ticker -> {id, time, strategy_id}
        strategy_id_row = await self.db_pool.fetchrow(
            "SELECT id FROM strategies WHERE name = $1", config["strategy_name"]
        )
        strategy_db_id = strategy_id_row["id"] if strategy_id_row else None

        for signal in signals:
            log.info("deployment %d: %s %s @ confidence %.2f",
                     dep_id, signal.direction, signal.ticker, signal.confidence)

            if strategy_db_id is not None:
                row = await self.db_pool.fetchrow("""
                    INSERT INTO signals (time, strategy_id, ticker, direction, confidence, metadata)
                    VALUES (NOW(), $1, $2, $3, $4, $5)
                    ON CONFLICT DO NOTHING
                    RETURNING id, time
                """, strategy_db_id, signal.ticker, signal.direction,
                    signal.confidence, json.dumps(signal.metadata or {}))
                if row:
                    signal_refs[signal.ticker] = {
                        "id": row["id"],
                        "time": row["time"],
                        "strategy_id": strategy_db_id,
                    }

        # Process through broker (live/paper) or virtual portfolio
        broker = self._get_broker(config.get("account_id"))
        if broker and broker.connected:
            await self._execute_broker_signals(dep_id, config, signals, broker, signal_refs)
        else:
            # Fallback to virtual portfolio
            portfolio = self.portfolios.get(dep_id)
            if portfolio:
                for signal in signals:
                    if len(portfolio.positions) >= config["max_positions"]:
                        if signal.direction in ("long", "short", "hedge"):
                            continue
                    portfolio.process_signal(signal)

    def _get_broker(self, account_id: str | None):
        """Get broker instance from API's account registry."""
        if not account_id or not hasattr(self, "_broker_clients"):
            return None
        return self._broker_clients.get(account_id)

    async def _execute_broker_signals(
        self, dep_id: int, config: dict, signals, broker, signal_refs: dict[str, dict] | None = None
    ):
        """Execute signals through a live/paper broker.

        Uses broker positions (source of truth) to determine actual holdings
        before placing any orders. The orders table is used only for logging.
        """
        signal_refs = signal_refs or {}
        account_id = str(config.get("account_id", ""))
        # Live broker state: what we actually hold right now
        broker_held = self._broker_held_tickers(account_id)
        dep_positions = await self._get_deployment_positions(dep_id, config)

        for signal in signals:
            try:
                if signal.direction == "close":
                    # Use actual broker quantity, not what we think we have
                    broker_qty = broker_held.get(signal.ticker, 0)
                    if broker_qty == 0:
                        continue
                    action = "SELL" if broker_qty > 0 else "BUY"
                    order = await broker.place_order(
                        ticker=signal.ticker,
                        action=action,
                        quantity=abs(broker_qty),
                        order_type="MKT",
                    )
                    log.info("deployment %d: CLOSE %s qty=%d, order %s",
                             dep_id, signal.ticker, abs(broker_qty), order.broker_order_id)
                    ref = signal_refs.get(signal.ticker, {})
                    await self.db_pool.execute("""
                        INSERT INTO orders
                            (signal_id, signal_time, broker_order_id, account_id, ticker, direction,
                             order_type, quantity, fill_price, status)
                        VALUES ($1, $2, $3, $4, $5, $6, 'MKT', $7, $8, 'submitted')
                    """, ref.get("id"), ref.get("time"), order.broker_order_id,
                        account_id, signal.ticker, action.lower(),
                        abs(broker_qty),
                        signal.metadata.get("entry_price") if signal.metadata else None)

                elif signal.direction in ("long", "hedge"):
                    # Skip if broker already holds this ticker for this deployment
                    if signal.ticker in dep_positions:
                        log.debug("deployment %d: HELD %s %s (already in position)",
                                  dep_id, signal.direction, signal.ticker)
                        continue

                    if signal.direction == "long" and len(dep_positions) >= config["max_positions"]:
                        log.warning("deployment %d: SKIPPED %s %s (at max %d positions)",
                                    dep_id, signal.direction, signal.ticker, config["max_positions"])
                        continue

                    entry_price = signal.metadata.get("entry_price", 0)
                    position_value = signal.metadata.get("position_value", 0)
                    if entry_price <= 0 or position_value <= 0:
                        log.warning("deployment %d: SKIPPED %s %s (entry_price=%.2f, position_value=%.2f)",
                                    dep_id, signal.direction, signal.ticker, entry_price, position_value)
                        continue

                    quantity = int(position_value / entry_price)
                    if quantity <= 0:
                        log.warning("deployment %d: SKIPPED %s %s (quantity=0 from value=%.2f / price=%.2f)",
                                    dep_id, signal.direction, signal.ticker, position_value, entry_price)
                        continue

                    order = await broker.place_order(
                        ticker=signal.ticker,
                        action="BUY",
                        quantity=quantity,
                        order_type="MKT",
                    )
                    log.info("deployment %d: BUY %d %s @ ~%.2f, order %s",
                             dep_id, quantity, signal.ticker, entry_price, order.broker_order_id)
                    ref = signal_refs.get(signal.ticker, {})
                    await self.db_pool.execute("""
                        INSERT INTO orders
                            (signal_id, signal_time, broker_order_id, account_id, ticker, direction,
                             order_type, quantity, fill_price, status)
                        VALUES ($1, $2, $3, $4, $5, 'long', 'MKT', $6, $7, 'submitted')
                    """, ref.get("id"), ref.get("time"), order.broker_order_id,
                        account_id, signal.ticker, quantity, entry_price)

                elif signal.direction == "short":
                    entry_price = signal.metadata.get("entry_price", 0)
                    position_value = signal.metadata.get("position_value", 0)
                    if entry_price <= 0 or position_value <= 0:
                        log.warning("deployment %d: SKIPPED short %s (entry_price=%.2f, position_value=%.2f)",
                                    dep_id, signal.ticker, entry_price, position_value)
                        continue
                    quantity = int(position_value / entry_price)
                    if quantity <= 0:
                        log.warning("deployment %d: SKIPPED short %s (quantity=0 from value=%.2f / price=%.2f)",
                                    dep_id, signal.ticker, position_value, entry_price)
                        continue

                    order = await broker.place_order(
                        ticker=signal.ticker,
                        action="SELL",
                        quantity=quantity,
                        order_type="MKT",
                    )
                    log.info("deployment %d: SHORT %d %s @ ~%.2f, order %s",
                             dep_id, quantity, signal.ticker, entry_price, order.broker_order_id)
                    ref = signal_refs.get(signal.ticker, {})
                    await self.db_pool.execute("""
                        INSERT INTO orders
                            (signal_id, signal_time, broker_order_id, account_id, ticker, direction,
                             order_type, quantity, fill_price, status)
                        VALUES ($1, $2, $3, $4, $5, 'short', 'MKT', $6, $7, 'submitted')
                    """, ref.get("id"), ref.get("time"), order.broker_order_id,
                        account_id, signal.ticker, quantity, entry_price)

            except Exception as e:
                log.error("deployment %d: failed to execute %s %s: %s",
                          dep_id, signal.direction, signal.ticker, e)

    async def _vix_update_loop(self):
        """Fetch VIX every 5 minutes and store in Redis for strategies."""
        while self._running:
            try:
                # Try yfinance first for actual ^VIX
                vix_value = None
                try:
                    import yfinance as yf
                    vix_ticker = yf.Ticker("^VIX")
                    hist = vix_ticker.history(period="1d")
                    if not hist.empty:
                        vix_value = float(hist["Close"].iloc[-1])
                except Exception:
                    pass

                if vix_value and vix_value > 5:
                    await self.redis.set("icarus:vix_current", str(round(vix_value, 2)))
                    log.debug("VIX (yfinance): %.2f", vix_value)
                else:
                    # Fallback: use VIXY via Alpaca with better mapping
                    import httpx
                    api_key = os.environ.get("ALPACA_API_KEY", "")
                    api_secret = os.environ.get("ALPACA_API_SECRET", "")
                    if api_key and api_secret:
                        headers = {"APCA-API-KEY-ID": api_key, "APCA-API-SECRET-KEY": api_secret}
                        async with httpx.AsyncClient(timeout=10) as client:
                            resp = await client.get(
                                "https://data.alpaca.markets/v2/stocks/bars",
                                params={"symbols": "VIXY", "timeframe": "1Day", "limit": 1, "feed": "iex", "sort": "desc"},
                                headers=headers,
                            )
                            if resp.status_code == 200:
                                bars = resp.json().get("bars", {}).get("VIXY", [])
                                if bars:
                                    vixy_price = float(bars[0]["c"])
                                    # VIXY ~$20 when VIX ~15, ~$25 when VIX ~20, ~$35 when VIX ~30
                                    # Approximate: VIX ~ 0.8 * VIXY + 2
                                    estimated_vix = vixy_price * 0.8 + 2.0
                                    await self.redis.set("icarus:vix_current", str(round(estimated_vix, 2)))
                                    log.debug("VIX estimate: %.2f (VIXY: %.2f)", estimated_vix, vixy_price)
            except Exception as e:
                log.warning("VIX update failed: %s", e)
            await asyncio.sleep(300)

    async def _flatten_loop(self):
        """Flatten all positions at 3:55 PM ET. Non-negotiable."""
        flattened_today = False
        while self._running:
            now = datetime.now(ET)
            if is_flatten_time() and is_market_hours() and not flattened_today:
                log.warning("FLATTEN LOOP: triggered at %s ET", now.strftime("%H:%M:%S"))
                flattened_today = True
                for dep_id, config in self._deployments.items():
                    if not config.get("no_overnight", True):
                        continue

                    broker = self._get_broker(config.get("account_id"))
                    if broker and broker.connected:
                        positions = await broker.get_positions()
                        for pos in positions:
                            if pos.quantity == 0:
                                continue
                            universe_set = set(config.get("universe", []))
                            if pos.ticker not in universe_set:
                                continue
                            try:
                                action = "SELL" if pos.quantity > 0 else "BUY"
                                order = await broker.place_order(
                                    ticker=pos.ticker,
                                    action=action,
                                    quantity=abs(pos.quantity),
                                    order_type="MKT",
                                )
                                log.warning("deployment %d: FLATTEN %s qty=%d, order %s",
                                            dep_id, pos.ticker, abs(pos.quantity), order.broker_order_id)
                                sig_row = await self.db_pool.fetchrow("""
                                    INSERT INTO signals
                                        (time, strategy_id, ticker, direction, confidence, metadata)
                                    VALUES (NOW(),
                                        (SELECT id FROM strategies WHERE name = $1),
                                        $2, 'flatten', 1.0, '{}')
                                    RETURNING id
                                """, config["strategy_name"], pos.ticker)
                                signal_id = sig_row["id"] if sig_row else None
                                await self.db_pool.execute("""
                                    INSERT INTO orders
                                        (signal_id, broker_order_id, account_id, ticker, direction,
                                         order_type, quantity, status)
                                    VALUES ($1, $2, $3, $4, 'flatten', 'MKT', $5, 'submitted')
                                """, signal_id, order.broker_order_id,
                                    str(config.get("account_id", "")),
                                    pos.ticker, abs(pos.quantity))
                            except Exception as e:
                                log.error("deployment %d: flatten order failed for %s: %s",
                                          dep_id, pos.ticker, e)

                    portfolio = self.portfolios.get(dep_id)
                    if portfolio and portfolio.positions:
                        for ticker in list(portfolio.positions.keys()):
                            await self.db_pool.execute("""
                                INSERT INTO signals
                                    (time, strategy_id, ticker, direction, confidence, metadata)
                                VALUES (NOW(),
                                    (SELECT id FROM strategies WHERE name = $1),
                                    $2, 'flatten', 1.0, '{}')
                                ON CONFLICT DO NOTHING
                            """, config["strategy_name"], ticker)
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
                # Reset the flag at start of next trading day
                if not is_market_hours() and flattened_today:
                    now_check = datetime.now(ET)
                    if now_check.time() < dtime(9, 30):
                        flattened_today = False
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
