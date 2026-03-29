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

-- Risk snapshots (hypertable)
CREATE TABLE risk_snapshots (
    time TIMESTAMPTZ NOT NULL,
    account_id VARCHAR(50),
    portfolio_value DOUBLE PRECISION,
    var_95 DOUBLE PRECISION,
    cvar_95 DOUBLE PRECISION,
    max_drawdown DOUBLE PRECISION,
    current_drawdown DOUBLE PRECISION,
    net_exposure DOUBLE PRECISION,
    gross_exposure DOUBLE PRECISION,
    beta DOUBLE PRECISION,
    sharpe DOUBLE PRECISION,
    positions_count INTEGER,
    metadata JSONB,
    PRIMARY KEY (time)
);
SELECT create_hypertable('risk_snapshots', 'time');

-- Approvals (CIO gate)
CREATE TABLE approvals (
    id SERIAL PRIMARY KEY,
    action_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    reasoning TEXT,
    payload JSONB,
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    decided_by VARCHAR(100),
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_approvals_status ON approvals (status, created_at DESC);

-- Factor values (hypertable)
CREATE TABLE factor_values (
    time TIMESTAMPTZ NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    factor_name VARCHAR(100) NOT NULL,
    value DOUBLE PRECISION,
    z_score DOUBLE PRECISION,
    quintile INTEGER,
    PRIMARY KEY (time, ticker, factor_name)
);
SELECT create_hypertable('factor_values', 'time');
CREATE INDEX idx_factor_ticker ON factor_values (ticker, factor_name, time DESC);

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

-- Cost models
CREATE TABLE cost_models (
    id SERIAL PRIMARY KEY,
    ticker VARCHAR(20),
    commission_per_share DOUBLE PRECISION DEFAULT 0.005,
    min_commission DOUBLE PRECISION DEFAULT 1.0,
    avg_spread_bps DOUBLE PRECISION DEFAULT 5.0,
    avg_daily_volume BIGINT,
    slippage_model VARCHAR(50) DEFAULT 'linear',
    short_borrow_rate DOUBLE PRECISION DEFAULT 0.0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_cost_models_ticker ON cost_models (ticker);

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
