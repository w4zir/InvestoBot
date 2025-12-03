"""
Repository layer for database operations.
Handles persistence of strategy runs, backtests, trades, risk violations, and fills.
"""
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.database import get_supabase_client
from app.core.logging import get_logger
from app.trading.models import (
    BacktestResult,
    CandidateResult,
    Fill,
    RiskAssessment,
    StrategyRunResponse,
    Trade,
)

logger = get_logger(__name__)


class RunRepository:
    """Repository for storing and retrieving strategy run results."""

    def __init__(self):
        self.client = get_supabase_client()
        if not self.client:
            logger.warning("Supabase client not available. Persistence will be disabled.")

    def _is_available(self) -> bool:
        """Check if database client is available."""
        return self.client is not None

    def _serialize_model(self, model: Any) -> Dict[str, Any]:
        """Serialize a Pydantic model to a dictionary."""
        if hasattr(model, "model_dump"):
            return model.model_dump(mode="json")
        elif hasattr(model, "dict"):
            return model.dict()
        else:
            return dict(model)

    def save_run(self, run_response: StrategyRunResponse, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a strategy run to the database.

        Args:
            run_response: The StrategyRunResponse to save
            context: Optional context dictionary from the original request

        Returns:
            True if successful, False otherwise
        """
        if not self._is_available():
            return False

        try:
            run_data = {
                "run_id": run_response.run_id,
                "mission": run_response.mission,
                "context": context or {},
                "status": "completed",
                "created_at": run_response.created_at.isoformat(),
            }

            result = self.client.table("strategy_runs").upsert(run_data).execute()
            logger.info(f"Saved strategy run {run_response.run_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save strategy run {run_response.run_id}: {e}", exc_info=True)
            return False

    def save_backtest_result(
        self, run_id: str, strategy_id: str, backtest: BacktestResult, data_range: str
    ) -> Optional[UUID]:
        """
        Save a backtest result to the database.

        Args:
            run_id: The run ID this backtest belongs to
            strategy_id: The strategy ID
            backtest: The BacktestResult to save
            data_range: The data range used for the backtest

        Returns:
            The UUID of the created backtest result, or None if failed
        """
        if not self._is_available():
            return None

        try:
            # Serialize strategy spec and metrics
            strategy_spec = self._serialize_model(backtest.strategy)
            metrics = self._serialize_model(backtest.metrics)

            backtest_data = {
                "run_id": run_id,
                "strategy_id": strategy_id,
                "strategy_spec": strategy_spec,
                "data_range": data_range,
                "sharpe": backtest.metrics.sharpe,
                "max_drawdown": backtest.metrics.max_drawdown,
                "total_return": backtest.metrics.total_return,
                "metrics": metrics,
            }

            result = self.client.table("backtest_results").insert(backtest_data).execute()
            if result.data and len(result.data) > 0:
                backtest_id = UUID(result.data[0]["id"])
                logger.debug(f"Saved backtest result {backtest_id} for strategy {strategy_id}")
                return backtest_id
            return None
        except Exception as e:
            logger.error(f"Failed to save backtest result for strategy {strategy_id}: {e}", exc_info=True)
            return None

    def save_trades(self, run_id: str, strategy_id: str, trades: List[Trade], backtest_result_id: Optional[UUID] = None) -> int:
        """
        Save trades to the database.

        Args:
            run_id: The run ID these trades belong to
            strategy_id: The strategy ID
            trades: List of Trade objects to save
            backtest_result_id: Optional UUID of the backtest result

        Returns:
            Number of trades successfully saved
        """
        if not self._is_available() or not trades:
            return 0

        try:
            trades_data = []
            for trade in trades:
                trade_data = {
                    "run_id": run_id,
                    "strategy_id": strategy_id,
                    "timestamp": trade.timestamp.isoformat(),
                    "symbol": trade.symbol,
                    "side": trade.side,
                    "quantity": trade.quantity,
                    "price": trade.price,
                }
                if backtest_result_id:
                    trade_data["backtest_result_id"] = str(backtest_result_id)
                trades_data.append(trade_data)

            # Insert in batches to avoid payload size issues
            batch_size = 100
            saved_count = 0
            for i in range(0, len(trades_data), batch_size):
                batch = trades_data[i : i + batch_size]
                result = self.client.table("trades").insert(batch).execute()
                saved_count += len(batch)

            logger.debug(f"Saved {saved_count} trades for strategy {strategy_id}")
            return saved_count
        except Exception as e:
            logger.error(f"Failed to save trades for strategy {strategy_id}: {e}", exc_info=True)
            return 0

    def save_risk_violations(
        self, run_id: str, strategy_id: str, risk_assessment: RiskAssessment
    ) -> int:
        """
        Save risk violations to the database.

        Args:
            run_id: The run ID these violations belong to
            strategy_id: The strategy ID
            risk_assessment: The RiskAssessment containing violations

        Returns:
            Number of violations successfully saved
        """
        if not self._is_available() or not risk_assessment.violations:
            return 0

        try:
            violations_data = []
            for violation in risk_assessment.violations:
                # Try to extract violation type from the violation text
                violation_type = None
                if "blacklisted" in violation.lower() or "blacklist" in violation.lower():
                    violation_type = "blacklist"
                elif "notional" in violation.lower():
                    violation_type = "max_notional"
                elif "exposure" in violation.lower():
                    violation_type = "max_exposure"

                violation_data = {
                    "run_id": run_id,
                    "strategy_id": strategy_id,
                    "violation_text": violation,
                    "violation_type": violation_type,
                }
                violations_data.append(violation_data)

            result = self.client.table("risk_violations").insert(violations_data).execute()
            saved_count = len(violations_data)
            logger.debug(f"Saved {saved_count} risk violations for strategy {strategy_id}")
            return saved_count
        except Exception as e:
            logger.error(f"Failed to save risk violations for strategy {strategy_id}: {e}", exc_info=True)
            return 0

    def save_fills(self, run_id: str, strategy_id: str, fills: List[Fill]) -> int:
        """
        Save execution fills to the database.

        Args:
            run_id: The run ID these fills belong to
            strategy_id: The strategy ID
            fills: List of Fill objects to save

        Returns:
            Number of fills successfully saved
        """
        if not self._is_available() or not fills:
            return 0

        try:
            fills_data = []
            for fill in fills:
                fill_data = {
                    "run_id": run_id,
                    "strategy_id": strategy_id,
                    "order_id": fill.order_id,
                    "symbol": fill.symbol,
                    "side": fill.side,
                    "quantity": fill.quantity,
                    "price": fill.price,
                    "timestamp": fill.timestamp.isoformat(),
                }
                fills_data.append(fill_data)

            result = self.client.table("fills").insert(fills_data).execute()
            saved_count = len(fills_data)
            logger.debug(f"Saved {saved_count} fills for strategy {strategy_id}")
            return saved_count
        except Exception as e:
            logger.error(f"Failed to save fills for strategy {strategy_id}: {e}", exc_info=True)
            return 0

    def save_run_metrics(
        self,
        run_id: str,
        metrics: Dict[str, float],
        metric_type: str = "aggregate",
        strategy_id: Optional[str] = None,
    ) -> int:
        """
        Save run-level metrics to the database.

        Args:
            run_id: The run ID
            metrics: Dictionary of metric name -> value
            metric_type: Type of metrics (e.g., 'aggregate', 'per_strategy', 'portfolio')
            strategy_id: Optional strategy ID if these are per-strategy metrics

        Returns:
            Number of metrics successfully saved
        """
        if not self._is_available() or not metrics:
            return 0

        try:
            metrics_data = []
            for metric_name, metric_value in metrics.items():
                metric_data = {
                    "run_id": run_id,
                    "metric_name": metric_name,
                    "metric_value": metric_value,
                    "metric_type": metric_type,
                    "strategy_id": strategy_id,
                }
                metrics_data.append(metric_data)

            # Use upsert to handle duplicates
            result = self.client.table("run_metrics").upsert(metrics_data).execute()
            saved_count = len(metrics_data)
            logger.debug(f"Saved {saved_count} metrics for run {run_id}")
            return saved_count
        except Exception as e:
            logger.error(f"Failed to save run metrics for run {run_id}: {e}", exc_info=True)
            return 0

    def save_candidate_result(self, run_id: str, candidate: CandidateResult, data_range: str) -> bool:
        """
        Save a complete candidate result (backtest, trades, risk, fills).

        Args:
            run_id: The run ID
            candidate: The CandidateResult to save
            data_range: The data range used for backtesting

        Returns:
            True if successful, False otherwise
        """
        if not self._is_available():
            return False

        strategy_id = candidate.strategy.strategy_id

        try:
            # Save backtest result
            backtest_id = self.save_backtest_result(run_id, strategy_id, candidate.backtest, data_range)

            # Save trades
            if candidate.backtest.trade_log:
                self.save_trades(run_id, strategy_id, candidate.backtest.trade_log, backtest_id)

            # Save risk violations
            if candidate.risk:
                self.save_risk_violations(run_id, strategy_id, candidate.risk)

            # Save fills
            if candidate.execution_fills:
                self.save_fills(run_id, strategy_id, candidate.execution_fills)

            # Save strategy-level metrics
            if candidate.backtest.metrics:
                metrics = {
                    "sharpe": candidate.backtest.metrics.sharpe,
                    "max_drawdown": candidate.backtest.metrics.max_drawdown,
                }
                if candidate.backtest.metrics.total_return is not None:
                    metrics["total_return"] = candidate.backtest.metrics.total_return
                self.save_run_metrics(run_id, metrics, metric_type="per_strategy", strategy_id=strategy_id)

            logger.info(f"Saved candidate result for strategy {strategy_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save candidate result for strategy {strategy_id}: {e}", exc_info=True)
            return False

    def save_strategy_run(self, run_response: StrategyRunResponse, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a complete strategy run with all candidates.

        Args:
            run_response: The StrategyRunResponse to save
            context: Optional context dictionary from the original request

        Returns:
            True if successful, False otherwise
        """
        if not self._is_available():
            return False

        try:
            # Extract data_range from context if available
            data_range = context.get("data_range") if context else None
            if not data_range:
                # Try to extract from first candidate's backtest if available
                if run_response.candidates and run_response.candidates[0].backtest:
                    # We don't have data_range in the response, so we'll use a placeholder
                    data_range = "unknown"

            # Save the main run record
            self.save_run(run_response, context)

            # Save each candidate result
            for candidate in run_response.candidates:
                self.save_candidate_result(run_response.run_id, candidate, data_range or "unknown")

            # Save aggregate run-level metrics
            if run_response.candidates:
                # Calculate aggregate metrics
                all_sharpes = [
                    c.backtest.metrics.sharpe
                    for c in run_response.candidates
                    if c.backtest and c.backtest.metrics
                ]
                all_drawdowns = [
                    c.backtest.metrics.max_drawdown
                    for c in run_response.candidates
                    if c.backtest and c.backtest.metrics
                ]

                if all_sharpes:
                    aggregate_metrics = {
                        "avg_sharpe": sum(all_sharpes) / len(all_sharpes),
                        "max_sharpe": max(all_sharpes),
                        "min_sharpe": min(all_sharpes),
                        "avg_max_drawdown": sum(all_drawdowns) / len(all_drawdowns) if all_drawdowns else 0.0,
                        "candidate_count": len(run_response.candidates),
                    }
                    self.save_run_metrics(run_response.run_id, aggregate_metrics, metric_type="aggregate")

            logger.info(f"Successfully saved strategy run {run_response.run_id} with {len(run_response.candidates)} candidates")
            return True
        except Exception as e:
            logger.error(f"Failed to save strategy run {run_response.run_id}: {e}", exc_info=True)
            return False

