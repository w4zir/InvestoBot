from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class StrategyRule(BaseModel):
    type: str
    indicator: str
    params: Dict[str, Any] = Field(default_factory=dict)


class StrategyParams(BaseModel):
    position_sizing: Literal["fixed_fraction", "fixed_size"] = "fixed_fraction"
    fraction: Optional[float] = 0.02
    timeframe: Optional[str] = "1d"


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


class BacktestResult(BaseModel):
    strategy: StrategySpec
    metrics: BacktestMetrics
    trade_log: List[Trade]


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


class StrategyRunResponse(BaseModel):
    run_id: str
    mission: str
    candidates: List[CandidateResult]
    created_at: datetime



