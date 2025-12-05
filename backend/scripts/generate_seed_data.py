"""
Generate seed data for testing and development.

This script populates the database with realistic test data including:
- Strategy runs
- Strategies
- Backtest results
- Risk assessments
- Execution results
- Portfolio snapshots
- Data metadata
- Data quality reports
"""
import argparse
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
from uuid import uuid4

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.core.database import get_supabase_client
from app.core.logging import configure_logging, get_logger
from app.trading.models import StrategyRule, StrategySpec

import logging

configure_logging(level=logging.INFO, enable_json=True, enable_file=True)
logger = get_logger(__name__)


def generate_strategy_runs(count: int = 5) -> List[dict]:
    """Generate strategy run records."""
    runs = []
    missions = [
        "Find momentum strategies for tech stocks",
        "Identify mean reversion opportunities in large caps",
        "Develop volatility breakout strategies",
        "Create pairs trading strategies",
        "Build intraday mean reversion strategies",
    ]
    
    for i in range(count):
        run_id = f"seed_run_{i+1}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        runs.append({
            "run_id": run_id,
            "mission": missions[i % len(missions)],
            "context": {
                "universe": ["AAPL", "MSFT", "GOOGL"],
                "date_range": "2024-01-01 to 2024-12-31",
            },
            "status": random.choice(["completed", "completed", "completed", "failed"]),
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
        })
    
    return runs


def generate_strategies(run_ids: List[str], strategies_per_run: int = 3) -> List[dict]:
    """Generate strategy records."""
    strategies = []
    template_types = ["momentum", "mean_reversion", "volatility_breakout", "pairs_trading", "intraday_mean_reversion"]
    
    strategy_names = [
        "Momentum Breakout",
        "Mean Reversion Z-Score",
        "Volatility Expansion",
        "Pairs Correlation",
        "Intraday Reversal",
        "SMA Crossover",
        "RSI Oversold",
        "Bollinger Bands",
    ]
    
    for run_id in run_ids:
        for i in range(strategies_per_run):
            strategy_id = f"seed_strategy_{len(strategies)+1}_{uuid4().hex[:8]}"
            template_type = random.choice(template_types)
            
            strategies.append({
                "strategy_id": strategy_id,
                "run_id": run_id,
                "name": random.choice(strategy_names),
                "description": f"Test strategy of type {template_type}",
                "universe": random.choice([["AAPL"], ["MSFT"], ["GOOGL"], ["AAPL", "MSFT"]]),
                "rules": [
                    {
                        "type": "entry",
                        "indicator": "sma",
                        "params": {"window": random.randint(10, 50)},
                    }
                ],
                "params": {},
                "template_type": template_type,
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
            })
    
    return strategies


def generate_backtest_results(strategy_ids: List[str]) -> List[dict]:
    """Generate backtest result records."""
    results = []
    
    for strategy_id in strategy_ids:
        sharpe = random.uniform(-1.0, 3.0)
        max_drawdown = random.uniform(0.05, 0.40)
        total_return = random.uniform(-0.20, 0.50)
        
        results.append({
            "strategy_id": strategy_id,
            "data_range": "2024-01-01 to 2024-12-31",
            "sharpe": round(sharpe, 3),
            "max_drawdown": round(max_drawdown, 3),
            "total_return": round(total_return, 3),
            "trade_log": [
                {
                    "timestamp": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
                    "symbol": "AAPL",
                    "side": "buy",
                    "quantity": 10.0,
                    "price": 150.0,
                }
            ],
            "metrics": {
                "win_rate": round(random.uniform(0.4, 0.7), 2),
                "avg_trade_duration": random.randint(1, 30),
            },
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
        })
    
    return results


