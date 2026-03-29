-- Multi-broker orchestration: accounts, deployments, per-account tracking.
-- Run against existing databases. Fresh installs get these in init.sql.

-- Broker accounts registry
CREATE TABLE IF NOT EXISTS broker_accounts (
    id VARCHAR(50) PRIMARY KEY,
    broker_type VARCHAR(20) NOT NULL CHECK (broker_type IN ('ib', 'alpaca')),
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('paper', 'live')),
    display_name VARCHAR(200),
    config JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'error')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Strategy-to-account deployment mapping
CREATE TABLE IF NOT EXISTS strategy_deployments (
    id SERIAL PRIMARY KEY,
    strategy_id INTEGER NOT NULL REFERENCES strategies(id),
    account_id VARCHAR(50) NOT NULL REFERENCES broker_accounts(id),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'paused', 'stopped')),
    deployed_at TIMESTAMPTZ DEFAULT NOW(),
    stopped_at TIMESTAMPTZ,
    UNIQUE(strategy_id, account_id)
);
CREATE INDEX IF NOT EXISTS idx_deployments_account ON strategy_deployments (account_id, status);

-- Add account_id and broker_order_id to orders
ALTER TABLE orders ADD COLUMN IF NOT EXISTS account_id VARCHAR(50);
ALTER TABLE orders ADD COLUMN IF NOT EXISTS broker_order_id VARCHAR(100);

-- Add account_id to positions, update unique constraint
ALTER TABLE positions ADD COLUMN IF NOT EXISTS account_id VARCHAR(50);
-- Drop old unique on ticker alone, replace with (ticker, account_id)
ALTER TABLE positions DROP CONSTRAINT IF EXISTS positions_ticker_key;
CREATE UNIQUE INDEX IF NOT EXISTS idx_positions_ticker_account
    ON positions (ticker, COALESCE(account_id, ''));

-- Add account_id to trades
ALTER TABLE trades ADD COLUMN IF NOT EXISTS account_id VARCHAR(50);

-- Add account_id to risk_snapshots (NULL = aggregate)
ALTER TABLE risk_snapshots ADD COLUMN IF NOT EXISTS account_id VARCHAR(50);

-- Add account_id to kill_switch_log (NULL = global)
ALTER TABLE kill_switch_log ADD COLUMN IF NOT EXISTS account_id VARCHAR(50);
