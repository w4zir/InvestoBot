from typing import Dict, List, Optional

from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading.models import Order, PortfolioState, RiskAssessment, RiskLevel, EquityPoint

logger = get_logger(__name__)
settings = get_settings()


def risk_assess(
    portfolio: PortfolioState,
    proposed_trades: List[Order],
    latest_prices: Optional[Dict[str, float]] = None,
    equity_curve: Optional[List[EquityPoint]] = None,
    historical_data: Optional[Dict[str, List[Dict]]] = None,
    use_agent: bool = False,
) -> RiskAssessment:
    """
    Enhanced risk assessment with multiple risk checks and optional agent-based reasoning.
    
    Implements tiered architecture: deterministic checks first, then agent for complex cases.

    Args:
        portfolio: Current portfolio state
        proposed_trades: List of proposed orders
        latest_prices: Optional dict of latest prices per symbol (for notional calculation)
        equity_curve: Optional equity curve for drawdown calculation
        historical_data: Optional historical OHLCV data for correlation and liquidity checks
        use_agent: If True, use LLM agent for complex risk decisions

    Returns:
        RiskAssessment with approved trades, violations, warnings, and risk metrics
    """
    # Phase 1: Deterministic risk checks (always run, fast)
    assessment = _deterministic_risk_checks(
        portfolio, proposed_trades, latest_prices, equity_curve, historical_data
    )
    
    # Phase 2: Agent-based assessment (if enabled and needed)
    if use_agent and _needs_agent_review(assessment):
        try:
            agent_assessment = _agent_risk_assessment(
                portfolio, proposed_trades, latest_prices, assessment
            )
            # Merge agent reasoning with deterministic results
            assessment.reasoning = agent_assessment.reasoning
            assessment.warnings.extend(agent_assessment.warnings)
            # Agent can adjust risk level
            if agent_assessment.risk_level != RiskLevel.SAFE:
                assessment.risk_level = agent_assessment.risk_level
        except Exception as e:
            logger.warning(f"Agent risk assessment failed: {e}", exc_info=True)
            # Continue with deterministic assessment only
    
    # Determine final risk level based on violations and warnings
    assessment.risk_level = _determine_risk_level(assessment)
    
    return assessment


