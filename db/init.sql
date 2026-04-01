-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Market data (hypertable)
CREATE TABLE market_data (
    time TIMESTAMPTZ NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume BIGINT,
    source VARCHAR(50),
    PRIMARY KEY (time, ticker)
);
SELECT create_hypertable('market_data', 'time');
CREATE INDEX idx_market_data_ticker ON market_data (ticker, time DESC);

-- Fundamentals
CREATE TABLE fundamentals (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    metric VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION,
    period VARCHAR(20),
    as_of TIMESTAMPTZ NOT NULL,
    source VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_fundamentals_ticker ON fundamentals (ticker, metric, as_of DESC);

-- Sentiment scores (hypertable)
CREATE TABLE sentiment_scores (
    time TIMESTAMPTZ NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    source VARCHAR(50) NOT NULL,
    score DOUBLE PRECISION,
    magnitude DOUBLE PRECISION,
    raw_text TEXT,
    metadata JSONB,
    PRIMARY KEY (time, ticker, source)
);
SELECT create_hypertable('sentiment_scores', 'time');
CREATE INDEX idx_sentiment_ticker ON sentiment_scores (ticker, time DESC);

-- SEC filings
CREATE TABLE filings (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    filing_type VARCHAR(20) NOT NULL,
    filing_date TIMESTAMPTZ NOT NULL,
    url TEXT,
    description TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_filings_ticker ON filings (ticker, filing_date DESC);

-- Social posts (hypertable)
CREATE TABLE social_posts (
    time TIMESTAMPTZ NOT NULL,
    ticker VARCHAR(20),
    source VARCHAR(50) NOT NULL,
    author VARCHAR(200),
    content TEXT,
    score DOUBLE PRECISION,
    engagement JSONB,
    PRIMARY KEY (time, source, author)
);
SELECT create_hypertable('social_posts', 'time');
CREATE INDEX idx_social_ticker ON social_posts (ticker, time DESC);

-- Broker accounts registry
CREATE TABLE broker_accounts (
    id VARCHAR(50) PRIMARY KEY,
    broker_type VARCHAR(20) NOT NULL CHECK (broker_type IN ('ib', 'alpaca')),
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('paper', 'live')),
    display_name VARCHAR(200),
    config JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Strategy registry
CREATE TABLE strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    module_path VARCHAR(500) NOT NULL,
    parameters JSONB DEFAULT '{}',
    mode VARCHAR(20) DEFAULT 'backtest' CHECK (mode IN ('backtest', 'paper', 'live')),
    status VARCHAR(20) DEFAULT 'inactive' CHECK (status IN ('active', 'inactive', 'error')),
    risk_budget DOUBLE PRECISION DEFAULT 0.05,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Strategy-to-account deployment mapping
CREATE TABLE strategy_deployments (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    account_id VARCHAR(50) NOT NULL REFERENCES broker_accounts(id),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'stopped')),
    deployed_at TIMESTAMPTZ DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    UNIQUE(strategy_id, account_id)
);
CREATE INDEX idx_deployments_account ON strategy_deployments (account_id, status);

-- Signals (hypertable)
CREATE TABLE signals (
    time TIMESTAMPTZ NOT NULL,
    strategy_id INTEGER REFERENCES strategies(id),
    ticker VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('long', 'short', 'hedge', 'close')),
    instrument VARCHAR(20) DEFAULT 'stock' CHECK (instrument IN ('stock', 'option', 'future', 'etf')),
    confidence DOUBLE PRECISION,
    hedge_for VARCHAR(20),
    metadata JSONB,
    PRIMARY KEY (time, strategy_id, ticker)
);
SELECT create_hypertable('signals', 'time');

-- Orders
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    signal_id BIGINT,
    ib_order_id INTEGER,
    broker_order_id VARCHAR(100),
    account_id VARCHAR(50),
    ticker VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    order_type VARCHAR(20) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    limit_price DOUBLE PRECISION,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'submitted', 'filled', 'partial', 'cancelled', 'rejected')),
    fill_price DOUBLE PRECISION,
    fill_quantity DOUBLE PRECISION,
    commission DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_orders_status ON orders (status, created_at DESC);

-- Trades
CREATE TABLE trades (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    account_id VARCHAR(50),
    ticker VARCHAR(20) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    commission DOUBLE PRECISION DEFAULT 0,
    slippage DOUBLE PRECISION DEFAULT 0,
    executed_at TIMESTAMPTZ NOT NULL,
    metadata JSONB
);
CREATE INDEX idx_trades_ticker ON trades (ticker, executed_at DESC);

-- Positions
CREATE TABLE positions (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    account_id VARCHAR(50),
    quantity DOUBLE PRECISION NOT NULL,
    avg_cost DOUBLE PRECISION NOT NULL,
    current_price DOUBLE PRECISION,
    unrealized_pnl DOUBLE PRECISION,
    strategy_id INTEGER REFERENCES strategies(id),
    hedge_for INTEGER,
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(ticker, account_id)
);

