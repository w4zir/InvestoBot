-- Supabase Database Schema for Strategy Persistence
-- 
-- NOTE: This file is maintained for reference. The authoritative schema is:
--   backend/migrations/004_unified_schema.sql (with 005_add_timeframe_support.sql)
-- 
-- For new deployments, use the unified schema in the migrations directory.
-- This file matches the unified schema for backward compatibility.

-- ============================================================================
-- CORE TABLES
-- ============================================================================

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
-- Backtest metrics and metadata per candidate strategy
-- Supports both run_id and strategy_id references
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    strategy_id TEXT REFERENCES strategies(strategy_id) ON DELETE CASCADE,
    strategy_spec JSONB,  -- Full strategy specification
    data_range TEXT NOT NULL,
    sharpe FLOAT NOT NULL,
    max_drawdown FLOAT NOT NULL,
    total_return FLOAT,
    trade_log JSONB NOT NULL DEFAULT '[]',  -- Trade log as JSONB array
    metrics JSONB NOT NULL DEFAULT '{}',  -- Additional metrics as JSONB
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

-- ============================================================================
-- OBSERVABILITY TABLES
-- ============================================================================

-- Table 7: trades
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

-- Table 8: risk_violations
-- Risk assessment violations as individual records
CREATE TABLE IF NOT EXISTS risk_violations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id TEXT NOT NULL REFERENCES strategy_runs(run_id) ON DELETE CASCADE,
    strategy_id TEXT NOT NULL,
    violation_text TEXT NOT NULL,
    violation_type TEXT,  -- e.g., 'blacklist', 'max_notional', 'max_exposure'
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 9: fills
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

-- Table 10: run_metrics
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

-- ============================================================================
-- DATA MANAGEMENT TABLES
-- ============================================================================

-- Table 11: data_sources
-- Track data source configurations
CREATE TABLE IF NOT EXISTS data_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name TEXT NOT NULL UNIQUE,  -- 'yahoo', 'synthetic', etc.
    source_type TEXT NOT NULL,  -- 'api', 'synthetic', 'file'
    config JSONB NOT NULL DEFAULT '{}',  -- Source-specific configuration
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Table 12: data_metadata
-- Store metadata about loaded datasets
CREATE TABLE IF NOT EXISTS data_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    data_source_id UUID REFERENCES data_sources(id) ON DELETE SET NULL,
    timeframe TEXT NOT NULL DEFAULT '1d',  -- '1m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '1wk', '1mo', '3mo'
    file_path TEXT NOT NULL,  -- Path to cached data file
    file_format TEXT NOT NULL DEFAULT 'json',  -- 'json', 'parquet'
    file_size_bytes BIGINT,
    row_count INTEGER,
    last_updated TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    data_version INTEGER NOT NULL DEFAULT 1,  -- Incremental version number
    source_version TEXT,  -- Version of data source (e.g., yfinance version)
    checksum TEXT,  -- Hash of data for change detection
    quality_status TEXT NOT NULL DEFAULT 'pending',  -- 'pending', 'pass', 'warning', 'fail'
    quality_report_id UUID,  -- Reference to quality report
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    UNIQUE(symbol, start_date, end_date, data_source_id, timeframe)
);

-- Table 13: data_quality_reports
-- Store quality check results per dataset
CREATE TABLE IF NOT EXISTS data_quality_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    data_metadata_id UUID REFERENCES data_metadata(id) ON DELETE CASCADE,
    overall_status TEXT NOT NULL,  -- 'pass', 'warning', 'fail'
    checks_performed JSONB NOT NULL DEFAULT '[]',  -- List of checks performed
    issues_found JSONB NOT NULL DEFAULT '[]',  -- List of issues with severity
    gap_count INTEGER NOT NULL DEFAULT 0,
    outlier_count INTEGER NOT NULL DEFAULT 0,
    validation_errors JSONB NOT NULL DEFAULT '[]',  -- OHLC validation errors
    recommendations TEXT[],  -- Recommendations for fixing issues
    checked_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Core table indexes
CREATE INDEX IF NOT EXISTS idx_strategy_runs_created_at ON strategy_runs(created_at);
CREATE INDEX IF NOT EXISTS idx_strategy_runs_status ON strategy_runs(status);
CREATE INDEX IF NOT EXISTS idx_strategies_run_id ON strategies(run_id);
CREATE INDEX IF NOT EXISTS idx_strategies_template_type ON strategies(template_type);
CREATE INDEX IF NOT EXISTS idx_backtest_results_run_id ON backtest_results(run_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_strategy_id ON backtest_results(strategy_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_created_at ON backtest_results(created_at);
CREATE INDEX IF NOT EXISTS idx_risk_assessments_strategy_id ON risk_assessments(strategy_id);
CREATE INDEX IF NOT EXISTS idx_execution_results_strategy_id ON execution_results(strategy_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_run_id ON portfolio_snapshots(run_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_strategy_id ON portfolio_snapshots(strategy_id);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_timestamp ON portfolio_snapshots(timestamp);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_snapshot_type ON portfolio_snapshots(snapshot_type);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_created_at ON portfolio_snapshots(created_at);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_run_timestamp ON portfolio_snapshots(run_id, timestamp DESC);

-- Observability table indexes
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

-- Data management table indexes
CREATE INDEX IF NOT EXISTS idx_data_metadata_symbol ON data_metadata(symbol);
CREATE INDEX IF NOT EXISTS idx_data_metadata_date_range ON data_metadata(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_data_metadata_last_updated ON data_metadata(last_updated);
CREATE INDEX IF NOT EXISTS idx_data_metadata_quality_status ON data_metadata(quality_status);
CREATE INDEX IF NOT EXISTS idx_data_metadata_source ON data_metadata(data_source_id);
CREATE INDEX IF NOT EXISTS idx_data_metadata_timeframe ON data_metadata(timeframe);
CREATE INDEX IF NOT EXISTS idx_data_metadata_symbol_timeframe ON data_metadata(symbol, timeframe);
CREATE INDEX IF NOT EXISTS idx_data_quality_reports_metadata_id ON data_quality_reports(data_metadata_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_reports_status ON data_quality_reports(overall_status);

-- ============================================================================
-- FUNCTIONS AND TRIGGERS
-- ============================================================================

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

-- Trigger to auto-update updated_at on data_sources
CREATE TRIGGER update_data_sources_updated_at BEFORE UPDATE ON data_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger to auto-update updated_at on data_metadata
CREATE TRIGGER update_data_metadata_updated_at BEFORE UPDATE ON data_metadata
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- SEED DATA FOR DATA SOURCES
-- ============================================================================

-- Insert default data sources
INSERT INTO data_sources (source_name, source_type, config, is_active)
VALUES 
    ('yahoo', 'api', '{"provider": "yfinance", "rate_limit": 2000}', TRUE),
    ('synthetic', 'synthetic', '{"generator": "random_walk"}', TRUE)
ON CONFLICT (source_name) DO NOTHING;
