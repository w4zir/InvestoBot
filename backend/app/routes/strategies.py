from fastapi import APIRouter

from app.trading.models import StrategyRunRequest, StrategyRunResponse
from app.trading.orchestrator import run_strategy_run


router = APIRouter()


@router.post("/run", response_model=StrategyRunResponse)
async def run_strategy(payload: StrategyRunRequest) -> StrategyRunResponse:
    """
    Trigger a full strategy run:
    - Google Agent proposes strategies.
    - Each strategy is backtested.
    - Risk assessment is performed and (optionally) orders are executed.
    """
    return run_strategy_run(payload)



