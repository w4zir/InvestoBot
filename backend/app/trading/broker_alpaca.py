from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from time import sleep

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    RetryError,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading.broker_interface import BrokerInterface
from app.trading.models import Fill, Order, PortfolioPosition, PortfolioState

logger = get_logger(__name__)
settings = get_settings()


def _retry_on_http_error(exception: Exception) -> bool:
    """Check if exception is an HTTP error that should be retried."""
    if isinstance(exception, httpx.HTTPStatusError):
        status = exception.response.status_code
        # Retry on rate limits (429) and server errors (5xx)
        return status == 429 or (500 <= status < 600)
    if isinstance(exception, (httpx.NetworkError, httpx.TimeoutException)):
        return True
    return False


class AlpacaBroker(BrokerInterface):
    """
    Enhanced Alpaca paper trading client with order management, monitoring,
    and error handling capabilities.
    """

    def __init__(self, timeout: float = 30.0, max_retries: int = 3) -> None:
        if not settings.alpaca.api_key or not settings.alpaca.secret_key:
            logger.warning(
                "Alpaca API credentials are not fully configured; broker calls will fail."
            )
        # Normalize base_url to remove trailing /v2/ if present
        base_url = str(settings.alpaca.base_url).rstrip("/")
        if base_url.endswith("/v2"):
            base_url = base_url[:-3]
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "APCA-API-KEY-ID": settings.alpaca.api_key or "",
                "APCA-API-SECRET-KEY": settings.alpaca.secret_key or "",
            },
            timeout=timeout,
        )
        self._max_retries = max_retries

    def _make_request(
        self, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """
        Make HTTP request with retry logic and error handling.
        
        Args:
            method: HTTP method (get, post, delete, etc.)
            url: URL path
            **kwargs: Additional arguments to pass to the HTTP client
            
        Returns:
            HTTP response
            
        Raises:
            httpx.HTTPStatusError: If request fails after retries
        """
        @retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.NetworkError, httpx.TimeoutException)),
            reraise=True,
        )
        def _do_request():
            try:
                resp = getattr(self._client, method.lower())(url, **kwargs)
                # Check for rate limiting or server errors
                if resp.status_code == 429:
                    logger.warning(f"Rate limited on {method} {url}, will retry")
                    raise httpx.HTTPStatusError("Rate limited", request=resp.request, response=resp)
                if 500 <= resp.status_code < 600:
                    logger.warning(f"Server error {resp.status_code} on {method} {url}, will retry")
                    raise httpx.HTTPStatusError("Server error", request=resp.request, response=resp)
                return resp
            except (httpx.NetworkError, httpx.TimeoutException) as e:
                logger.warning(f"Network error on {method} {url}: {e}, will retry")
                raise
        
        try:
            return _do_request()
        except RetryError as e:
            logger.error(f"Request failed after {self._max_retries} retries: {method} {url}", exc_info=True)
            raise e.last_attempt.exception()

    def get_account(self) -> dict:
        """Get account information from Alpaca."""
        resp = self._make_request("get", "/v2/account")
        resp.raise_for_status()
        return resp.json()

    def get_positions(self) -> PortfolioState:
        """
        Get current portfolio positions from Alpaca.
        
        Returns:
            PortfolioState with cash and positions
        """
        resp = self._make_request("get", "/v2/positions")
        resp.raise_for_status()
        positions_data = resp.json()

        positions: List[PortfolioPosition] = []
        for item in positions_data:
            positions.append(
                PortfolioPosition(
                    symbol=item["symbol"],
                    quantity=float(item["qty"]),
                    average_price=float(item["avg_entry_price"]),
                )
            )

        account = self.get_account()
        cash = float(account.get("cash", 0.0))
        return PortfolioState(cash=cash, positions=positions)

    def get_position(self, symbol: str) -> Optional[PortfolioPosition]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Stock symbol to query
            
        Returns:
            PortfolioPosition if position exists, None otherwise
        """
        try:
            resp = self._make_request("get", f"/v2/positions/{symbol}")
            resp.raise_for_status()
            item = resp.json()
            return PortfolioPosition(
                symbol=item["symbol"],
                quantity=float(item["qty"]),
                average_price=float(item["avg_entry_price"]),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # No position for this symbol
                return None
            raise

    def get_order_status(self, order_id: str) -> dict:
        """
        Get status of a specific order.
        
        Args:
            order_id: Alpaca order ID
            
        Returns:
            Order status dictionary with fields like status, filled_qty, etc.
        """
        resp = self._make_request("get", f"/v2/orders/{order_id}")
        resp.raise_for_status()
        return resp.json()

    def get_all_orders(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        after: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all orders, optionally filtered by status.
        
        Args:
            status: Filter by order status (open, closed, all)
            limit: Maximum number of orders to return
            after: Return orders submitted after this date (ISO format)
            until: Return orders submitted until this date (ISO format)
            
        Returns:
            List of order dictionaries
        """
        params: Dict[str, Any] = {"limit": limit}
        if status:
            params["status"] = status
        if after:
            params["after"] = after
        if until:
            params["until"] = until
            
        resp = self._make_request("get", "/v2/orders", params=params)
        resp.raise_for_status()
        return resp.json()

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a specific order.
        
        Args:
            order_id: Alpaca order ID to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        try:
            resp = self._make_request("delete", f"/v2/orders/{order_id}")
            resp.raise_for_status()
            logger.info(f"Cancelled order {order_id}", extra={"order_id": order_id})
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"Order {order_id} not found (may already be cancelled)", extra={"order_id": order_id})
                return False
            logger.error(f"Failed to cancel order {order_id}", exc_info=True, extra={"order_id": order_id})
            raise

    def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all open orders.
        
        Returns:
            Dictionary with cancellation results:
            - cancelled_count: Number of orders cancelled
            - total_orders: Total number of open orders
            - errors: List of error messages
        """
        try:
            orders = self.get_all_orders(status="open")
            
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
                order_id = order["id"]
                try:
                    if self.cancel_order(order_id):
                        cancelled_count += 1
                except Exception as e:
                    error_msg = f"Failed to cancel order {order_id}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(f"Failed to cancel order {order_id}", exc_info=True, extra={"order_id": order_id})
            
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
            logger.error("Failed to cancel all orders", exc_info=True, extra={"error": str(e)})
            raise

    def verify_fill(
        self,
        order_id: str,
        timeout_seconds: float = 30.0,
        poll_interval: float = 1.0,
    ) -> Optional[Fill]:
        """
        Verify that an order has been filled by polling its status.
        
        Args:
            order_id: Alpaca order ID to verify
            timeout_seconds: Maximum time to wait for fill
            poll_interval: Time between status checks (seconds)
            
        Returns:
            Fill object if order was filled, None if timeout or order cancelled
        """
        start_time = datetime.utcnow()
        
        while True:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                logger.warning(f"Timeout waiting for order {order_id} to fill", extra={"order_id": order_id, "timeout": timeout_seconds})
                return None
            
            try:
                order_data = self.get_order_status(order_id)
                status = order_data.get("status", "").lower()
                
                if status == "filled":
                    # Order is filled, create Fill object
                    filled_at = order_data.get("filled_at") or order_data.get("updated_at") or order_data.get("created_at")
                    if filled_at:
                        timestamp = datetime.fromisoformat(filled_at.replace("Z", "+00:00"))
                    else:
                        timestamp = datetime.utcnow()
                    
                    return Fill(
                        order_id=order_id,
                        symbol=order_data["symbol"],
                        side=order_data["side"],
                        quantity=float(order_data.get("filled_qty", order_data.get("qty", 0))),
                        price=float(order_data.get("filled_avg_price", order_data.get("limit_price", 0.0))),
                        timestamp=timestamp,
                    )
                elif status in ("canceled", "expired", "rejected"):
                    logger.info(f"Order {order_id} was {status}, not filled", extra={"order_id": order_id, "status": status})
                    return None
                # Otherwise, order is still pending (new, accepted, pending_new, etc.)
                
            except Exception as e:
                logger.error(f"Error checking order status for {order_id}", exc_info=True, extra={"order_id": order_id})
                # Continue polling despite errors
            
            sleep(poll_interval)

    def adjust_limit_price(
        self,
        symbol: str,
        base_price: float,
        adjustment_pct: float,
        side: str,
    ) -> float:
        """
        Adjust a limit price based on market price and adjustment percentage.
        
        Args:
            symbol: Stock symbol (for validation, not currently used)
            base_price: Base price (typically current market price)
            adjustment_pct: Adjustment percentage (e.g., -0.01 for 1% below market)
            side: Order side ("buy" or "sell")
            
        Returns:
            Adjusted limit price
            
        Raises:
            ValueError: If adjustment results in invalid price
        """
        adjusted = base_price * (1 + adjustment_pct)
        
        # Validate price is positive
        if adjusted <= 0:
            raise ValueError(f"Adjusted price {adjusted} is not positive for {symbol}")
        
        # For buys, adjusted price should typically be <= market (negative adjustment)
        # For sells, adjusted price should typically be >= market (positive adjustment)
        # But we allow both directions for flexibility
        
        logger.debug(
            f"Adjusted limit price for {symbol}: {base_price} -> {adjusted} ({adjustment_pct*100:.2f}%)",
            extra={"symbol": symbol, "base_price": base_price, "adjusted": adjusted, "side": side}
        )
        
        return adjusted

    def execute_orders(
        self,
        orders: List[Order],
        verify_fills: bool = True,
        fill_timeout: float = 30.0,
    ) -> List[Fill]:
        """
        Execute orders and optionally verify fills.
        
        Args:
            orders: List of Order objects to execute
            verify_fills: If True, poll for fill confirmation
            fill_timeout: Maximum time to wait for fill verification (seconds)
            
        Returns:
            List of Fill objects representing executed orders
        """
        fills: List[Fill] = []
        
        for order in orders:
            try:
                payload = {
                    "symbol": order.symbol,
                    "qty": order.quantity,
                    "side": order.side,
                    "type": order.type,
                    "time_in_force": "day",
                }
                
                # Handle limit orders with price adjustments
                if order.type == "limit":
                    if order.limit_price is not None:
                        payload["limit_price"] = order.limit_price
                    else:
                        logger.warning(
                            f"Limit order for {order.symbol} has no limit_price, skipping",
                            extra={"symbol": order.symbol, "order": order}
                        )
                        continue
                
                resp = self._make_request("post", "/v2/orders", json=payload)
                resp.raise_for_status()
                data = resp.json()
                
                order_id = data["id"]
                
                # If order is immediately filled, create Fill from response
                if data.get("status", "").lower() == "filled":
                    filled_at = data.get("filled_at") or data.get("created_at")
                    if filled_at:
                        timestamp = datetime.fromisoformat(filled_at.replace("Z", "+00:00"))
                    else:
                        timestamp = datetime.utcnow()
                    
                    fills.append(
                        Fill(
                            order_id=order_id,
                            symbol=data["symbol"],
                            side=data["side"],
                            quantity=float(data.get("filled_qty", data.get("qty", 0))),
                            price=float(data.get("filled_avg_price", data.get("limit_price", 0.0))),
                            timestamp=timestamp,
                        )
                    )
                elif verify_fills:
                    # Poll for fill confirmation
                    fill = self.verify_fill(order_id, timeout_seconds=fill_timeout)
                    if fill:
                        fills.append(fill)
                    else:
                        logger.warning(
                            f"Order {order_id} was not filled within timeout",
                            extra={"order_id": order_id, "symbol": order.symbol, "timeout": fill_timeout}
                        )
                else:
                    # Create Fill from order submission (may not be filled yet)
                    created_at = data.get("created_at")
                    if created_at:
                        timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    else:
                        timestamp = datetime.utcnow()
                    
                    fills.append(
                        Fill(
                            order_id=order_id,
                            symbol=data["symbol"],
                            side=data["side"],
                            quantity=float(data["qty"]),
                            price=float(data.get("filled_avg_price") or data.get("limit_price") or 0.0),
                            timestamp=timestamp,
                        )
                    )
                
                logger.info(
                    f"Submitted order {order_id} for {order.symbol}",
                    extra={"order_id": order_id, "symbol": order.symbol, "side": order.side, "type": order.type}
                )
                
            except Exception as e:
                logger.error(
                    f"Failed to execute order for {order.symbol}",
                    exc_info=True,
                    extra={"symbol": order.symbol, "order": order, "error": str(e)}
                )
                # Continue with other orders even if one fails
                continue

        return fills

    def health_check(self) -> bool:
        """
        Check if the broker connection is healthy.
        
        Returns:
            True if broker is accessible, False otherwise
        """
        try:
            self.get_account()
            return True
        except Exception as e:
            logger.warning(f"Broker health check failed: {e}", extra={"error": str(e)})
            return False

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get detailed health status of the broker.
        
        Returns:
            Dictionary with health information
        """
        try:
            account = self.get_account()
            return {
                "healthy": True,
                "account_status": account.get("status", "unknown"),
                "trading_blocked": account.get("trading_blocked", False),
                "pattern_day_trader": account.get("pattern_day_trader", False),
            }
        except Exception as e:
            return {
                "healthy": False,
                "error": str(e),
            }


_alpaca_instance: AlpacaBroker | None = None


def get_alpaca_broker() -> AlpacaBroker:
    """Get or create the singleton AlpacaBroker instance."""
    global _alpaca_instance
    if _alpaca_instance is None:
        _alpaca_instance = AlpacaBroker()
    return _alpaca_instance
