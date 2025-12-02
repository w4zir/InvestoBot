"""
Minimal database module for Supabase connection.
This is a placeholder - customize based on your needs.
"""
import os
import logging
from typing import Optional
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


def get_supabase_client() -> Optional[Client]:
    """Create and return Supabase client instance."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.warning("Supabase credentials not found. Check SUPABASE_URL and SUPABASE_SERVICE_KEY in .env")
        return None
    
    if not supabase_url.startswith("http"):
        logger.error(f"Invalid SUPABASE_URL format: {supabase_url}. Should start with http:// or https://")
        return None
    
    try:
        logger.info(f"Creating Supabase client with URL: {supabase_url[:30]}...")
        client = create_client(supabase_url, supabase_key)
        logger.info("Supabase client created successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {e}", exc_info=True)
        return None


class Database:
    """Database operations wrapper for Supabase."""
    
    def __init__(self):
        self.client = get_supabase_client()
        self._init_error = None
        
        if not self.client:
            try:
                supabase_url = os.getenv("SUPABASE_URL")
                supabase_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_KEY")
                if supabase_url and supabase_key:
                    test_client = create_client(supabase_url, supabase_key)
            except Exception as e:
                self._init_error = str(e)
                logger.error(f"Captured initialization error: {e}", exc_info=True)


# Global database instance
db = Database()
