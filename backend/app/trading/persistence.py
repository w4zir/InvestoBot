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
    DataMetadataDB,
    DataQualityReportDB,
    DataSourceDB,
    ExecutionResultDB,
    PortfolioSnapshotDB,
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
    PortfolioState,
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
    
    def save_portfolio_snapshot(
        self,
        portfolio_state: "PortfolioState",
        run_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        snapshot_type: str = "periodic",
        notes: Optional[str] = None,
        latest_prices: Optional[Dict[str, float]] = None,
    ) -> bool:
        """
        Save a portfolio state snapshot to the database.
        
        Args:
            portfolio_state: The PortfolioState to save
            run_id: Optional run_id to associate with
            strategy_id: Optional strategy_id to associate with
            snapshot_type: Type of snapshot ('initial', 'pre_execution', 'post_execution', 'periodic')
            notes: Optional notes about the snapshot
            latest_prices: Optional dict of latest prices to calculate portfolio value
        
        Returns True if successful, False otherwise (non-blocking).
        """
        if not self.client:
            logger.debug("Skipping portfolio snapshot: Supabase client not available")
            return False
        
        try:
            # Calculate portfolio value
            portfolio_value = portfolio_state.cash
            positions_data = []
            
            for pos in portfolio_state.positions:
                position_dict = {
                    "symbol": pos.symbol,
                    "quantity": pos.quantity,
                    "average_price": pos.average_price,
                }
                positions_data.append(position_dict)
                
                # Add position value if prices available
                if latest_prices and pos.symbol in latest_prices:
                    portfolio_value += pos.quantity * latest_prices[pos.symbol]
            
            snapshot_data = {
                "run_id": run_id,
                "strategy_id": strategy_id,
                "snapshot_type": snapshot_type,
                "cash": portfolio_state.cash,
                "positions": positions_data,
                "portfolio_value": portfolio_value,
                "timestamp": datetime.utcnow().isoformat(),
                "notes": notes,
                "created_at": datetime.utcnow().isoformat(),
            }
            
            self.client.table("portfolio_snapshots").insert(snapshot_data).execute()
            logger.debug(
                f"Saved portfolio snapshot: type={snapshot_type}, value={portfolio_value:.2f}, "
                f"run_id={run_id}, strategy_id={strategy_id}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save portfolio snapshot: {e}", exc_info=True)
            return False
    
    def get_portfolio_snapshots(
        self,
        run_id: Optional[str] = None,
        strategy_id: Optional[str] = None,
        snapshot_type: Optional[str] = None,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[PortfolioSnapshotDB]:
        """
        Retrieve portfolio snapshots with optional filters.
        
        Returns empty list on error (non-blocking).
        """
        if not self.client:
            logger.warning("Cannot query: Supabase client not available")
            return []
        
        try:
            query = self.client.table("portfolio_snapshots").select("*")
            
            if run_id:
                query = query.eq("run_id", run_id)
            if strategy_id:
                query = query.eq("strategy_id", strategy_id)
            if snapshot_type:
                query = query.eq("snapshot_type", snapshot_type)
            if start_date:
                query = query.gte("timestamp", start_date.isoformat())
            if end_date:
                query = query.lte("timestamp", end_date.isoformat())
            
            query = query.order("timestamp", desc=True).limit(limit)
            
            response = query.execute()
            return [PortfolioSnapshotDB(**r) for r in response.data]
        except Exception as e:
            logger.error(f"Failed to get portfolio snapshots: {e}", exc_info=True)
            return []
    
    def save_data_metadata(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        file_path: str,
        data_source_id: Optional[str] = None,
        file_format: str = "json",
        row_count: Optional[int] = None,
        quality_status: str = "pending",
        quality_report_id: Optional[str] = None,
        checksum: Optional[str] = None,
    ) -> bool:
        """
        Save or update data metadata.
        
        Returns True if successful, False otherwise (non-blocking).
        """
        if not self.client:
            logger.debug("Skipping data metadata: Supabase client not available")
            return False
        
        try:
            metadata_data = {
                "symbol": symbol,
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "data_source_id": data_source_id,
                "file_path": file_path,
                "file_format": file_format,
                "row_count": row_count,
                "quality_status": quality_status,
                "quality_report_id": quality_report_id,
                "checksum": checksum,
                "last_updated": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            # Check if exists
            existing = (
                self.client.table("data_metadata")
                .select("id, data_version")
                .eq("symbol", symbol)
                .eq("start_date", start_date.date().isoformat())
                .eq("end_date", end_date.date().isoformat())
                .execute()
            )
            
            if existing.data:
                # Update existing
                metadata_id = existing.data[0]["id"]
                metadata_data["data_version"] = existing.data[0].get("data_version", 1) + 1
                self.client.table("data_metadata").update(metadata_data).eq("id", metadata_id).execute()
            else:
                # Insert new
                metadata_data["data_version"] = 1
                metadata_data["created_at"] = datetime.utcnow().isoformat()
                self.client.table("data_metadata").insert(metadata_data).execute()
            
            return True
        except Exception as e:
            logger.error(f"Failed to save data metadata: {e}", exc_info=True)
            return False
    
    def get_data_metadata(
        self,
        symbol: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[DataMetadataDB]:
        """
        Get data metadata with optional filters.
        
        Returns empty list on error (non-blocking).
        """
        if not self.client:
            logger.warning("Cannot query: Supabase client not available")
            return []
        
        try:
            query = self.client.table("data_metadata").select("*")
            
            if symbol:
                query = query.eq("symbol", symbol)
            if start_date:
                query = query.gte("start_date", start_date.date().isoformat())
            if end_date:
                query = query.lte("end_date", end_date.date().isoformat())
            
            query = query.order("last_updated", desc=True).limit(limit)
            
            response = query.execute()
            return [DataMetadataDB(**row) for row in response.data]
        except Exception as e:
            logger.error(f"Failed to get data metadata: {e}", exc_info=True)
            return []


# Global persistence service instance
_persistence_service: Optional[PersistenceService] = None


def get_persistence_service() -> PersistenceService:
    """Get the global persistence service instance."""
    global _persistence_service
    if _persistence_service is None:
        _persistence_service = PersistenceService()
    return _persistence_service

