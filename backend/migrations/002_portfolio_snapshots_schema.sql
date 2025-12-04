-- Portfolio Snapshots Schema Migration
-- Run this SQL in your Supabase SQL editor to add portfolio tracking

-- Table: portfolio_snapshots
-- Stores portfolio state snapshots over time for tracking portfolio evolution
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    strategy_id TEXT REFERENCES strategies(strategy_id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL,  -- 'initial', 'pre_execution', 'post_execution', 'periodic'
    cash FLOAT NOT NULL,
    positions JSONB NOT NULL DEFAULT '[]',  -- Array of {symbol, quantity, average_price}
    portfolio_value FLOAT NOT NULL,  -- Total portfolio value (cash + positions)
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    notes TEXT,  -- Optional notes about the snapshot
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_run_id ON portfolio_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_strategy_id ON portfolio_snapshots(strategy_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp ON portfolio_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_snapshot_type ON portfolio_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_created_at ON portfolio_snapshots(created_at);

-- Composite index for querying snapshots by run and time
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_run_timestamp ON portfolio_snapshots(run_id, timestamp DESC);

