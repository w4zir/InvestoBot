"""
Control endpoints for kill switch, order cancellation, and scheduler management.

These endpoints provide safety mechanisms and operational controls for the trading system.
"""
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException

from app.core.logging import get_logger
from app.core.scheduler import get_active_runs
from app.trading.broker_alpaca import get_alpaca_broker
from app.core.config import get_settings

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

# Global kill switch state
_kill_switch_enabled = False
_kill_switch_reason: Optional[str] = None
_kill_switch_activated_at: Optional[datetime] = None


@router.post("/kill-switch/enable")
async def enable_kill_switch(reason: str = "Manual activation") -> Dict:
    """
    Enable the kill switch to prevent all strategy executions.
    
    When enabled:
    - All new strategy runs are blocked
    - Existing orders can still be cancelled
    - Scheduled runs (if using APScheduler) are paused
    
    Args:
        reason: Optional reason for enabling the kill switch
    
    Returns:
        Status information about the kill switch
    """
    global _kill_switch_enabled, _kill_switch_reason, _kill_switch_activated_at
    
    _kill_switch_enabled = True
    _kill_switch_reason = reason
    _kill_switch_activated_at = datetime.utcnow()
    
    logger.warning(
        "Kill switch enabled - all strategy executions blocked",
        extra={"reason": reason, "activated_at": _kill_switch_activated_at.isoformat()}
    )
    
    return {
        "status": "enabled",
        "reason": reason,
        "activated_at": _kill_switch_activated_at.isoformat(),
        "message": "Kill switch enabled. All strategy executions are blocked."
    }


@router.post("/kill-switch/disable")
async def disable_kill_switch() -> Dict:
    """
    Disable the kill switch and allow strategy executions.
    
    Returns:
        Status information about the kill switch
    """
    global _kill_switch_enabled, _kill_switch_reason, _kill_switch_activated_at
    
    _kill_switch_enabled = False
    previous_reason = _kill_switch_reason
    _kill_switch_reason = None
    _kill_switch_activated_at = None
    
    logger.info(
        "Kill switch disabled - strategy executions allowed",
        extra={"previous_reason": previous_reason}
    )
    
    return {
        "status": "disabled",
        "message": "Kill switch disabled. Strategy executions are allowed."
    }


@router.get("/kill-switch/status")
async def get_kill_switch_status() -> Dict:
    """
    Get current kill switch status.
    
    Returns:
        Current kill switch state and metadata
    """
    return {
        "enabled": _kill_switch_enabled,
        "reason": _kill_switch_reason,
        "activated_at": _kill_switch_activated_at.isoformat() if _kill_switch_activated_at else None
    }


@router.post("/orders/cancel-all")
async def cancel_all_orders() -> Dict:
    """
    Cancel all open orders in Alpaca.
    
    This is a safety endpoint to immediately cancel all pending orders.
    Works even when kill switch is enabled.
    
    Returns:
        Summary of cancellation results
    """
    try:
        broker = get_alpaca_broker()
        
        # Fetch all open orders from Alpaca
        client = broker._client
        resp = client.get("/v2/orders", params={"status": "open"})
        resp.raise_for_status()
        orders = resp.json()
        
        if not orders:
            return {
                "cancelled_count": 0,
                "total_orders": 0,
                "errors": [],
                "message": "No open orders to cancel"
            }
        
        cancelled_count = 0
        errors = []
        
        for order in orders:
            try:
                cancel_resp = client.delete(f"/v2/orders/{order['id']}")
                cancel_resp.raise_for_status()
                cancelled_count += 1
                logger.info(
                    f"Cancelled order {order['id']}",
                    extra={
                        "order_id": order['id'],
                        "symbol": order.get("symbol"),
                        "side": order.get("side"),
                        "quantity": order.get("qty")
                    }
                )
            except Exception as e:
                error_msg = f"Failed to cancel order {order['id']}: {str(e)}"
                errors.append(error_msg)
                logger.error(
                    f"Failed to cancel order {order['id']}",
                    exc_info=True,
                    extra={"order_id": order['id'], "error": str(e)}
                )
        
        logger.info(
            f"Cancelled {cancelled_count} of {len(orders)} open orders",
            extra={"cancelled": cancelled_count, "total": len(orders), "errors": len(errors)}
        )
        
        return {
            "cancelled_count": cancelled_count,
            "total_orders": len(orders),
            "errors": errors,
            "message": f"Cancelled {cancelled_count} of {len(orders)} open orders"
        }
    except Exception as e:
        logger.error("Failed to cancel orders", exc_info=True, extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to cancel orders: {str(e)}")


@router.get("/orders/open")
async def get_open_orders() -> Dict:
    """
    Get all open orders from Alpaca.
    
    Returns:
        List of open orders
    """
    try:
        broker = get_alpaca_broker()
        client = broker._client
        resp = client.get("/v2/orders", params={"status": "open"})
        resp.raise_for_status()
        orders = resp.json()
        
        return {
            "count": len(orders),
            "orders": orders
        }
    except Exception as e:
        logger.error("Failed to fetch open orders", exc_info=True, extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to fetch open orders: {str(e)}")


@router.get("/scheduler/status")
async def get_scheduler_status() -> Dict:
    """
    Get scheduler status and active runs.
    
    Returns:
        Current scheduler state and active runs
    """
    active_runs = get_active_runs()
    return {
        "active_runs": list(active_runs.keys()),
        "active_run_count": len(active_runs),
        "kill_switch_enabled": _kill_switch_enabled
    }


def is_kill_switch_enabled() -> bool:
    """
    Check if kill switch is enabled.
    
    This function is used by the orchestrator to block executions.
    
    Returns:
        True if kill switch is enabled, False otherwise
    """
    return _kill_switch_enabled

