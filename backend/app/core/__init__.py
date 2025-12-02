"""
Core application modules.
Contains database connections, configuration, and other core functionality.
"""
from .database import db, get_supabase_client, Database

__all__ = ["db", "get_supabase_client", "Database"]

