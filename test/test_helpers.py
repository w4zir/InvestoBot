"""
Test helper utilities for InvestoBot tests.

Provides common fixtures, mock generators, and utility functions for testing.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.trading.models import (
    BacktestMetrics,
    BacktestResult,
    Order,
    PortfolioPosition,
    PortfolioState,
    StrategyParams,
    StrategyRule,
    StrategySpec,
    Trade,
)


def create_mock_ohlcv_data(
    symbols: List[str],
    start_date: datetime,
    days: int = 100,
    base_price: float = 100.0,
) -> Dict[str, List[Dict]]:
    """
    Generate synthetic OHLCV data for testing.
    
    Args:
        symbols: List of symbols to generate data for
        start_date: Start date for the data
        days: Number of days of data to generate
        base_price: Base price for the first day
    
    Returns:
        Dictionary mapping symbol to list of OHLCV bars
    """
    ohlcv_data = {}
    
    for symbol in symbols:
        bars = []
        price = base_price
        
        for i in range(days):
            timestamp = start_date + timedelta(days=i)
            # Simple random walk with slight upward trend
            price_change = (i % 10) * 0.1 - 0.5  # Oscillating price
            price = max(1.0, price + price_change)
            
            bars.append({
                "timestamp": timestamp,
                "open": price,
                "high": price * 1.02,
                "low": price * 0.98,
                "close": price,
                "volume": 1000000,
            })
        
        ohlcv_data[symbol] = bars
    
    return ohlcv_data


def create_mock_strategy_spec(
    strategy_id: str = "test_strategy",
    universe: Optional[List[str]] = None,
    fraction: float = 0.02,
) -> StrategySpec:
    """
    Create a mock strategy specification for testing.
    
    Args:
        strategy_id: Unique strategy identifier
        universe: List of symbols to trade
        fraction: Position sizing fraction
    
    Returns:
        StrategySpec object
    """
    if universe is None:
        universe = ["AAPL"]
    
    return StrategySpec(
        strategy_id=strategy_id,
        name=f"Test Strategy {strategy_id}",
        description="A test strategy",
        universe=universe,
        rules=[
            StrategyRule(
                type="entry",
                indicator="sma",
                params={"window": 10, "threshold": 0, "direction": "above"},
            ),
            StrategyRule(
                type="exit",
                indicator="sma",
                params={"window": 20, "threshold": 0, "direction": "below"},
            ),
        ],
        params=StrategyParams(
            position_sizing="fixed_fraction",
            fraction=fraction,
            timeframe="1d",
        ),
    )


def create_momentum_strategy_spec(
    strategy_id: str = "momentum_strategy",
    universe: Optional[List[str]] = None,
    fraction: float = 0.02,
) -> StrategySpec:
    """
    Create a momentum strategy specification for testing.
    
    Args:
        strategy_id: Unique strategy identifier
        universe: List of symbols to trade
        fraction: Position sizing fraction
    
    Returns:
        StrategySpec object with momentum rules
    """
    if universe is None:
        universe = ["AAPL"]
    
    return StrategySpec(
        strategy_id=strategy_id,
        name=f"Momentum Strategy {strategy_id}",
        description="A momentum strategy that buys on upward price momentum",
        universe=universe,
        rules=[
            StrategyRule(
                type="entry",
                indicator="momentum",
                params={"window": 20, "return_threshold": 0.02, "lookback": 5},
            ),
            StrategyRule(
                type="exit",
                indicator="momentum",
                params={"window": 20, "return_threshold": -0.01, "lookback": 5},
            ),
        ],
        params=StrategyParams(
            position_sizing="fixed_fraction",
            fraction=fraction,
            timeframe="1d",
        ),
    )


def create_mean_reversion_strategy_spec(
    strategy_id: str = "mean_reversion_strategy",
    universe: Optional[List[str]] = None,
    fraction: float = 0.02,
) -> StrategySpec:
    """
    Create a mean reversion strategy specification for testing.
    
    Args:
        strategy_id: Unique strategy identifier
        universe: List of symbols to trade
        fraction: Position sizing fraction
    
    Returns:
        StrategySpec object with mean reversion rules
    """
    if universe is None:
        universe = ["AAPL"]
    
    return StrategySpec(
        strategy_id=strategy_id,
        name=f"Mean Reversion Strategy {strategy_id}",
        description="A mean reversion strategy that buys on oversold conditions",
        universe=universe,
        rules=[
            StrategyRule(
                type="entry",
                indicator="zscore",
                params={"window": 20, "threshold": -2.0, "direction": "below"},
            ),
            StrategyRule(
                type="exit",
                indicator="zscore",
                params={"window": 20, "threshold": 0.5, "direction": "above"},
            ),
        ],
        params=StrategyParams(
            position_sizing="fixed_fraction",
            fraction=fraction,
            timeframe="1d",
        ),
    )


def create_ma_crossover_strategy_spec(
    strategy_id: str = "ma_crossover_strategy",
    universe: Optional[List[str]] = None,
    fraction: float = 0.02,
) -> StrategySpec:
    """
    Create an MA crossover strategy specification for testing.
    
    Args:
        strategy_id: Unique strategy identifier
        universe: List of symbols to trade
        fraction: Position sizing fraction
    
    Returns:
        StrategySpec object with MA crossover rules
    """
    if universe is None:
        universe = ["AAPL"]
    
    return StrategySpec(
        strategy_id=strategy_id,
        name=f"MA Crossover Strategy {strategy_id}",
        description="A moving average crossover strategy",
        universe=universe,
        rules=[
            StrategyRule(
                type="entry",
                indicator="sma_cross",
                params={"fast": 10, "slow": 20, "direction": "above"},
            ),
            StrategyRule(
                type="exit",
                indicator="sma_cross",
                params={"fast": 10, "slow": 20, "direction": "below"},
            ),
        ],
        params=StrategyParams(
            position_sizing="fixed_fraction",
            fraction=fraction,
            timeframe="1d",
        ),
    )


def create_mock_portfolio_state(
    cash: float = 100000.0,
    positions: Optional[List[PortfolioPosition]] = None,
) -> PortfolioState:
    """
    Create a mock portfolio state for testing.
    
    Args:
        cash: Cash balance
        positions: List of positions (defaults to empty)
    
    Returns:
        PortfolioState object
    """
    if positions is None:
        positions = []
    
    return PortfolioState(cash=cash, positions=positions)


def create_mock_trade(
    symbol: str = "AAPL",
    side: str = "buy",
    quantity: float = 10.0,
    price: float = 150.0,
    timestamp: Optional[datetime] = None,
) -> Trade:
    """
    Create a mock trade for testing.
    
    Args:
        symbol: Symbol being traded
        side: "buy" or "sell"
        quantity: Number of shares
        price: Price per share
        timestamp: Trade timestamp (defaults to now)
    
    Returns:
        Trade object
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    return Trade(
        timestamp=timestamp,
        symbol=symbol,
        side=side,
        quantity=quantity,
        price=price,
    )


