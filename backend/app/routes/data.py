"""
API routes for data management.

Provides endpoints for:
- Data refresh (on-demand)
- Data metadata queries
- Data quality reports
- Data validation
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.core.logging import get_logger
from app.trading.data_manager import get_data_manager
from app.trading.data_quality import DataQualityChecker
from app.trading.db_models import DataMetadataDB, DataQualityReportDB
from app.trading.market_data import load_data

logger = get_logger(__name__)
router = APIRouter()


class RefreshDataRequest(BaseModel):
    """Request model for data refresh."""
    
    symbols: List[str]
    start_date: str  # ISO format date
    end_date: str  # ISO format date
    force: bool = False  # Force refresh even if cache is fresh


class RefreshDataResponse(BaseModel):
    """Response model for data refresh."""
    
    refreshed: List[str]
    cached: List[str]
    failed: List[str]
    message: str


@router.post("/refresh", response_model=RefreshDataResponse)
async def refresh_data(request: RefreshDataRequest):
    """
    Trigger on-demand data refresh for specified symbols and date range.
    
    Args:
        request: Refresh request with symbols and date range
    
    Returns:
        Refresh response with status for each symbol
    """
    try:
        start_date = datetime.fromisoformat(request.start_date.replace("Z", "+00:00"))
        end_date = datetime.fromisoformat(request.end_date.replace("Z", "+00:00"))
        
        data_manager = get_data_manager()
        
        refreshed = []
        cached = []
        failed = []
        
        for symbol in request.symbols:
            try:
                # Check cache first
                if not request.force:
                    cached_data = data_manager.get_cached_data(symbol, start_date, end_date)
                    if cached_data:
                        cached.append(symbol)
                        continue
                
                # Load from source
                source_data = load_data([symbol], start_date, end_date, use_cache=False)
                if symbol in source_data and source_data[symbol]:
                    # Save to cache
                    data_manager.save_data(symbol, source_data[symbol], start_date, end_date)
                    refreshed.append(symbol)
                else:
                    failed.append(symbol)
            except Exception as e:
                logger.error(f"Failed to refresh data for {symbol}: {e}", exc_info=True)
                failed.append(symbol)
        
        message = f"Refreshed {len(refreshed)}, used cache for {len(cached)}, failed {len(failed)}"
        
        return RefreshDataResponse(
            refreshed=refreshed,
            cached=cached,
            failed=failed,
            message=message,
        )
    except Exception as e:
        logger.error(f"Data refresh failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Data refresh failed: {str(e)}")


@router.get("/metadata")
async def get_metadata(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    start_date: Optional[str] = Query(None, description="Filter by start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by end date (ISO format)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
):
    """
    Query data metadata.
    
    Args:
        symbol: Optional symbol filter
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Maximum number of results
    
    Returns:
        List of data metadata entries
    """
    try:
        data_manager = get_data_manager()
        
        if not data_manager.client:
            raise HTTPException(status_code=503, detail="Database not available")
        
        query = data_manager.client.table("data_metadata").select("*")
        
        if symbol:
            query = query.eq("symbol", symbol)
        if start_date:
            query = query.gte("start_date", start_date)
        if end_date:
            query = query.lte("end_date", end_date)
        
        query = query.order("last_updated", desc=True).limit(limit)
        
        response = query.execute()
        
        return [DataMetadataDB(**row) for row in response.data]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")


@router.get("/quality/{symbol}")
async def get_quality_report(
    symbol: str,
    start_date: Optional[str] = Query(None, description="Start date (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date (ISO format)"),
):
    """
    Get quality report for a specific symbol and date range.
    
    Args:
        symbol: Symbol to check
        start_date: Optional start date
        end_date: Optional end date
    
    Returns:
        Quality report
    """
    try:
        data_manager = get_data_manager()
        
        if not data_manager.client:
            raise HTTPException(status_code=503, detail="Database not available")
        
        # Get metadata
        if start_date and end_date:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
            metadata = data_manager.get_data_metadata(symbol, start_dt, end_dt)
        else:
            # Get latest metadata for symbol
            response = (
                data_manager.client.table("data_metadata")
                .select("*")
                .eq("symbol", symbol)
                .order("last_updated", desc=True)
                .limit(1)
                .execute()
            )
            if not response.data:
                raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
            metadata = DataMetadataDB(**response.data[0])
        
        if not metadata or not metadata.quality_report_id:
            raise HTTPException(status_code=404, detail="No quality report found")
        
        # Get quality report
        response = (
            data_manager.client.table("data_quality_reports")
            .select("*")
            .eq("id", metadata.quality_report_id)
            .execute()
        )
        
        if not response.data:
            raise HTTPException(status_code=404, detail="Quality report not found")
        
        return DataQualityReportDB(**response.data[0])
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get quality report: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get quality report: {str(e)}")


@router.post("/validate")
async def validate_data(
    symbol: str,
    start_date: str,
    end_date: str,
):
    """
    Validate a specific dataset and return quality report.
    
    Args:
        symbol: Symbol to validate
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
    
    Returns:
        Quality report
    """
    try:
        start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        
        # Load data
        data = load_data([symbol], start_dt, end_dt, use_cache=True)
        
        if symbol not in data or not data[symbol]:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Run quality checks
        quality_checker = DataQualityChecker()
        report = quality_checker.validate_ohlcv_data(data[symbol])
        
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")