def _deterministic_risk_checks(
    portfolio: PortfolioState,
    proposed_trades: List[Order],
    latest_prices: Optional[Dict[str, float]],
    equity_curve: Optional[List[EquityPoint]],
    historical_data: Optional[Dict[str, List[Dict]]],
) -> RiskAssessment:
    """Perform deterministic risk checks."""
    from app.trading.risk_utils import (
        calculate_drawdown,
        check_liquidity,
        get_avg_daily_volume,
        calculate_correlation_matrix,
        group_correlated_symbols,
        calculate_var,
    )
    
    approved: List[Order] = []
    violations: List[str] = []
    warnings: List[str] = []
    
    blacklist = set(settings.risk.blacklist_symbols)

    # Calculate total portfolio value for exposure checks
    portfolio_value = portfolio.cash
    if latest_prices:
        for pos in portfolio.positions:
            if pos.symbol in latest_prices:
                portfolio_value += pos.quantity * latest_prices[pos.symbol]

    # Check drawdown-based limits (blocks all trades if exceeded)
    current_drawdown = None
    if equity_curve and len(equity_curve) > 1:
        portfolio_values = [ep.value for ep in equity_curve]
        current_drawdown, _ = calculate_drawdown(portfolio_values)
        
        if current_drawdown > settings.risk.max_drawdown_threshold:
            return RiskAssessment(
                approved_trades=[],
                violations=[f"Trading blocked: drawdown {current_drawdown:.2%} exceeds threshold {settings.risk.max_drawdown_threshold:.2%}"],
                drawdown_blocked=True,
                current_drawdown=current_drawdown,
                risk_level=RiskLevel.BLOCK,
            )

    # Calculate current position values per symbol
    current_positions_value: Dict[str, float] = {}
    if latest_prices:
        for pos in portfolio.positions:
            if pos.symbol in latest_prices:
                current_positions_value[pos.symbol] = pos.quantity * latest_prices[pos.symbol]

    # Track symbols in proposed trades for correlation checks
    symbols_in_trades = set()
    for order in proposed_trades:
        symbols_in_trades.add(order.symbol)

    # Calculate correlation if historical data available
    correlation_groups: List[set] = []
    if historical_data and len(symbols_in_trades) > 1:
        try:
            # Extract historical returns
            historical_returns: Dict[str, List[float]] = {}
            for symbol in symbols_in_trades:
                if symbol in historical_data and len(historical_data[symbol]) > 1:
                    bars = historical_data[symbol]
                    returns = []
                    for i in range(1, len(bars)):
                        if 'close' in bars[i-1] and 'close' in bars[i]:
                            prev_close = bars[i-1]['close']
                            curr_close = bars[i]['close']
                            if prev_close > 0:
                                ret = (curr_close - prev_close) / prev_close
                                returns.append(ret)
                    if len(returns) >= 20:
                        historical_returns[symbol] = returns
            
            if len(historical_returns) >= 2:
                correlations = calculate_correlation_matrix(
                    list(symbols_in_trades),
                    historical_returns,
                    min_periods=20,
                )
                correlation_groups = group_correlated_symbols(
                    list(symbols_in_trades),
                    correlations,
                    threshold=settings.risk.correlation_threshold,
                )
        except Exception as e:
            logger.warning(f"Correlation calculation failed: {e}", exc_info=True)

    # Check each order
    for order in proposed_trades:
        if order.symbol in blacklist:
            violations.append(f"Symbol {order.symbol} is blacklisted")
            continue

        # Calculate notional using latest price or limit price
        price = order.limit_price
        if price is None and latest_prices and order.symbol in latest_prices:
            price = latest_prices[order.symbol]
        elif price is None:
            price = 100.0  # Fallback to default

        notional = abs(order.quantity) * price

        # Check max trade notional
        if notional > settings.risk.max_trade_notional:
            violations.append(
                f"Order for {order.symbol} exceeds max trade notional ({notional:.2f} > {settings.risk.max_trade_notional:.2f})"
            )
            continue

        # Check portfolio exposure (per trade)
        if portfolio_value > 0:
            exposure = notional / portfolio_value
            if exposure > settings.risk.max_portfolio_exposure:
                violations.append(
                    f"Order for {order.symbol} exceeds max portfolio exposure ({exposure:.2%} > {settings.risk.max_portfolio_exposure:.2%})"
                )
                continue

        # Check per-symbol position limits
        if portfolio_value > 0:
            # Calculate new position value after this order
            current_pos_value = current_positions_value.get(order.symbol, 0.0)
            if order.side == "buy":
                new_position_value = current_pos_value + notional
            else:  # sell
                new_position_value = max(0.0, current_pos_value - notional)
            
            position_exposure = new_position_value / portfolio_value
            if position_exposure > settings.risk.max_position_per_symbol:
                violations.append(
                    f"Position in {order.symbol} would exceed per-symbol limit "
                    f"({position_exposure:.2%} > {settings.risk.max_position_per_symbol:.2%})"
                )
                continue

        # Check liquidity
        if historical_data and order.symbol in historical_data:
            try:
                adv = get_avg_daily_volume(
                    order.symbol,
                    historical_data[order.symbol],
                    lookback_days=30,
                )
                is_valid, msg = check_liquidity(
                    order.symbol,
                    notional,
                    adv,
                    settings.risk.min_avg_volume,
                    settings.risk.min_volume_ratio,
                )
                if not is_valid:
                    violations.append(msg)
                    continue
            except Exception as e:
                logger.warning(f"Liquidity check failed for {order.symbol}: {e}", exc_info=True)
                # Don't block on liquidity check failure, just warn
                warnings.append(f"Could not verify liquidity for {order.symbol}")

        approved.append(order)

    # Check correlation exposure
    if correlation_groups and portfolio_value > 0:
        for group in correlation_groups:
            # Calculate total exposure to this correlated group
            group_exposure = 0.0
            group_symbols = []
            for symbol in group:
                # Current position exposure
                if symbol in current_positions_value:
                    group_exposure += current_positions_value[symbol] / portfolio_value
                # Proposed trade exposure
                for order in approved:
                    if order.symbol == symbol:
                        price = order.limit_price or (latest_prices.get(symbol) if latest_prices else 100.0)
                        notional = abs(order.quantity) * price
                        group_exposure += notional / portfolio_value
                        group_symbols.append(symbol)
            
            if group_exposure > settings.risk.max_correlation_exposure:
                symbols_str = ", ".join(sorted(group_symbols))
                violations.append(
                    f"Correlated group exposure exceeds limit: {symbols_str} "
                    f"({group_exposure:.2%} > {settings.risk.max_correlation_exposure:.2%})"
                )
                # Remove orders from this group from approved
                approved = [o for o in approved if o.symbol not in group]

    # Calculate VaR if equity curve available
    var_estimate = None
    if equity_curve and len(equity_curve) > 10:
        try:
            portfolio_values = [ep.value for ep in equity_curve]
            returns = []
            for i in range(1, len(portfolio_values)):
                if portfolio_values[i-1] > 0:
                    ret = (portfolio_values[i] - portfolio_values[i-1]) / portfolio_values[i-1]
                    returns.append(ret)
            
            if returns:
                var_estimate = calculate_var(
                    returns,
                    confidence_level=settings.risk.var_confidence_level,
                    portfolio_value=portfolio_value,
                )
                # Add warning if VaR is high relative to portfolio
                if var_estimate > portfolio_value * 0.1:  # 10% of portfolio
                    warnings.append(
                        f"High VaR estimate: ${var_estimate:,.2f} ({var_estimate/portfolio_value:.2%} of portfolio)"
                    )
        except Exception as e:
            logger.warning(f"VaR calculation failed: {e}", exc_info=True)

    # Calculate risk score (0-1, higher = riskier)
    risk_score = _calculate_risk_score(approved, violations, warnings, current_drawdown, var_estimate, portfolio_value)

    return RiskAssessment(
        approved_trades=approved,
        violations=violations,
        warnings=warnings,
        drawdown_blocked=False,
        current_drawdown=current_drawdown,
        var_estimate=var_estimate,
        risk_score=risk_score,
        risk_level=RiskLevel.SAFE,  # Will be determined later
    )


