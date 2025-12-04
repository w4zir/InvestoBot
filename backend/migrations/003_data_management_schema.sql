-- Data Management Schema Migration
-- This migration adds data management tables for OHLCV data caching and quality tracking
-- Note: These tables are also included in 004_unified_schema.sql
-- Run either this migration OR the unified schema, not both

-- Table 1: data_sources
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

-- Table 2: data_metadata
-- Store metadata about loaded datasets
CREATE TABLE IF NOT EXISTS data_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    data_source_id UUID REFERENCES data_sources(id) ON DELETE SET NULL,
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
    UNIQUE(symbol, start_date, end_date, data_source_id)
);

-- Table 3: data_quality_reports
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

-- Indexes
CREATE INDEX IF NOT EXISTS idx_data_metadata_symbol ON data_metadata(symbol);
CREATE INDEX IF NOT EXISTS idx_data_metadata_date_range ON data_metadata(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_data_metadata_last_updated ON data_metadata(last_updated);
CREATE INDEX IF NOT EXISTS idx_data_metadata_quality_status ON data_metadata(quality_status);
CREATE INDEX IF NOT EXISTS idx_data_metadata_source ON data_metadata(data_source_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_reports_metadata_id ON data_quality_reports(data_metadata_id);
CREATE INDEX IF NOT EXISTS idx_data_quality_reports_status ON data_quality_reports(overall_status);

-- Triggers
CREATE TRIGGER update_data_sources_updated_at BEFORE UPDATE ON data_sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_data_metadata_updated_at BEFORE UPDATE ON data_metadata
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Seed data sources
INSERT INTO data_sources (source_name, source_type, config, is_active)
VALUES 
    ('yahoo', 'api', '{"provider": "yfinance", "rate_limit": 2000}', TRUE),
    ('synthetic', 'synthetic', '{"generator": "random_walk"}', TRUE)
ON CONFLICT (source_name) DO NOTHING;

