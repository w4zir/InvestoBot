import json
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.agents.strategy_templates import get_template_registry
from app.core.logging import add_log_context, get_logger, LogContext
from app.trading.db_models import StrategyRunDB, StrategyRunWithDetails
from app.trading.models import StrategyRunRequest, StrategyRunResponse
from app.trading.orchestrator import run_strategy_run
from app.trading.persistence import get_persistence_service
from pydantic import BaseModel


router = APIRouter()
logger = get_logger(__name__)


class TemplateInfo(BaseModel):
    """Template information for API responses."""
    template_id: str
    name: str
    description: str
    type: str
    required_params: dict
    optional_params: dict


@router.post("/run", response_model=StrategyRunResponse)
async def run_strategy(payload: StrategyRunRequest) -> StrategyRunResponse:
    """
    Trigger a full strategy run:
    - Google Agent proposes strategies.
    - Each strategy is backtested.
    - Risk assessment is performed and (optionally) orders are executed.
    """
    # Add logging context for the request
    with LogContext(mission=payload.mission, endpoint="/strategies/run"):
        logger.info(
            "Strategy run request received",
            extra={
                "mission": payload.mission,
                "context_keys": list(payload.context.keys()) if payload.context else [],
            },
        )
        
        try:
            response = run_strategy_run(payload)
            
            # Add run_id to log context after it's created
            add_log_context("run_id", response.run_id)
            
            logger.info(
                "Strategy run completed",
                extra={
                    "run_id": response.run_id,
                    "candidate_count": len(response.candidates),
                    "mission": response.mission,
                },
            )
            
            return response
        except ValueError as e:
            logger.error(
                "Validation error in strategy run",
                exc_info=True,
                extra={"error": str(e), "error_type": "ValueError"},
            )
            raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(
                "JSON decode error in strategy run",
                exc_info=True,
                extra={"error": str(e), "error_type": "JSONDecodeError"},
            )
            raise HTTPException(status_code=500, detail="Failed to parse agent response")
        except Exception as e:
            logger.error(
                "Unexpected error in strategy run",
                exc_info=True,
                extra={"error": str(e), "error_type": type(e).__name__},
            )
            raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/history", response_model=List[StrategyRunDB])
async def list_strategy_runs(
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of runs to return"),
    offset: int = Query(default=0, ge=0, description="Number of runs to skip"),
    start_date: Optional[str] = Query(default=None, description="Start date filter (ISO format: YYYY-MM-DD)"),
    end_date: Optional[str] = Query(default=None, description="End date filter (ISO format: YYYY-MM-DD)"),
    mission: Optional[str] = Query(default=None, description="Filter by mission text (partial match)"),
) -> List[StrategyRunDB]:
    """
    List strategy runs with optional filters.
    
    Returns a list of strategy runs ordered by creation date (newest first).
    """
    try:
        persistence_service = get_persistence_service()
        
        # Parse date filters
        start_dt = None
        end_dt = None
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid start_date format: {start_date}. Use YYYY-MM-DD")
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid end_date format: {end_date}. Use YYYY-MM-DD")
        
        runs = persistence_service.list_strategy_runs(
            limit=limit,
            offset=offset,
            start_date=start_dt,
            end_date=end_dt,
            mission_filter=mission,
        )
        
        return runs
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to list strategy runs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/history/{run_id}", response_model=StrategyRunWithDetails)
async def get_strategy_run(run_id: str) -> StrategyRunWithDetails:
    """
    Get detailed information about a specific strategy run.
    
    Returns the run with all associated strategies, backtest results, risk assessments, and execution results.
    """
    try:
        persistence_service = get_persistence_service()
        run_details = persistence_service.get_strategy_run(run_id)
        
        if not run_details:
            raise HTTPException(status_code=404, detail=f"Strategy run not found: {run_id}")
        
        return run_details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get strategy run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/history/strategy/{strategy_id}")
async def get_strategy_history(strategy_id: str) -> dict:
    """
    Get all backtest results for a specific strategy across all runs.
    
    Returns a list of backtest results showing the strategy's performance over time.
    """
    try:
        persistence_service = get_persistence_service()
        history = persistence_service.get_strategy_history(strategy_id)
        
        return {
            "strategy_id": strategy_id,
            "backtest_count": len(history),
            "results": [result.model_dump() for result in history],
        }
    except Exception as e:
        logger.error(f"Failed to get strategy history for {strategy_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/templates", response_model=List[TemplateInfo])
async def list_strategy_templates() -> List[TemplateInfo]:
    """
    List all available strategy templates.
    
    Returns a list of predefined strategy templates that can be instantiated directly.
    """
    try:
        registry = get_template_registry()
        templates = registry.list_all()
        
        return [
            TemplateInfo(
                template_id=template.template_id,
                name=template.name,
                description=template.description,
                type=template.type,
                required_params=template.required_params,
                optional_params=template.optional_params,
            )
            for template in templates
        ]
    except Exception as e:
        logger.error(f"Failed to list strategy templates: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/best")
async def get_best_strategies(
    limit: int = Query(default=10, ge=1, le=100, description="Maximum number of strategies to return"),
    min_sharpe: Optional[float] = Query(default=None, description="Minimum Sharpe ratio filter"),
    max_drawdown: Optional[float] = Query(default=None, description="Maximum drawdown filter (as positive number)"),
) -> dict:
    """
    Get top performing strategies by metrics.
    
    Returns strategies ranked by Sharpe ratio with optional filters.
    """
    try:
        persistence_service = get_persistence_service()
        best = persistence_service.get_best_strategies(
            limit=limit,
            min_sharpe=min_sharpe,
            max_drawdown=max_drawdown,
        )
        
        return {
            "count": len(best),
            "strategies": best,
        }
    except Exception as e:
        logger.error(f"Failed to get best strategies: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