def generate_risk_assessments(strategy_ids: List[str]) -> List[dict]:
    """Generate risk assessment records."""
    assessments = []
    
    for strategy_id in strategy_ids:
        # Mix of passing and failing assessments
        if random.random() > 0.3:  # 70% pass
            approved_trades = [
                {
                    "symbol": "AAPL",
                    "side": "buy",
                    "quantity": 10.0,
                }
            ]
            violations = []
        else:  # 30% fail
            approved_trades = []
            violations = [
                random.choice([
                    "Symbol AAPL is blacklisted",
                    "Trade exceeds max notional limit",
                    "Portfolio exposure limit exceeded",
                ])
            ]
        
        assessments.append({
            "strategy_id": strategy_id,
            "approved_trades": approved_trades,
            "violations": violations,
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
        })
    
    return assessments


def generate_execution_results(strategy_ids: List[str]) -> List[dict]:
    """Generate execution result records."""
    results = []
    
    for strategy_id in strategy_ids:
        # Mix of successful and failed executions
        if random.random() > 0.2:  # 80% success
            fills = [
                {
                    "order_id": f"order_{uuid4().hex[:8]}",
                    "symbol": "AAPL",
                    "side": "buy",
                    "quantity": 10.0,
                    "price": 150.0,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
            execution_error = None
        else:  # 20% failure
            fills = []
            execution_error = random.choice([
                "Insufficient buying power",
                "Order rejected by broker",
                "Symbol not tradeable",
            ])
        
        results.append({
            "strategy_id": strategy_id,
            "fills": fills,
            "execution_error": execution_error,
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
        })
    
    return results


def generate_portfolio_snapshots(run_ids: List[str], strategy_ids: List[str]) -> List[dict]:
    """Generate portfolio snapshot records."""
    snapshots = []
    snapshot_types = ["initial", "pre_execution", "post_execution", "periodic"]
    
    for run_id in run_ids[:3]:  # Only for first 3 runs
        for snapshot_type in snapshot_types:
            cash = random.uniform(50_000, 200_000)
            positions = [
                {
                    "symbol": "AAPL",
                    "quantity": random.uniform(10, 100),
                    "average_price": random.uniform(140, 160),
                }
            ] if snapshot_type != "initial" else []
            portfolio_value = cash + sum(p["quantity"] * p["average_price"] for p in positions)
            
            snapshots.append({
                "run_id": run_id,
                "strategy_id": random.choice(strategy_ids) if strategy_ids else None,
                "snapshot_type": snapshot_type,
                "cash": round(cash, 2),
                "positions": positions,
                "portfolio_value": round(portfolio_value, 2),
                "timestamp": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
                "notes": f"Snapshot for {snapshot_type}",
                "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
            })
    
    return snapshots


def generate_data_metadata() -> List[dict]:
    """Generate data metadata records."""
    metadata = []
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    timeframes = ["1d", "1d", "1d", "1h", "1wk"]  # Mostly daily, some variety
    
    for symbol in symbols:
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 12, 31)
        timeframe = random.choice(timeframes)
        
        metadata.append({
            "symbol": symbol,
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "data_source_id": None,  # Will be set if data_sources exist
            "timeframe": timeframe,  # Data timeframe (1m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 1wk, 1mo, 3mo)
            "file_path": f"data/ohlcv/{symbol}/2024-01-01_2024-12-31_{timeframe}.json",
            "file_format": "json",
            "file_size_bytes": random.randint(100_000, 1_000_000),
            "row_count": 252,  # Trading days
            "last_updated": (datetime.utcnow() - timedelta(days=random.randint(1, 7))).isoformat(),
            "data_version": 1,
            "checksum": f"md5_{uuid4().hex[:16]}",
            "quality_status": random.choice(["pass", "pass", "pass", "warning", "fail"]),
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 30))).isoformat(),
        })
    
    return metadata


