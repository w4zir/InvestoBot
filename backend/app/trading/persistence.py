"""
Persistence layer for storing and retrieving strategy runs and results.

This module provides a non-blocking persistence service that gracefully
handles database failures without breaking the strategy generation flow.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from app.core.database import get_supabase_client
from app.core.logging import get_logger
from app.trading.db_models import (
    BacktestResultDB,
    ExecutionResultDB,
    RiskAssessmentDB,
    StrategyDB,
    StrategyRunDB,
    StrategyRunWithDetails,
)
from app.trading.models import (
    BacktestResult,
    CandidateResult,
    Fill,
    Order,
    RiskAssessment,
    StrategyRunResponse,
    StrategySpec,
    Trade,
)

logger = get_logger(__name__)


class PersistenceService:
    """Service for persisting and querying strategy data."""
    
    def __init__(self):
        self.client = get_supabase_client()
        if not self.client:
            logger.warning("Supabase client not available. Persistence will be disabled.")
    
    def save_strategy_run(self, response: StrategyRunResponse, context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Save a complete strategy run with all candidates to the database.
        
        Args:
            response: The StrategyRunResponse to save
            context: Optional context dict to store with the run
        
        Returns True if successful, False otherwise (non-blocking).
        """
        if not self.client:
            logger.debug("Skipping persistence: Supabase client not available")
            return False
        
        try:
            # Extract data_range from context if available
            data_range = context.get("data_range") if context else None
            
            # Save strategy run
            run_data = {
                "run_id": response.run_id,
                "mission": response.mission,
                "context": context or {},
                "created_at": response.created_at.isoformat(),
                "updated_at": response.created_at.isoformat(),
            }
            
            self.client.table("strategy_runs").upsert(run_data).execute()
            logger.info(f"Saved strategy run: {response.run_id}")
            
            # Save each candidate (strategy + backtest + risk + execution)
            for candidate in response.candidates:
                self._save_candidate(response.run_id, candidate, data_range=data_range)
            
            return True
        except Exception as e:
            logger.error(f"Failed to save strategy run {response.run_id}: {e}", exc_info=True)
            return False
    
    def _save_candidate(self, run_id: str, candidate: CandidateResult, data_range: Optional[str] = None) -> None:
        """Save a single candidate result."""
        strategy = candidate.strategy
        
        # Save strategy
        strategy_data = {
            "strategy_id": strategy.strategy_id,
            "run_id": run_id,
            "name": strategy.name,
            "description": strategy.description,
            "universe": strategy.universe,
            "rules": [rule.model_dump() for rule in strategy.rules],
            "params": strategy.params.model_dump(),
            "template_type": None,  # Could be extracted from strategy metadata if available
            "created_at": datetime.utcnow().isoformat(),
        }
        
        self.client.table("strategies").upsert(strategy_data).execute()
        
        # Save backtest result
        backtest = candidate.backtest
        backtest_data = {
            "strategy_id": strategy.strategy_id,
            "data_range": data_range or "",
            "sharpe": backtest.metrics.sharpe,
            "max_drawdown": backtest.metrics.max_drawdown,
            "total_return": backtest.metrics.total_return,
            "trade_log": [trade.model_dump() for trade in backtest.trade_log],
            "created_at": datetime.utcnow().isoformat(),
        }
        
        self.client.table("backtest_results").insert(backtest_data).execute()
        
        # Save risk assessment if available
        if candidate.risk:
            risk_data = {
                "strategy_id": strategy.strategy_id,
                "approved_trades": [order.model_dump() for order in candidate.risk.approved_trades],
                "violations": candidate.risk.violations,
                "created_at": datetime.utcnow().isoformat(),
            }
            
            self.client.table("risk_assessments").insert(risk_data).execute()
        
        # Save execution results if available
        if candidate.execution_fills or candidate.execution_error:
            execution_data = {
                "strategy_id": strategy.strategy_id,
                "fills": [fill.model_dump() for fill in candidate.execution_fills],
                "execution_error": candidate.execution_error,
                "created_at": datetime.utcnow().isoformat(),
            }
            
            self.client.table("execution_results").insert(execution_data).execute()
    
    def get_strategy_run(self, run_id: str) -> Optional[StrategyRunWithDetails]:
        """
        Retrieve a complete strategy run by run_id.
        
        Returns None if not found or on error.
        """
        if not self.client:
            logger.warning("Cannot query: Supabase client not available")
            return None
        
        try:
            # Get run
            run_response = self.client.table("strategy_runs").select("*").eq("run_id", run_id).execute()
            if not run_response.data:
                return None
            
            run_data = run_response.data[0]
            run = StrategyRunDB(**run_data)
            
            # Get strategies for this run
            strategies_response = self.client.table("strategies").select("*").eq("run_id", run_id).execute()
            strategies = [StrategyDB(**s) for s in strategies_response.data]
            
            # Get backtest results
            strategy_ids = [s.strategy_id for s in strategies]
            backtest_results = {}
            risk_assessments = {}
            execution_results = {}
            
            for strategy_id in strategy_ids:
                # Backtest results
                bt_response = (
                    self.client.table("backtest_results")
                    .select("*")
                    .eq("strategy_id", strategy_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if bt_response.data:
                    backtest_results[strategy_id] = BacktestResultDB(**bt_response.data[0])
                
                # Risk assessments
                risk_response = (
                    self.client.table("risk_assessments")
                    .select("*")
                    .eq("strategy_id", strategy_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if risk_response.data:
                    risk_assessments[strategy_id] = RiskAssessmentDB(**risk_response.data[0])
                
                # Execution results
                exec_response = (
                    self.client.table("execution_results")
                    .select("*")
                    .eq("strategy_id", strategy_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                )
                if exec_response.data:
                    execution_results[strategy_id] = ExecutionResultDB(**exec_response.data[0])
            
            return StrategyRunWithDetails(
                run=run,
                strategies=strategies,
                backtest_results=backtest_results,
                risk_assessments=risk_assessments,
                execution_results=execution_results,
            )
        except Exception as e:
            logger.error(f"Failed to get strategy run {run_id}: {e}", exc_info=True)
            return None
    
    def list_strategy_runs(
        self,
        limit: int = 50,
        offset: int = 0,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        mission_filter: Optional[str] = None,
    ) -> List[StrategyRunDB]:
        """
        List strategy runs with optional filters.
        
        Returns empty list on error (non-blocking).
        """
        if not self.client:
            logger.warning("Cannot query: Supabase client not available")
            return []
        
        try:
            query = self.client.table("strategy_runs").select("*")
            
            if start_date:
                query = query.gte("created_at", start_date.isoformat())
            if end_date:
                query = query.lte("created_at", end_date.isoformat())
            if mission_filter:
                query = query.ilike("mission", f"%{mission_filter}%")
            
            query = query.order("created_at", desc=True).limit(limit).offset(offset)
            
            response = query.execute()
            return [StrategyRunDB(**r) for r in response.data]
        except Exception as e:
            logger.error(f"Failed to list strategy runs: {e}", exc_info=True)
            return []
    
    def get_strategy_history(self, strategy_id: str) -> List[BacktestResultDB]:
        """
        Get all backtest results for a specific strategy_id across all runs.
        
        Returns empty list on error.
        """
        if not self.client:
            logger.warning("Cannot query: Supabase client not available")
            return []
        
        try:
            response = (
                self.client.table("backtest_results")
                .select("*")
                .eq("strategy_id", strategy_id)
                .order("created_at", desc=True)
                .execute()
            )
            return [BacktestResultDB(**r) for r in response.data]
        except Exception as e:
            logger.error(f"Failed to get strategy history for {strategy_id}: {e}", exc_info=True)
            return []
    
    def get_best_strategies(
        self,
        limit: int = 10,
        min_sharpe: Optional[float] = None,
        max_drawdown: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query top performing strategies by metrics.
        
        Returns list of dicts with strategy info and metrics.
        """
        if not self.client:
            logger.warning("Cannot query: Supabase client not available")
            return []
        
        try:
            query = (
                self.client.table("backtest_results")
                .select("*, strategies(*)")
                .order("sharpe", desc=True)
            )
            
            if min_sharpe is not None:
                query = query.gte("sharpe", min_sharpe)
            if max_drawdown is not None:
                query = query.lte("max_drawdown", max_drawdown)
            
            response = query.limit(limit).execute()
            
            results = []
            for row in response.data:
                strategy_info = row.get("strategies", {})
                results.append({
                    "strategy_id": row["strategy_id"],
                    "name": strategy_info.get("name"),
                    "sharpe": row["sharpe"],
                    "max_drawdown": row["max_drawdown"],
                    "total_return": row.get("total_return"),
                    "created_at": row["created_at"],
                })
            
            return results
        except Exception as e:
            logger.error(f"Failed to get best strategies: {e}", exc_info=True)
            return []


# Global persistence service instance
_persistence_service: Optional[PersistenceService] = None


def get_persistence_service() -> PersistenceService:
    """Get the global persistence service instance."""
    global _persistence_service
    if _persistence_service is None:
        _persistence_service = PersistenceService()
    return _persistence_service