def create_mock_order(
    symbol: str = "AAPL",
    side: str = "buy",
    quantity: float = 10.0,
    order_type: str = "market",
    limit_price: Optional[float] = None,
) -> Order:
    """
    Create a mock order for testing.
    
    Args:
        symbol: Symbol to trade
        side: "buy" or "sell"
        quantity: Number of shares
        order_type: "market" or "limit"
        limit_price: Limit price (required for limit orders)
    
    Returns:
        Order object
    """
    return Order(
        symbol=symbol,
        side=side,
        quantity=quantity,
        type=order_type,
        limit_price=limit_price,
    )


def create_mock_backtest_result(
    strategy: StrategySpec,
    sharpe: float = 1.0,
    max_drawdown: float = 0.1,
    total_return: float = 0.15,
    trades: Optional[List[Trade]] = None,
) -> BacktestResult:
    """
    Create a mock backtest result for testing.
    
    Args:
        strategy: Strategy specification
        sharpe: Sharpe ratio
        max_drawdown: Maximum drawdown
        total_return: Total return
        trades: List of trades (defaults to empty)
    
    Returns:
        BacktestResult object
    """
    if trades is None:
        trades = []
    
    return BacktestResult(
        strategy=strategy,
        metrics=BacktestMetrics(
            sharpe=sharpe,
            max_drawdown=max_drawdown,
            total_return=total_return,
        ),
        trade_log=trades,
    )


def create_mock_llm_response(
    strategies: List[Dict[str, Any]],
    wrapped_in_markdown: bool = False,
) -> str:
    """
    Create a mock LLM response for testing.
    
    Args:
        strategies: List of strategy dictionaries
        wrapped_in_markdown: Whether to wrap JSON in markdown code blocks
    
    Returns:
        String representation of LLM response
    """
    import json
    
    response_data = {"strategies": strategies}
    json_str = json.dumps(response_data, indent=2)
    
    if wrapped_in_markdown:
        return f"```json\n{json_str}\n```"
    else:
        return json_str


def create_mock_llm_response_with_text(
    strategies: List[Dict[str, Any]],
    prefix_text: str = "Here are the strategies:",
    suffix_text: str = "These strategies are ready to use.",
) -> str:
    """
    Create a mock LLM response with text before/after JSON.
    
    Args:
        strategies: List of strategy dictionaries
        prefix_text: Text to add before JSON
        suffix_text: Text to add after JSON
    
    Returns:
        String representation of LLM response with text
    """
    import json
    
    response_data = {"strategies": strategies}
    json_str = json.dumps(response_data, indent=2)
    
    return f"{prefix_text}\n\n{json_str}\n\n{suffix_text}"

