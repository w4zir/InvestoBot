"""
Pydantic models for database entities.

These models match the Supabase database schema and are used for
serialization/deserialization when persisting and querying data.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class StrategyRunDB(BaseModel):
    """Database model for strategy_runs table."""
    
    run_id: str
    mission: str
    context: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class StrategyDB(BaseModel):
    """Database model for strategies table."""
    
    strategy_id: str
    run_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    universe: List[str] = Field(default_factory=list)
    rules: List[Dict[str, Any]] = Field(default_factory=list)
    params: Dict[str, Any] = Field(default_factory=dict)
    template_type: Optional[str] = None
    created_at: datetime


class BacktestResultDB(BaseModel):
    """Database model for backtest_results table."""
    
    id: UUID
    strategy_id: str
    data_range: str
    sharpe: float
    max_drawdown: float
    total_return: Optional[float] = None
    trade_log: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class RiskAssessmentDB(BaseModel):
    """Database model for risk_assessments table."""
    
    id: UUID
    strategy_id: str
    approved_trades: List[Dict[str, Any]] = Field(default_factory=list)
    violations: List[str] = Field(default_factory=list)
    created_at: datetime


class ExecutionResultDB(BaseModel):
    """Database model for execution_results table."""
    
    id: UUID
    strategy_id: str
    fills: List[Dict[str, Any]] = Field(default_factory=list)
    execution_error: Optional[str] = None
    created_at: datetime


class PortfolioSnapshotDB(BaseModel):
    """Database model for portfolio_snapshots table."""
    
    id: UUID
    run_id: Optional[str] = None
    strategy_id: Optional[str] = None
    snapshot_type: str  # 'initial', 'pre_execution', 'post_execution', 'periodic'
    cash: float
    positions: List[Dict[str, Any]] = Field(default_factory=list)
    portfolio_value: float
    timestamp: datetime
    notes: Optional[str] = None
    created_at: datetime


class DataSourceDB(BaseModel):
    """Database model for data_sources table."""
    
    id: UUID
    source_name: str
    source_type: str
    config: Dict[str, Any] = Field(default_factory=dict)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DataMetadataDB(BaseModel):
    """Database model for data_metadata table."""
    
    id: UUID
    symbol: str
    start_date: datetime
    end_date: datetime
    data_source_id: Optional[UUID] = None
    timeframe: str = "1d"  # "1m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "1wk", "1mo", "3mo"
    file_path: str
    file_format: str = "json"
    file_size_bytes: Optional[int] = None
    row_count: Optional[int] = None
    last_updated: datetime
    data_version: int = 1
    source_version: Optional[str] = None
    checksum: Optional[str] = None
    quality_status: str = "pending"
    quality_report_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime


class DataQualityReportDB(BaseModel):
    """Database model for data_quality_reports table."""
    
    id: UUID
    data_metadata_id: UUID
    overall_status: str  # 'pass', 'warning', 'fail'
    checks_performed: List[Dict[str, Any]] = Field(default_factory=list)
    issues_found: List[Dict[str, Any]] = Field(default_factory=list)
    gap_count: int = 0
    outlier_count: int = 0
    validation_errors: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    checked_at: datetime
    created_at: datetime


class StrategyRunWithDetails(BaseModel):
    """Combined model for a strategy run with all related data."""
    
    run: StrategyRunDB
    strategies: List[StrategyDB] = Field(default_factory=list)
    backtest_results: Dict[str, BacktestResultDB] = Field(default_factory=dict)  # keyed by strategy_id
    risk_assessments: Dict[str, RiskAssessmentDB] = Field(default_factory=dict)  # keyed by strategy_id
    execution_results: Dict[str, ExecutionResultDB] = Field(default_factory=dict)  # keyed by strategy_id

