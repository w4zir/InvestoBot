from fastapi import APIRouter, HTTPException

from app.trading.broker_manager import get_broker, get_broker_manager
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/account")
async def account_status():
    """
    Return a snapshot of the broker account and positions.
    """
    try:
        broker = get_broker()
        account = broker.get_account()
        positions = broker.get_positions()
        return {
            "account": account,
            "portfolio": positions.model_dump(),
        }
    except Exception as e:
        logger.error("Failed to fetch account status", exc_info=True, extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to fetch account status: {str(e)}")


@router.get("/broker/health")
async def broker_health():
    """
    Get health status for all configured brokers.
    
    Returns:
        Dictionary with health status for primary and failover brokers
    """
    try:
        manager = get_broker_manager()
        health_status = manager.get_all_broker_health()
        current_broker = manager.get_current_broker_name()
        
        return {
            "current_broker": current_broker,
            "brokers": health_status,
        }
    except Exception as e:
        logger.error("Failed to fetch broker health", exc_info=True, extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to fetch broker health: {str(e)}")


@router.get("/broker/current")
async def current_broker():
    """
    Get information about the currently active broker.
    
    Returns:
        Information about the current broker including health status
    """
    try:
        manager = get_broker_manager()
        current_broker_name = manager.get_current_broker_name()
        
        if current_broker_name is None:
            return {
                "broker_name": None,
                "status": "no_broker_available",
                "message": "No broker is currently available"
            }
        
        broker = manager.get_broker()
        health_status = broker.get_health_status()
        
        return {
            "broker_name": current_broker_name,
            "status": "active",
            "health": health_status,
        }
    except Exception as e:
        logger.error("Failed to fetch current broker info", exc_info=True, extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to fetch current broker info: {str(e)}")