-- Research log
CREATE TABLE research_log (
    id SERIAL PRIMARY KEY,
    hypothesis TEXT NOT NULL,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'confirmed', 'rejected', 'inconclusive')),
    methodology TEXT,
    findings TEXT,
    data_sources TEXT[],
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Backtest runs
CREATE TABLE backtest_runs (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(200) NOT NULL,
    parameters JSONB,
    universe TEXT[],
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital DOUBLE PRECISION DEFAULT 100000,
    results JSONB,
    metrics JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Universes
CREATE TABLE universes (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    description TEXT,
    filters JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Universe members
CREATE TABLE universe_members (
    id SERIAL PRIMARY KEY,
    universe_id INTEGER REFERENCES universes(id),
    ticker VARCHAR(20) NOT NULL,
    added_at TIMESTAMPTZ DEFAULT NOW(),
    removed_at TIMESTAMPTZ,
    UNIQUE(universe_id, ticker, added_at)
);
CREATE INDEX idx_universe_members ON universe_members (universe_id, removed_at);

-- Economic calendar
CREATE TABLE economic_calendar (
    id SERIAL PRIMARY KEY,
    event_date DATE NOT NULL,
    event_time TIME,
    country VARCHAR(10) DEFAULT 'US',
    event VARCHAR(500) NOT NULL,
    impact VARCHAR(20) DEFAULT 'medium',
    actual VARCHAR(50),
    forecast VARCHAR(50),
    previous VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_econ_cal_date ON economic_calendar (event_date, impact);

-- Dark pool volume (FINRA ATS weekly data)
CREATE TABLE dark_pool_volume (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    ats_name VARCHAR(200),
    share_volume BIGINT NOT NULL DEFAULT 0,
    trade_count INTEGER NOT NULL DEFAULT 0,
    avg_daily_volume BIGINT,
    volume_pct_of_adv DOUBLE PRECISION,
    z_score DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, report_date, ats_name)
);
CREATE INDEX idx_dark_pool_ticker ON dark_pool_volume (ticker, report_date DESC);
CREATE INDEX idx_dark_pool_zscore ON dark_pool_volume (z_score DESC) WHERE z_score > 2.0;

-- Congressional trades (STOCK Act disclosures)
CREATE TABLE congressional_trades (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    congress_member VARCHAR(200) NOT NULL,
    chamber VARCHAR(10) NOT NULL CHECK (chamber IN ('house', 'senate')),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('buy', 'sell')),
    amount_min DOUBLE PRECISION,
    amount_max DOUBLE PRECISION,
    trade_date DATE NOT NULL,
    disclosure_date DATE NOT NULL,
    committee VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, congress_member, trade_date, direction)
);
CREATE INDEX idx_congress_ticker ON congressional_trades (ticker, trade_date DESC);
CREATE INDEX idx_congress_recent ON congressional_trades (trade_date DESC);

-- Short interest
CREATE TABLE short_interest (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    report_date DATE NOT NULL,
    short_shares BIGINT,
    shares_outstanding BIGINT,
    short_pct_float DOUBLE PRECISION,
    days_to_cover DOUBLE PRECISION,
    change_pct DOUBLE PRECISION,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ticker, report_date)
);
CREATE INDEX idx_short_interest_ticker ON short_interest (ticker, report_date DESC);

-- Notifications
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) DEFAULT 'info'
        CHECK (severity IN ('info', 'warning', 'critical')),
    title VARCHAR(500) NOT NULL,
    body TEXT,
    metadata JSONB DEFAULT '{}',
    ticker VARCHAR(20),
    read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_notifications_unread ON notifications (read, created_at DESC);
CREATE INDEX idx_notifications_ticker ON notifications (ticker, created_at DESC);

-- Deployment config (extends strategy_deployments)
CREATE TABLE deployment_config (
    deployment_id INTEGER PRIMARY KEY REFERENCES strategy_deployments(id),
    trigger_mode VARCHAR(20) DEFAULT 'hybrid',
    schedule_interval_sec INTEGER DEFAULT 60,
    universe TEXT[] NOT NULL DEFAULT '{}',
    capital_allocated DOUBLE PRECISION NOT NULL DEFAULT 0,
    stop_max_loss_pct DOUBLE PRECISION DEFAULT 0.05,
    stop_max_drawdown_pct DOUBLE PRECISION DEFAULT 0.10,
    stop_time_limit_days INTEGER,
    no_overnight BOOLEAN DEFAULT TRUE,
    daily_loss_limit_pct DOUBLE PRECISION DEFAULT 0.02,
    max_concurrent_positions INTEGER DEFAULT 3,
    parameters_override JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Deployment snapshots (hypertable for strategy performance tracking)
CREATE TABLE deployment_snapshots (
    time TIMESTAMPTZ NOT NULL,
    deployment_id INTEGER NOT NULL,
    nav DOUBLE PRECISION,
    cash DOUBLE PRECISION,
    positions_count INTEGER,
    unrealized_pnl DOUBLE PRECISION,
    realized_pnl DOUBLE PRECISION,
    drawdown DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    total_trades INTEGER,
    win_rate DOUBLE PRECISION,
    daily_pnl DOUBLE PRECISION,
    positions JSONB,
    PRIMARY KEY (time, deployment_id)
);
SELECT create_hypertable('deployment_snapshots', 'time');

-- Kill switch log
CREATE TABLE kill_switch_log (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50),
    triggered_at TIMESTAMPTZ DEFAULT NOW(),
    reason TEXT NOT NULL,
    trigger_type VARCHAR(50) NOT NULL,
    portfolio_state JSONB,
    positions_flattened JSONB,
    deactivated_at TIMESTAMPTZ,
    deactivated_by VARCHAR(100)
);

-- Debate results (agent-assisted analysis)
CREATE TABLE debate_results (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    bull_thesis TEXT,
    bull_catalysts TEXT[],
    bull_conviction INTEGER,
    bear_thesis TEXT,
    bear_risks TEXT[],
    bear_conviction INTEGER,
    judge_direction VARCHAR(10) CHECK (judge_direction IN ('long', 'short', 'skip')),
    judge_conviction INTEGER,
    price_targets JSONB,
    entry_price DOUBLE PRECISION,
    stop_price DOUBLE PRECISION,
    sector VARCHAR(50),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '24 hours'
);
CREATE INDEX idx_debate_ticker ON debate_results (ticker, created_at DESC);
CREATE INDEX idx_debate_active ON debate_results (expires_at) WHERE expires_at > NOW();
