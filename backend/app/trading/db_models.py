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


class StrategyRunWithDetails(BaseModel):
    """Combined model for a strategy run with all related data."""
    
    run: StrategyRunDB
    strategies: List[StrategyDB] = Field(default_factory=list)
    backtest_results: Dict[str, BacktestResultDB] = Field(default_factory=dict)  # keyed by strategy_id
    risk_assessments: Dict[str, RiskAssessmentDB] = Field(default_factory=dict)  # keyed by strategy_id
    execution_results: Dict[str, ExecutionResultDB] = Field(default_factory=dict)  # keyed by strategy_id

