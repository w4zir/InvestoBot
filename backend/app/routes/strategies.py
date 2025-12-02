import json

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.trading.models import StrategyRunRequest, StrategyRunResponse
from app.trading.orchestrator import run_strategy_run


router = APIRouter()
logger = get_logger(__name__)


@router.post("/run", response_model=StrategyRunResponse)
async def run_strategy(payload: StrategyRunRequest) -> StrategyRunResponse:
    """
    Trigger a full strategy run:
    - Google Agent proposes strategies.
    - Each strategy is backtested.
    - Risk assessment is performed and (optionally) orders are executed.
    """
    try:
        return run_strategy_run(payload)
    except ValueError as e:
        logger.error(f"Validation error in strategy run: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in strategy run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to parse agent response")
    except Exception as e:
        logger.error(f"Unexpected error in strategy run: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")



