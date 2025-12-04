-- Supabase Database Schema for Strategy Persistence
-- Run these SQL statements in your Supabase SQL editor to create the tables

-- Table 1: strategy_runs
-- Stores high-level information about each strategy run
CREATE TABLE IF NOT EXISTS strategy_runs (
    run_id TEXT PRIMARY KEY,
    mission TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 2: strategies
-- Stores individual strategy specifications
CREATE TABLE IF NOT EXISTS strategies (
    strategy_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    universe TEXT[] NOT NULL DEFAULT '{}',
    rules JSONB NOT NULL DEFAULT '[]',
    params JSONB NOT NULL DEFAULT '{}',
    template_type TEXT,  -- e.g., "volatility_breakout", "pairs_trading", "intraday_mean_reversion"
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 3: backtest_results
-- Stores backtest performance metrics and trade logs
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id TEXT NOT NULL REFERENCES strategies(strategy_id) ON DELETE CASCADE,
    data_range TEXT NOT NULL,
    sharpe FLOAT NOT NULL,
    max_drawdown FLOAT NOT NULL,
    total_return FLOAT,
    trade_log JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 4: risk_assessments
-- Stores risk assessment results for each strategy
CREATE TABLE IF NOT EXISTS risk_assessments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id TEXT NOT NULL REFERENCES strategies(strategy_id) ON DELETE CASCADE,
    approved_trades JSONB NOT NULL DEFAULT '[]',
    violations TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 5: execution_results
-- Stores execution results (fills, errors) for strategies that were executed
CREATE TABLE IF NOT EXISTS execution_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    strategy_id TEXT NOT NULL REFERENCES strategies(strategy_id) ON DELETE CASCADE,
    fills JSONB NOT NULL DEFAULT '[]',
    execution_error TEXT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_strategies_run_id ON strategies(run_id);
CREATE INDEX IF NOT EXISTS idx_strategies_template_type ON strategies(template_type);
CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy_id ON backtest_results(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_created_at ON backtest_results(created_at);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_strategy_id ON risk_assessments(strategy_id);
CREATE INDEX IF NOT EXISTS idx_execution_results_strategy_id ON execution_results(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_runs_created_at ON strategy_runs(created_at);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at on strategy_runs
CREATE TRIGGER update_strategy_runs_updated_at BEFORE UPDATE ON strategy_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Table 6: portfolio_snapshots
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

-- Indexes for portfolio_snapshots
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_run_id ON portfolio_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_strategy_id ON portfolio_snapshots(strategy_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp ON portfolio_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_snapshot_type ON portfolio_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_created_at ON portfolio_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_run_timestamp ON portfolio_snapshots(run_id, timestamp DESC);

