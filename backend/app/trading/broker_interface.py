"""
Broker interface defining the contract for all broker implementations.

This abstract base class ensures all brokers implement a consistent API
for order execution, position monitoring, and account management.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.trading.models import Fill, Order, PortfolioPosition, PortfolioState


class BrokerInterface(ABC):
    """
    Abstract base class defining the broker contract.
    
    All broker implementations must inherit from this class and implement
    all abstract methods to ensure consistent behavior across different brokers.
    """

    @abstractmethod
    def get_account(self) -> dict:
        """
        Get account information from the broker.
        
        Returns:
            Dictionary containing account information (balance, status, etc.)
            
        Raises:
            Exception: If account information cannot be retrieved
        """
        pass

    @abstractmethod
    def get_positions(self) -> PortfolioState:
        """
        Get current portfolio positions from the broker.
        
        Returns:
            PortfolioState with cash and positions
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[PortfolioPosition]:
        """
        Get position for a specific symbol.
        
        Args:
            symbol: Stock symbol to query
            
        Returns:
            PortfolioPosition if position exists, None otherwise
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> dict:
        """
        Get status of a specific order.
        
        Args:
            order_id: Broker order ID
            
        Returns:
            Order status dictionary with fields like status, filled_qty, etc.
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel a specific order.
        
        Args:
            order_id: Broker order ID to cancel
            
        Returns:
            True if cancellation was successful, False otherwise
        """
        pass

    @abstractmethod
    def cancel_all_orders(self) -> Dict[str, Any]:
        """
        Cancel all open orders.
        
        Returns:
            Dictionary with cancellation results:
            - cancelled_count: Number of orders cancelled
            - total_orders: Total number of open orders
            - errors: List of error messages
        """
        pass

    @abstractmethod
    def verify_fill(
        self,
        order_id: str,
        timeout_seconds: float = 30.0,
        poll_interval: float = 1.0,
    ) -> Optional[Fill]:
        """
        Verify that an order has been filled by polling its status.
        
        Args:
            order_id: Broker order ID to verify
            timeout_seconds: Maximum time to wait for fill
            poll_interval: Time between status checks (seconds)
            
        Returns:
            Fill object if order was filled, None if timeout or order cancelled
        """
        pass

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check if the broker connection is healthy.
        
        Returns:
            True if broker is accessible, False otherwise
        """
        pass

    @abstractmethod
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get detailed health status of the broker.
        
        Returns:
            Dictionary with health information including:
            - healthy: Boolean indicating if broker is healthy
            - Additional broker-specific health metrics
        """
        pass

    # Optional methods that some brokers may implement
    def get_all_orders(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        after: Optional[str] = None,
        until: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all orders, optionally filtered by status.
        
        This is an optional method - not all brokers may support all parameters.
        Default implementation raises NotImplementedError.
        
        Args:
            status: Filter by order status (open, closed, all)
            limit: Maximum number of orders to return
            after: Return orders submitted after this date (ISO format)
            until: Return orders submitted until this date (ISO format)
            
        Returns:
            List of order dictionaries
        """
        raise NotImplementedError("get_all_orders not implemented for this broker")

    def adjust_limit_price(
        self,
        symbol: str,
        base_price: float,
        adjustment_pct: float,
        side: str,
    ) -> float:
        """
        Adjust a limit price based on market price and adjustment percentage.
        
        This is an optional method for brokers that support price adjustments.
        Default implementation raises NotImplementedError.
        
        Args:
            symbol: Stock symbol
            base_price: Base price (typically current market price)
            adjustment_pct: Adjustment percentage (e.g., -0.01 for 1% below market)
            side: Order side ("buy" or "sell")
            
        Returns:
            Adjusted limit price
        """
        raise NotImplementedError("adjust_limit_price not implemented for this broker")

