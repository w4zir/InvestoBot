"""
Health check endpoint.
"""
from fastapi import APIRouter
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/")
async def health_check():
    """
    Basic health check endpoint.
    """
    return {
        "status": "ok",
        "message": "API is running"
    }