def _calculate_risk_score(
    approved: List[Order],
    violations: List[str],
    warnings: List[str],
    current_drawdown: Optional[float],
    var_estimate: Optional[float],
    portfolio_value: float,
) -> float:
    """Calculate overall risk score (0-1, higher = riskier)."""
    score = 0.0
    
    # Violations increase risk
    score += len(violations) * 0.2
    score = min(score, 0.6)  # Cap at 0.6 from violations
    
    # Warnings increase risk
    score += len(warnings) * 0.1
    score = min(score, 0.7)  # Cap at 0.7 from warnings
    
    # Drawdown increases risk
    if current_drawdown:
        score += current_drawdown * 0.2  # Up to 0.2 from drawdown
        score = min(score, 0.9)
    
    # VaR increases risk if high relative to portfolio
    if var_estimate and portfolio_value > 0:
        var_ratio = var_estimate / portfolio_value
        if var_ratio > 0.1:  # > 10% of portfolio
            score += (var_ratio - 0.1) * 2  # Additional risk for high VaR
            score = min(score, 1.0)
    
    return min(score, 1.0)


def _determine_risk_level(assessment: RiskAssessment) -> RiskLevel:
    """Determine risk level based on violations, warnings, and risk score."""
    if assessment.drawdown_blocked or len(assessment.violations) > 0:
        return RiskLevel.BLOCK
    elif assessment.risk_score and assessment.risk_score > 0.7:
        return RiskLevel.WARNING
    elif assessment.risk_score and assessment.risk_score > 0.4 or len(assessment.warnings) > 2:
        return RiskLevel.CAUTION
    else:
        return RiskLevel.SAFE


def _needs_agent_review(assessment: RiskAssessment) -> bool:
    """Determine if agent review is needed."""
    # Use agent if:
    # - Multiple violations that might be contextual
    # - Large trades that pass deterministic checks but need reasoning
    # - Complex portfolio state (many positions, high correlation)
    return (
        len(assessment.violations) > 0 or
        len(assessment.approved_trades) > 5 or
        (assessment.risk_score and assessment.risk_score > 0.5)
    )


def _agent_risk_assessment(
    portfolio: PortfolioState,
    proposed_trades: List[Order],
    latest_prices: Optional[Dict[str, float]],
    deterministic_assessment: RiskAssessment,
) -> RiskAssessment:
    """LLM-based risk assessment for complex cases."""
    from app.agents.risk_agent import assess_risk_with_agent
    
    return assess_risk_with_agent(
        portfolio, proposed_trades, latest_prices, deterministic_assessment
    )



