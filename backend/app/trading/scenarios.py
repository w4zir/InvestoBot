"""
Golden dataset scenarios module.

Provides predefined crisis scenarios (2008 financial crisis, 2020 COVID, etc.)
and automated gating rules for strategy evaluation.
"""
from datetime import datetime
from typing import Dict, List, Optional

from app.core.logging import get_logger
from app.trading.backtester import run_backtest
from app.trading.models import (
    BacktestRequest,
    GatingResult,
    GatingRule,
    Scenario,
    ScenarioResult,
)

logger = get_logger(__name__)


# Predefined crisis scenarios
SCENARIO_2008_CRISIS = Scenario(
    scenario_id="2008_crisis",
    name="2008 Financial Crisis",
    description="Financial crisis period from October 2007 to March 2009",
    start_date=datetime(2007, 10, 1),
    end_date=datetime(2009, 3, 31),
    tags=["crisis", "volatility", "bear_market", "financial"],
)

SCENARIO_2020_COVID = Scenario(
    scenario_id="2020_covid",
    name="2020 COVID-19 Pandemic",
    description="COVID-19 market crash and recovery period from February to June 2020",
    start_date=datetime(2020, 2, 1),
    end_date=datetime(2020, 6, 30),
    tags=["crisis", "volatility", "pandemic", "bear_market"],
)

SCENARIO_2022_BEAR = Scenario(
    scenario_id="2022_bear",
    name="2022 Bear Market",
    description="Bear market period in 2022 with inflation concerns and rate hikes",
    start_date=datetime(2022, 1, 1),
    end_date=datetime(2022, 12, 31),
    tags=["bear_market", "volatility", "inflation"],
)

# Registry of all predefined scenarios
PREDEFINED_SCENARIOS: Dict[str, Scenario] = {
    SCENARIO_2008_CRISIS.scenario_id: SCENARIO_2008_CRISIS,
    SCENARIO_2020_COVID.scenario_id: SCENARIO_2020_COVID,
    SCENARIO_2022_BEAR.scenario_id: SCENARIO_2022_BEAR,
}


def get_scenario(scenario_id: str) -> Optional[Scenario]:
    """Get a scenario by ID."""
    return PREDEFINED_SCENARIOS.get(scenario_id)


def list_scenarios(tags: Optional[List[str]] = None) -> List[Scenario]:
    """
    List all available scenarios, optionally filtered by tags.

    Args:
        tags: Optional list of tags to filter by (scenario must have all tags)

    Returns:
        List of Scenario objects
    """
    scenarios = list(PREDEFINED_SCENARIOS.values())
    
    if tags:
        filtered = []
        for scenario in scenarios:
            if all(tag in scenario.tags for tag in tags):
                filtered.append(scenario)
        return filtered
    
    return scenarios


def evaluate_scenario(
    request: BacktestRequest,
    scenario: Scenario,
    ohlcv_data: Dict[str, List[Dict]],
) -> ScenarioResult:
    """
    Evaluate a strategy on a specific scenario.

    Args:
        request: BacktestRequest with strategy and costs
        scenario: Scenario to evaluate
        ohlcv_data: Pre-loaded OHLCV data (should cover scenario date range)

    Returns:
        ScenarioResult with backtest results and pass/fail status
    """
    logger.info(f"Evaluating scenario: {scenario.name} ({scenario.scenario_id})")

    # Filter data to scenario date range
    scenario_data: Dict[str, List[Dict]] = {}
    for symbol, bars in ohlcv_data.items():
        scenario_bars = [
            bar
            for bar in bars
            if scenario.start_date <= bar["timestamp"] <= scenario.end_date
        ]
        if scenario_bars:
            scenario_data[symbol] = scenario_bars

    if not scenario_data:
        logger.warning(f"No data available for scenario {scenario.scenario_id}")
        from app.trading.models import BacktestMetrics, BacktestResult
        empty_result = BacktestResult(
            strategy=request.strategy,
            metrics=BacktestMetrics(sharpe=0.0, max_drawdown=0.0, total_return=0.0),
            trade_log=[],
        )
        return ScenarioResult(
            scenario=scenario,
            backtest=empty_result,
            passed=False,
            violations=["No data available for scenario date range"],
        )

    # Run backtest on scenario data
    scenario_request = BacktestRequest(
        strategy=request.strategy,
        data_range=f"{scenario.start_date.isoformat()}:{scenario.end_date.isoformat()}",
        costs=request.costs,
    )
    backtest_result = run_backtest(scenario_request, scenario_data)

    # For now, scenario passes if it completes without errors
    # Gating rules will determine actual pass/fail
    return ScenarioResult(
        scenario=scenario,
        backtest=backtest_result,
        passed=True,  # Will be updated by gating rules
        violations=[],
    )