def generate_quality_reports(metadata_ids: List[str]) -> List[dict]:
    """Generate data quality report records."""
    reports = []
    statuses = ["pass", "pass", "pass", "warning", "fail"]
    
    for metadata_id in metadata_ids:
        status = random.choice(statuses)
        
        reports.append({
            "data_metadata_id": metadata_id,
            "overall_status": status,
            "checks_performed": ["missing_values", "ohlc_relationships", "gaps", "outliers"],
            "issues_found": [] if status == "pass" else [
                {
                    "severity": "warning",
                    "check": "gaps",
                    "description": "Found 2 gaps in time series",
                }
            ],
            "gap_count": 0 if status == "pass" else random.randint(1, 5),
            "outlier_count": 0 if status == "pass" else random.randint(1, 10),
            "validation_errors": [],
            "recommendations": [] if status == "pass" else ["Review data source accuracy"],
            "checked_at": (datetime.utcnow() - timedelta(days=random.randint(1, 7))).isoformat(),
            "created_at": (datetime.utcnow() - timedelta(days=random.randint(1, 7))).isoformat(),
        })
    
    return reports


def seed_database(clear_first: bool = False):
    """Generate and insert seed data."""
    client = get_supabase_client()
    if not client:
        logger.error("Supabase client not available")
        return
    
    try:
        if clear_first:
            logger.warning("Clearing existing data...")
            # Note: This will fail if there are foreign key constraints
            # In production, you'd want to delete in the right order
            tables = [
                "data_quality_reports",
                "data_metadata",
                "portfolio_snapshots",
                "execution_results",
                "risk_assessments",
                "backtest_results",
                "strategies",
                "strategy_runs",
            ]
            for table in tables:
                try:
                    client.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
                except Exception as e:
                    logger.warning(f"Could not clear {table}: {e}")
        
        # Generate data
        logger.info("Generating seed data...")
        runs = generate_strategy_runs(5)
        strategies = generate_strategies([r["run_id"] for r in runs], 3)
        strategy_ids = [s["strategy_id"] for s in strategies]
        backtest_results = generate_backtest_results(strategy_ids)
        risk_assessments = generate_risk_assessments(strategy_ids)
        execution_results = generate_execution_results(strategy_ids)
        portfolio_snapshots = generate_portfolio_snapshots([r["run_id"] for r in runs], strategy_ids)
        data_metadata = generate_data_metadata()
        
        # Insert data
        logger.info("Inserting seed data...")
        
        # Insert runs
        for run in runs:
            client.table("strategy_runs").insert(run).execute()
        logger.info(f"Inserted {len(runs)} strategy runs")
        
        # Insert strategies
        for strategy in strategies:
            client.table("strategies").insert(strategy).execute()
        logger.info(f"Inserted {len(strategies)} strategies")
        
        # Insert backtest results
        for result in backtest_results:
            client.table("backtest_results").insert(result).execute()
        logger.info(f"Inserted {len(backtest_results)} backtest results")
        
        # Insert risk assessments
        for assessment in risk_assessments:
            client.table("risk_assessments").insert(assessment).execute()
        logger.info(f"Inserted {len(risk_assessments)} risk assessments")
        
        # Insert execution results
        for result in execution_results:
            client.table("execution_results").insert(result).execute()
        logger.info(f"Inserted {len(execution_results)} execution results")
        
        # Insert portfolio snapshots
        for snapshot in portfolio_snapshots:
            client.table("portfolio_snapshots").insert(snapshot).execute()
        logger.info(f"Inserted {len(portfolio_snapshots)} portfolio snapshots")
        
        # Insert data metadata
        metadata_ids = []
        for metadata in data_metadata:
            response = client.table("data_metadata").insert(metadata).execute()
            if response.data:
                metadata_ids.append(response.data[0]["id"])
        logger.info(f"Inserted {len(data_metadata)} data metadata entries")
        
        # Insert quality reports
        quality_reports = generate_quality_reports(metadata_ids)
        for report in quality_reports:
            client.table("data_quality_reports").insert(report).execute()
        logger.info(f"Inserted {len(quality_reports)} quality reports")
        
        logger.info("Seed data generation completed successfully!")
        
    except Exception as e:
        logger.error(f"Failed to seed database: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate seed data for InvestoBot")
    parser.add_argument("--clear", action="store_true", help="Clear existing data before seeding")
    args = parser.parse_args()
    
    seed_database(clear_first=args.clear)

