from fastapi import APIRouter

from app.trading.broker_alpaca import get_alpaca_broker


router = APIRouter()


@router.get("/account")
async def account_status():
    """
    Return a snapshot of the Alpaca paper trading account and positions.
    """
    broker = get_alpaca_broker()
    account = broker.get_account()
    positions = broker.get_positions()
    return {
        "account": account,
        "portfolio": positions.model_dump(),
    }