def _check_gating_rule(
    rule: GatingRule,
    scenario_result: ScenarioResult,
) -> Optional[str]:
    """
    Check if a gating rule is violated.

    Returns:
        Violation message if rule is violated, None otherwise
    """
    # Check if rule applies to this scenario
    if rule.scenario_tags:
        if not any(tag in scenario_result.scenario.tags for tag in rule.scenario_tags):
            return None  # Rule doesn't apply to this scenario

    # Get metric value
    metrics = scenario_result.backtest.metrics
    metric_value: Optional[float] = None

    if rule.metric == "max_drawdown":
        metric_value = metrics.max_drawdown
    elif rule.metric == "sharpe":
        metric_value = metrics.sharpe
    elif rule.metric == "total_return":
        metric_value = metrics.total_return
    else:
        logger.warning(f"Unknown metric in gating rule: {rule.metric}")
        return None

    if metric_value is None:
        return f"Metric {rule.metric} is not available"

    # Check rule condition
    violated = False
    if rule.operator == "<":
        violated = metric_value >= rule.threshold
    elif rule.operator == "<=":
        violated = metric_value > rule.threshold
    elif rule.operator == ">":
        violated = metric_value <= rule.threshold
    elif rule.operator == ">=":
        violated = metric_value < rule.threshold
    elif rule.operator == "==":
        violated = abs(metric_value - rule.threshold) > 0.0001
    else:
        logger.warning(f"Unknown operator in gating rule: {rule.operator}")
        return None

    if violated:
        return (
            f"Scenario {scenario_result.scenario.name}: {rule.metric} = {metric_value:.4f} "
            f"violates rule {rule.metric} {rule.operator} {rule.threshold}"
        )

    return None


def get_default_gating_rules() -> List[GatingRule]:
    """Get default gating rules for strategy evaluation."""
    return [
        GatingRule(
            metric="max_drawdown",
            operator="<",
            threshold=0.5,  # Max drawdown must be less than 50%
            scenario_tags=["crisis"],
        ),
        GatingRule(
            metric="sharpe",
            operator=">",
            threshold=0.5,  # Sharpe ratio must be greater than 0.5
            scenario_tags=None,  # Applies to all scenarios
        ),
        GatingRule(
            metric="total_return",
            operator=">",
            threshold=-0.2,  # Total return must be greater than -20% in crisis scenarios
            scenario_tags=["crisis"],
        ),
    ]


def evaluate_gates(
    request: BacktestRequest,
    scenarios: List[Scenario],
    ohlcv_data: Dict[str, List[Dict]],
    gating_rules: Optional[List[GatingRule]] = None,
) -> GatingResult:
    """
    Evaluate strategy against scenarios and apply gating rules.

    Args:
        request: BacktestRequest with strategy and costs
        scenarios: List of scenarios to evaluate
        ohlcv_data: Pre-loaded OHLCV data
        gating_rules: Optional list of gating rules (uses defaults if None)

    Returns:
        GatingResult with pass/fail status and violations
    """
    if gating_rules is None:
        gating_rules = get_default_gating_rules()

    logger.info(f"Evaluating {len(scenarios)} scenarios with {len(gating_rules)} gating rules")

    # Evaluate each scenario
    scenario_results: List[ScenarioResult] = []
    all_violations: List[str] = []

    for scenario in scenarios:
        scenario_result = evaluate_scenario(request, scenario, ohlcv_data)
        
        # Check gating rules for this scenario
        scenario_violations: List[str] = []
        for rule in gating_rules:
            violation = _check_gating_rule(rule, scenario_result)
            if violation:
                scenario_violations.append(violation)
                all_violations.append(violation)

        # Update scenario result with violations
        scenario_result.passed = len(scenario_violations) == 0
        scenario_result.violations = scenario_violations

        scenario_results.append(scenario_result)

    # Determine overall pass/fail
    # Strategy passes if all scenarios pass
    overall_passed = all(sr.passed for sr in scenario_results)
    
    # Blocking violations are those from scenarios that failed
    blocking_violations = [
        v for sr in scenario_results if not sr.passed for v in sr.violations
    ]

    logger.info(
        f"Gating evaluation complete: overall_passed={overall_passed}, "
        f"blocking_violations={len(blocking_violations)}"
    )

    return GatingResult(
        passed=overall_passed,
        scenario_results=scenario_results,
        overall_passed=overall_passed,
        blocking_violations=blocking_violations,
    )

