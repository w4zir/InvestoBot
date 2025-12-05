"""
Broker manager for handling multiple brokers and failover.

This module provides a centralized broker factory and manager that:
- Supports multiple broker implementations (Alpaca, Interactive Brokers, etc.)
- Implements broker failover when primary broker is unavailable
- Provides health checks and automatic failover
- Maintains singleton instances for each broker type
"""
from typing import Dict, List, Optional, Type, Tuple
from enum import Enum

from app.core.config import get_settings
from app.core.logging import get_logger
from app.trading.broker_interface import BrokerInterface
from app.trading.broker_alpaca import AlpacaBroker

logger = get_logger(__name__)
settings = get_settings()


class BrokerType(str, Enum):
    """Supported broker types."""
    ALPACA = "alpaca"
    # Future: IB = "ib", SCHWAB = "schwab", etc.


# Registry of broker implementations
_BROKER_REGISTRY: Dict[str, Type[BrokerInterface]] = {
    BrokerType.ALPACA: AlpacaBroker,
    # Future: BrokerType.IB: IBBroker,
}


# Singleton instances for each broker type
_broker_instances: Dict[str, BrokerInterface] = {}


class BrokerManager:
    """
    Manager for broker instances with failover support.
    
    This class handles:
    - Creating and caching broker instances
    - Health checking brokers
    - Automatic failover to backup brokers
    - Broker selection based on configuration
    """
    
    def __init__(self):
        """Initialize the broker manager."""
        self._primary_broker_name = settings.broker.broker_primary
        self._failover_enabled = settings.broker.broker_failover_enabled
        self._failover_list = settings.broker.broker_failover_list
        self._current_broker: Optional[BrokerInterface] = None
        self._current_broker_name: Optional[str] = None
        
    def _create_broker(self, broker_name: str) -> Optional[BrokerInterface]:
        """
        Create a broker instance by name.
        
        Args:
            broker_name: Name of the broker (e.g., "alpaca")
            
        Returns:
            BrokerInterface instance or None if broker type not supported
        """
        broker_name_lower = broker_name.lower()
        
        # Check if we have a cached instance
        if broker_name_lower in _broker_instances:
            return _broker_instances[broker_name_lower]
        
        # Check if broker type is registered
        if broker_name_lower not in _BROKER_REGISTRY:
            logger.error(f"Broker type '{broker_name}' is not supported", extra={"broker_name": broker_name})
            return None
        
        # Create broker instance
        try:
            broker_class = _BROKER_REGISTRY[broker_name_lower]
            broker = broker_class()
            _broker_instances[broker_name_lower] = broker
            logger.info(f"Created broker instance: {broker_name}", extra={"broker_name": broker_name})
            return broker
        except Exception as e:
            logger.error(
                f"Failed to create broker '{broker_name}'",
                exc_info=True,
                extra={"broker_name": broker_name, "error": str(e)}
            )
            return None
    
    def _check_broker_health(self, broker: BrokerInterface, broker_name: str) -> bool:
        """
        Check if a broker is healthy.
        
        Args:
            broker: Broker instance to check
            broker_name: Name of the broker for logging
            
        Returns:
            True if broker is healthy, False otherwise
        """
        try:
            is_healthy = broker.health_check()
            if is_healthy:
                logger.debug(f"Broker '{broker_name}' health check passed", extra={"broker_name": broker_name})
            else:
                logger.warning(f"Broker '{broker_name}' health check failed", extra={"broker_name": broker_name})
            return is_healthy
        except Exception as e:
            logger.warning(
                f"Broker '{broker_name}' health check raised exception",
                exc_info=True,
                extra={"broker_name": broker_name, "error": str(e)}
            )
            return False
    
    def _select_broker(self) -> Tuple[Optional[BrokerInterface], Optional[str]]:
        """
        Select the best available broker (primary or failover).
        
        Returns:
            Tuple of (broker_instance, broker_name) or (None, None) if no broker available
        """
        # Try primary broker first
        primary_broker = self._create_broker(self._primary_broker_name)
        if primary_broker and self._check_broker_health(primary_broker, self._primary_broker_name):
            logger.info(
                f"Using primary broker: {self._primary_broker_name}",
                extra={"broker_name": self._primary_broker_name}
            )
            return primary_broker, self._primary_broker_name
        
        # Primary broker failed, try failover if enabled
        if self._failover_enabled and self._failover_list:
            logger.warning(
                f"Primary broker '{self._primary_broker_name}' is unavailable, trying failover brokers",
                extra={"primary": self._primary_broker_name, "failover_list": self._failover_list}
            )
            
            for failover_name in self._failover_list:
                failover_name = failover_name.strip()
                if not failover_name:
                    continue
                
                failover_broker = self._create_broker(failover_name)
                if failover_broker and self._check_broker_health(failover_broker, failover_name):
                    logger.info(
                        f"Using failover broker: {failover_name}",
                        extra={"broker_name": failover_name, "primary": self._primary_broker_name}
                    )
                    return failover_broker, failover_name
                else:
                    logger.warning(
                        f"Failover broker '{failover_name}' is also unavailable",
                        extra={"broker_name": failover_name}
                    )
        
        # All brokers failed
        logger.error(
            f"All brokers are unavailable (primary: {self._primary_broker_name}, failover: {self._failover_list})",
            extra={"primary": self._primary_broker_name, "failover_list": self._failover_list}
        )
        return None, None
    
    def get_broker(self, force_refresh: bool = False) -> BrokerInterface:
        """
        Get the current active broker instance.
        
        This method:
        - Returns cached broker if available and healthy
        - Performs health check and failover if needed
        - Creates new broker instance if needed
        
        Args:
            force_refresh: If True, force a new broker selection (useful after errors)
            
        Returns:
            BrokerInterface instance
            
        Raises:
            RuntimeError: If no broker is available
        """
        # If we have a current broker and not forcing refresh, check if it's still healthy
        if not force_refresh and self._current_broker and self._current_broker_name:
            if self._check_broker_health(self._current_broker, self._current_broker_name):
                return self._current_broker
            else:
                # Current broker is unhealthy, need to select a new one
                logger.warning(
                    f"Current broker '{self._current_broker_name}' became unhealthy, selecting new broker",
                    extra={"broker_name": self._current_broker_name}
                )
        
        # Select a broker (primary or failover)
        broker, broker_name = self._select_broker()
        
        if broker is None:
            raise RuntimeError(
                f"No available broker. Primary: {self._primary_broker_name}, "
                f"Failover enabled: {self._failover_enabled}, Failover list: {self._failover_list}"
            )
        
        self._current_broker = broker
        self._current_broker_name = broker_name
        return broker
    
    def get_broker_by_name(self, broker_name: str) -> Optional[BrokerInterface]:
        """
        Get a specific broker instance by name (bypassing failover logic).
        
        Args:
            broker_name: Name of the broker to get
            
        Returns:
            BrokerInterface instance or None if not available
        """
        return self._create_broker(broker_name)
    
    def get_all_broker_health(self) -> Dict[str, Dict]:
        """
        Get health status for all configured brokers.
        
        Returns:
            Dictionary mapping broker names to their health status
        """
        health_status = {}
        
        # Check primary broker
        primary_broker = self._create_broker(self._primary_broker_name)
        if primary_broker:
            try:
                health_info = primary_broker.get_health_status()
                health_status[self._primary_broker_name] = {
                    **health_info,
                    "is_primary": True,
                    "is_current": self._current_broker_name == self._primary_broker_name,
                }
            except Exception as e:
                health_status[self._primary_broker_name] = {
                    "healthy": False,
                    "error": str(e),
                    "is_primary": True,
                    "is_current": False,
                }
        
        # Check failover brokers
        if self._failover_list:
            for failover_name in self._failover_list:
                failover_name = failover_name.strip()
                if not failover_name:
                    continue
                
                failover_broker = self._create_broker(failover_name)
                if failover_broker:
                    try:
                        health_info = failover_broker.get_health_status()
                        health_status[failover_name] = {
                            **health_info,
                            "is_primary": False,
                            "is_current": self._current_broker_name == failover_name,
                        }
                    except Exception as e:
                        health_status[failover_name] = {
                            "healthy": False,
                            "error": str(e),
                            "is_primary": False,
                            "is_current": False,
                        }
        
        return health_status
    
    def get_current_broker_name(self) -> Optional[str]:
        """
        Get the name of the currently active broker.
        
        Returns:
            Broker name or None if no broker is active
        """
        return self._current_broker_name


