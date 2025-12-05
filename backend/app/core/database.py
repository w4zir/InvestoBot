"""
Database module for Supabase PostgreSQL connection.
Provides client management, JSONB helpers, and error handling.
"""
import json
import os
import logging
import base64
from functools import wraps
from typing import Any, Dict, Optional
from supabase import create_client, Client
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
if not env_path.exists():
    env_path = Path(__file__).parent.parent / ".env"

if env_path.exists():
    load_dotenv(env_path)
    logger.info(f"Loaded environment from {env_path}")
else:
    logger.warning(f".env file not found. Expected at: {env_path}")


def retry_on_failure(max_retries: int = 3, delay: float = 1.0):
    """
    Decorator to retry database operations on failure.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"Database operation failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying...")
                        import time
                        time.sleep(delay * (attempt + 1))  # Exponential backoff
                    else:
                        logger.error(f"Database operation failed after {max_retries} attempts: {e}", exc_info=True)
            raise last_exception
        return wrapper
    return decorator


def _detect_key_type(key: str) -> str:
    """
    Detect if Supabase key is service_role or anon based on JWT payload.
    
    Args:
        key: Supabase API key (JWT token)
        
    Returns:
        'service_role' or 'anon'
    """
    try:
        # JWT tokens have 3 parts separated by dots: header.payload.signature
        parts = key.split('.')
        if len(parts) != 3:
            return 'unknown'
        
        # Decode payload (second part)
        payload = parts[1]
        # Add padding if needed for base64 decoding
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        claims = json.loads(decoded)
        
        # Check the 'role' claim
        role = claims.get('role', '')
        if role == 'service_role':
            return 'service_role'
        elif role == 'anon' or role == 'authenticated':
            return 'anon'
        else:
            return 'unknown'
    except Exception:
        # If we can't decode, assume unknown
        return 'unknown'


def get_supabase_client() -> Optional[Client]:
    """
    Create and return Supabase client instance.
    
    Prefers SUPABASE_SERVICE_KEY over SUPABASE_KEY (anon key).
    Logs which key type is being used and warns if anon key is used.
    
    Returns:
        Supabase Client instance or None if connection fails
    """
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    anon_key = os.getenv("SUPABASE_KEY")
    
    # Prefer service_role key, fallback to anon key
    supabase_key = service_key or anon_key
    key_source = "SUPABASE_SERVICE_KEY" if service_key else "SUPABASE_KEY"
    
    if not supabase_url or not supabase_key:
        logger.warning(
            "Supabase credentials not found. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env. "
            "SUPABASE_SERVICE_KEY is required for backend database operations."
        )
        return None
    
    if not supabase_url.startswith("http"):
        logger.error(f"Invalid SUPABASE_URL format: {supabase_url}. Should start with http:// or https://")
        return None
    
    # Detect key type
    key_type = _detect_key_type(supabase_key)
    
    # Log key type being used
    if key_type == 'service_role':
        logger.info(f"Using Supabase service_role key (from {key_source}) - RLS bypassed")
    elif key_type == 'anon':
        logger.warning(
            f"Using Supabase anon key (from {key_source}) - RLS policies required! "
            "Backend operations may fail with permission errors. "
            "Set SUPABASE_SERVICE_KEY in backend/.env for proper access. "
            "If you must use anon key, ensure RLS policies are configured (see migration 006_rls_policies.sql)."
        )
    else:
        logger.warning(f"Could not determine Supabase key type - using key from {key_source}")
    
    try:
        logger.info(f"Creating Supabase client with URL: {supabase_url[:30]}...")
        client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client created successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}", exc_info=True)
        return None


def serialize_jsonb(data: Any) -> Dict[str, Any]:
    """
    Serialize data for JSONB storage in PostgreSQL.
    
    Args:
        data: Data to serialize (dict, list, or Pydantic model)
    
    Returns:
        Dictionary ready for JSONB storage
    """
    if isinstance(data, dict):
        return data
    elif isinstance(data, list):
        return data
    elif hasattr(data, "model_dump"):
        # Pydantic v2
        return data.model_dump(mode="json")
    elif hasattr(data, "dict"):
        # Pydantic v1
        return data.dict()
    elif hasattr(data, "__dict__"):
        return data.__dict__
    else:
        # Try JSON serialization
        try:
            return json.loads(json.dumps(data, default=str))
        except (TypeError, ValueError):
            return {"_raw": str(data)}


def deserialize_jsonb(data: Any) -> Any:
    """
    Deserialize JSONB data from PostgreSQL.
    
    Args:
        data: JSONB data from database
    
    Returns:
        Deserialized data
    """
    if isinstance(data, str):
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    return data


class Database:
    """
    Database operations wrapper for Supabase PostgreSQL.
    Provides connection management and helper methods.
    """
    
    def __init__(self):
        self.client = get_supabase_client()
        self._init_error = None
        self._key_type = None
        
        if not self.client:
            try:
                supabase_url = os.getenv("SUPABASE_URL")
                service_key = os.getenv("SUPABASE_SERVICE_KEY")
                anon_key = os.getenv("SUPABASE_KEY")
                supabase_key = service_key or anon_key
                
                if supabase_url and supabase_key:
                    self._key_type = _detect_key_type(supabase_key)
                    test_client = create_client(supabase_url, supabase_key)
            except Exception as e:
                self._init_error = str(e)
                logger.error(f"Captured initialization error: {e}", exc_info=True)
    
    def is_connected(self) -> bool:
        """Check if database connection is available."""
        return self.client is not None
    
    @retry_on_failure(max_retries=3)
    def execute_query(self, table: str, operation: str, data: Any = None) -> Optional[Any]:
        """
        Execute a database query with retry logic.
        
        Args:
            table: Table name
            operation: Operation type ('insert', 'update', 'select', 'delete')
            data: Data for the operation
        
        Returns:
            Query result or None if failed
        """
        if not self.client:
            logger.warning("Database client not available")
            return None
        
        try:
            table_ref = self.client.table(table)
            
            if operation == "insert":
                return table_ref.insert(data).execute()
            elif operation == "update":
                return table_ref.update(data).execute()
            elif operation == "upsert":
                return table_ref.upsert(data).execute()
            elif operation == "select":
                return table_ref.select("*").execute()
            elif operation == "delete":
                return table_ref.delete().execute()
            else:
                logger.error(f"Unknown operation: {operation}")
                return None
        except Exception as e:
            logger.error(f"Database query failed: {e}", exc_info=True)
            raise


# Global database instance
db = Database()
