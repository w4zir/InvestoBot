-- Migration 005: Add Timeframe Support
-- This migration adds timeframe/interval support to the data_metadata table
-- Run this SQL in your Supabase SQL editor

-- Add timeframe column to data_metadata table
ALTER TABLE data_metadata 
ADD COLUMN IF NOT EXISTS timeframe TEXT NOT NULL DEFAULT '1d';

-- Update the UNIQUE constraint to include timeframe
-- First, drop the existing constraint if it exists
ALTER TABLE data_metadata 
DROP CONSTRAINT IF EXISTS data_metadata_symbol_start_date_end_date_data_source_id_key;

-- Add new unique constraint including timeframe
ALTER TABLE data_metadata 
ADD CONSTRAINT data_metadata_symbol_start_date_end_date_data_source_id_timeframe_key 
UNIQUE(symbol, start_date, end_date, data_source_id, timeframe);

-- Add index on timeframe for query performance
CREATE INDEX IF NOT EXISTS idx_data_metadata_timeframe ON data_metadata(timeframe);

-- Add index on symbol and timeframe combination for common queries
CREATE INDEX IF NOT EXISTS idx_data_metadata_symbol_timeframe ON data_metadata(symbol, timeframe);

