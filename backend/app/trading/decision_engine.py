"""
Multi-source decision engine that combines strategy metrics, news sentiment,
and social media sentiment to make final trading decisions.
"""
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger
from app.trading.models import BacktestMetrics, Order, RiskAssessment

logger = get_logger(__name__)


class DecisionInput:
    """Input to the decision engine combining multiple data sources."""
    
    def __init__(
        self,
        strategy_metrics: List[BacktestMetrics],
        news_data: List[Dict[str, Any]],
        social_sentiment: Dict[str, float],
        current_prices: Dict[str, float],
        proposed_orders: List[Order],
        risk_assessment: RiskAssessment,
    ):
        self.strategy_metrics = strategy_metrics
        self.news_data = news_data
        self.social_sentiment = social_sentiment
        self.current_prices = current_prices
        self.proposed_orders = proposed_orders
        self.risk_assessment = risk_assessment


class DecisionOutput:
    """Output from the decision engine with recommended actions."""
    
    def __init__(
        self,
        recommended_actions: List[Order],
        adjustments: List[Dict[str, Any]],
        reasoning: str,
    ):
        self.recommended_actions = recommended_actions
        self.adjustments = adjustments
        self.reasoning = reasoning


class DecisionEngine:
    """
    Multi-source decision engine that combines:
    - Strategy backtest metrics
    - News sentiment
    - Social media sentiment
    - Risk assessment
    
    To make final trading decisions.
    """
    
    def make_decision(self, input: DecisionInput) -> DecisionOutput:
        """
        Make a trading decision based on multiple data sources.
        
        Args:
            input: DecisionInput containing all relevant data
            
        Returns:
            DecisionOutput with recommended actions and reasoning
        """
        adjustments: List[Dict[str, Any]] = []
        reasoning_parts: List[str] = []
        
        # Start with risk-approved orders
        recommended_orders = input.proposed_orders.copy()
        
        # Analyze strategy metrics
        if input.strategy_metrics:
            avg_sharpe = sum(m.sharpe for m in input.strategy_metrics) / len(input.strategy_metrics)
            avg_drawdown = sum(m.max_drawdown for m in input.strategy_metrics) / len(input.strategy_metrics)
            
            reasoning_parts.append(
                f"Strategy metrics: Sharpe={avg_sharpe:.2f}, Max Drawdown={avg_drawdown:.2%}"
            )
            
            # Reduce position sizes if drawdown is high
            if avg_drawdown > 0.15:  # 15% drawdown threshold
                reasoning_parts.append(f"High drawdown detected ({avg_drawdown:.2%}), reducing position sizes by 50%")
                adjusted_orders = []
                for order in recommended_orders:
                    new_order = Order(
                        symbol=order.symbol,
                        side=order.side,
                        quantity=order.quantity * 0.5,
                        type=order.type,
                        limit_price=order.limit_price,
                    )
                    adjusted_orders.append(new_order)
                    adjustments.append({
                        "type": "size_reduction",
                        "symbol": order.symbol,
                        "reason": "high_drawdown",
                        "factor": 0.5,
                    })
                recommended_orders = adjusted_orders
        
        # Analyze news sentiment
        if input.news_data:
            negative_news_symbols = set()
            for news_item in input.news_data:
                sentiment = news_item.get("sentiment", 0.0)
                symbol = news_item.get("symbol")
                if sentiment < -0.3 and symbol:  # Negative sentiment threshold
                    negative_news_symbols.add(symbol)
                    reasoning_parts.append(f"Negative news detected for {symbol} (sentiment: {sentiment:.2f})")
            
            # Remove or reduce orders for symbols with negative news
            if negative_news_symbols:
                filtered_orders = []
                for order in recommended_orders:
                    if order.symbol in negative_news_symbols:
                        if order.side == "buy":
                            # Cancel buy orders for negative news symbols
                            adjustments.append({
                                "type": "order_cancelled",
                                "symbol": order.symbol,
                                "reason": "negative_news",
                            })
                            reasoning_parts.append(f"Cancelled buy order for {order.symbol} due to negative news")
                        else:
                            # Keep sell orders but reduce size
                            new_order = Order(
                                symbol=order.symbol,
                                side=order.side,
                                quantity=order.quantity * 0.7,
                                type=order.type,
                                limit_price=order.limit_price,
                            )
                            filtered_orders.append(new_order)
                            adjustments.append({
                                "type": "size_reduction",
                                "symbol": order.symbol,
                                "reason": "negative_news",
                                "factor": 0.7,
                            })
                    else:
                        filtered_orders.append(order)
                recommended_orders = filtered_orders
        
        # Analyze social media sentiment
        if input.social_sentiment:
            negative_sentiment_symbols = {
                symbol: sentiment
                for symbol, sentiment in input.social_sentiment.items()
                if sentiment < -0.4  # Very negative social sentiment
            }
            
            if negative_sentiment_symbols:
                adjusted_orders = []
                for order in recommended_orders:
                    if order.symbol in negative_sentiment_symbols and order.side == "buy":
                        # Reduce buy order size
                        sentiment = negative_sentiment_symbols[order.symbol]
                        original_qty = order.quantity
                        new_qty = order.quantity * 0.6
                        new_order = Order(
                            symbol=order.symbol,
                            side=order.side,
                            quantity=new_qty,
                            type=order.type,
                            limit_price=order.limit_price,
                        )
                        adjusted_orders.append(new_order)
                        adjustments.append({
                            "type": "size_reduction",
                            "symbol": order.symbol,
                            "reason": "negative_social_sentiment",
                            "factor": 0.6,
                        })
                        reasoning_parts.append(
                            f"Reduced buy order for {order.symbol} due to negative social sentiment "
                            f"({sentiment:.2f}): {original_qty:.2f} -> {new_qty:.2f}"
                        )
                    else:
                        adjusted_orders.append(order)
                recommended_orders = adjusted_orders
        
        # Respect risk assessment
        if input.risk_assessment.risk_level.value in ["warning", "block"]:
            reasoning_parts.append(
                f"Risk level is {input.risk_assessment.risk_level.value}, "
                f"applying additional conservative adjustments"
            )
            # Further reduce sizes if risk is high
            adjusted_orders = []
            for order in recommended_orders:
                new_order = Order(
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity * 0.8,
                    type=order.type,
                    limit_price=order.limit_price,
                )
                adjusted_orders.append(new_order)
                adjustments.append({
                    "type": "size_reduction",
                    "symbol": order.symbol,
                    "reason": "high_risk_level",
                    "factor": 0.8,
                })
            recommended_orders = adjusted_orders
        
        # Build final reasoning
        if not reasoning_parts:
            reasoning = "No adjustments needed based on available data sources."
        else:
            reasoning = " | ".join(reasoning_parts)
        
        logger.debug(
            f"Decision engine processed {len(input.proposed_orders)} orders, "
            f"recommending {len(recommended_orders)} orders with {len(adjustments)} adjustments"
        )
        
        return DecisionOutput(
            recommended_actions=recommended_orders,
            adjustments=adjustments,
            reasoning=reasoning,
        )