# Global broker manager instance
_broker_manager: Optional[BrokerManager] = None


def get_broker_manager() -> BrokerManager:
    """
    Get or create the singleton BrokerManager instance.
    
    Returns:
        BrokerManager instance
    """
    global _broker_manager
    if _broker_manager is None:
        _broker_manager = BrokerManager()
    return _broker_manager


def get_broker(force_refresh: bool = False) -> BrokerInterface:
    """
    Get the current active broker instance.
    
    This is a convenience function that uses the global broker manager.
    It handles broker selection, health checks, and failover automatically.
    
    Args:
        force_refresh: If True, force a new broker selection
        
    Returns:
        BrokerInterface instance
        
    Raises:
        RuntimeError: If no broker is available
    """
    manager = get_broker_manager()
    return manager.get_broker(force_refresh=force_refresh)


def register_broker(broker_type: str, broker_class: Type[BrokerInterface]) -> None:
    """
    Register a new broker type.
    
    This allows adding support for new brokers at runtime.
    
    Args:
        broker_type: Name of the broker type (e.g., "ib")
        broker_class: BrokerInterface subclass
    """
    broker_type_lower = broker_type.lower()
    _BROKER_REGISTRY[broker_type_lower] = broker_class
    logger.info(f"Registered broker type: {broker_type}", extra={"broker_type": broker_type})
