-- Observability & Storage Schema Migration
-- Run these SQL statements in your Supabase SQL editor to create the tables
-- This schema is designed for storing strategy run results, metrics, trades, risk violations, and fills

-- Table 1: strategy_runs
-- Main run records with mission and context
CREATE TABLE IF NOT EXISTS strategy_runs (
    run_id TEXT PRIMARY KEY,
    mission TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'completed',  -- 'running', 'completed', 'failed'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 2: backtest_results
-- Backtest metrics and metadata per candidate strategy
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    strategy_id TEXT NOT NULL,
    strategy_spec JSONB NOT NULL,  -- Full strategy specification
    data_range TEXT NOT NULL,
    sharpe FLOAT NOT NULL,
    max_drawdown FLOAT NOT NULL,
    total_return FLOAT,
    metrics JSONB NOT NULL DEFAULT '{}',  -- Additional metrics as JSONB
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 3: trades
-- Individual trade records from backtests
CREATE TABLE IF NOT EXISTS trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    strategy_id TEXT NOT NULL,
    backtest_result_id UUID REFERENCES backtest_results(id) ON DELETE CASCADE,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity FLOAT NOT NULL,
    price FLOAT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 4: risk_violations
-- Risk assessment violations as individual records
CREATE TABLE IF NOT EXISTS risk_violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    strategy_id TEXT NOT NULL,
    violation_text TEXT NOT NULL,
    violation_type TEXT,  -- e.g., 'blacklist', 'max_notional', 'max_exposure'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 5: fills
-- Order execution fills
CREATE TABLE IF NOT EXISTS fills (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    strategy_id TEXT NOT NULL,
    order_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity FLOAT NOT NULL,
    price FLOAT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 6: run_metrics
-- Aggregated metrics per run
CREATE TABLE IF NOT EXISTS run_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    metric_name TEXT NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type TEXT,  -- e.g., 'aggregate', 'per_strategy', 'portfolio'
    strategy_id TEXT,  -- NULL for run-level metrics
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(run_id, metric_name, strategy_id)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_strategy_runs_created_at ON strategy_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_strategy_runs_status ON strategy_runs(status);
CREATE INDEX IF NOT EXISTS idx_backtest_results_run_id ON backtest_results(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy_id ON backtest_results(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_created_at ON backtest_results(created_at);
CREATE INDEX IF NOT EXISTS idx_trades_run_id ON trades(run_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy_id ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_backtest_result_id ON trades(backtest_result_id);
CREATE INDEX IF NOT EXISTS idx_risk_violations_run_id ON risk_violations(run_id);
CREATE INDEX IF NOT EXISTS idx_risk_violations_strategy_id ON risk_violations(strategy_id);
CREATE INDEX IF NOT EXISTS idx_fills_run_id ON fills(run_id);
CREATE INDEX IF NOT EXISTS idx_fills_strategy_id ON fills(strategy_id);
CREATE INDEX IF NOT EXISTS idx_fills_timestamp ON fills(timestamp);
CREATE INDEX IF NOT EXISTS idx_run_metrics_run_id ON run_metrics(run_id);
CREATE INDEX IF NOT EXISTS idx_run_metrics_strategy_id ON run_metrics(strategy_id);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at on strategy_runs
DROP TRIGGER IF EXISTS update_strategy_runs_updated_at ON strategy_runs;
CREATE TRIGGER update_strategy_runs_updated_at BEFORE UPDATE ON strategy_runs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

