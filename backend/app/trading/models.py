from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class PortfolioEvaluationMode(str, Enum):
    PER_SYMBOL = "per_symbol"
    PORTFOLIO_LEVEL = "portfolio_level"


class RebalancingMode(str, Enum):
    TIME_BASED = "time_based"
    SIGNAL_BASED = "signal_based"
    BOTH = "both"


class StrategyRule(BaseModel):
    type: str
    indicator: str
    params: Dict[str, Any] = Field(default_factory=dict)


class StrategyParams(BaseModel):
    position_sizing: Literal["fixed_fraction", "fixed_size"] = "fixed_fraction"
    fraction: Optional[float] = 0.02
    timeframe: Optional[str] = "1d"
    evaluation_mode: PortfolioEvaluationMode = PortfolioEvaluationMode.PER_SYMBOL
    rebalancing_mode: RebalancingMode = RebalancingMode.SIGNAL_BASED
    rebalancing_frequency: Optional[str] = None  # e.g., "1d", "1w" for time-based
    max_positions: Optional[int] = None  # for portfolio-level mode


class StrategySpec(BaseModel):
    strategy_id: str
    name: Optional[str] = None
    description: Optional[str] = None
    universe: List[str] = Field(default_factory=list)
    rules: List[StrategyRule]
    params: StrategyParams


class BacktestRequest(BaseModel):
    strategy: StrategySpec
    data_range: str
    costs: Dict[str, float] = Field(default_factory=dict)


class Trade(BaseModel):
    timestamp: datetime
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float


class BacktestMetrics(BaseModel):
    sharpe: float
    max_drawdown: float
    total_return: Optional[float] = None


class EquityPoint(BaseModel):
    timestamp: datetime
    value: float


class BacktestResult(BaseModel):
    strategy: StrategySpec
    metrics: BacktestMetrics
    trade_log: List[Trade]
    equity_curve: Optional[List[EquityPoint]] = Field(default=None)


class PortfolioPosition(BaseModel):
    symbol: str
    quantity: float
    average_price: float


class PortfolioState(BaseModel):
    cash: float
    positions: List[PortfolioPosition] = Field(default_factory=list)


class Order(BaseModel):
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    type: Literal["market", "limit"] = "market"
    limit_price: Optional[float] = None


class Fill(BaseModel):
    order_id: str
    symbol: str
    side: Literal["buy", "sell"]
    quantity: float
    price: float
    timestamp: datetime


class RiskAssessment(BaseModel):
    approved_trades: List[Order] = Field(default_factory=list)
    violations: List[str] = Field(default_factory=list)


class StrategyRunRequest(BaseModel):
    mission: str
    context: Dict[str, Any] = Field(default_factory=dict)


class CandidateResult(BaseModel):
    strategy: StrategySpec
    backtest: BacktestResult
    risk: Optional[RiskAssessment] = None
    execution_fills: List[Fill] = Field(default_factory=list)
    execution_error: Optional[str] = None
    validation: Optional["WalkForwardResult"] = None
    gating: Optional["GatingResult"] = None


class StrategyRunResponse(BaseModel):
    run_id: str
    mission: str
    candidates: List[CandidateResult]
    created_at: datetime


class ValidationConfig(BaseModel):
    train_split: float = 0.7
    validation_split: float = 0.15
    holdout_split: float = 0.15
    walk_forward: bool = False
    window_size: Optional[int] = None  # for fixed-size windows


class WalkForwardResult(BaseModel):
    windows: List[BacktestResult] = Field(default_factory=list)
    aggregate_metrics: BacktestMetrics
    train_metrics: BacktestMetrics
    validation_metrics: BacktestMetrics
    holdout_metrics: Optional[BacktestMetrics] = None


class Scenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    start_date: datetime
    end_date: datetime
    tags: List[str] = Field(default_factory=list)


class ScenarioResult(BaseModel):
    scenario: Scenario
    backtest: BacktestResult
    passed: bool
    violations: List[str] = Field(default_factory=list)


class GatingRule(BaseModel):
    metric: str  # e.g., "max_drawdown", "sharpe", "total_return"
    operator: str  # e.g., "<", ">", ">="
    threshold: float
    scenario_tags: Optional[List[str]] = None  # apply to specific scenario types


class GatingResult(BaseModel):
    passed: bool
    scenario_results: List[ScenarioResult] = Field(default_factory=list)
    overall_passed: bool
    blocking_violations: List[str] = Field(default_factory=list)



