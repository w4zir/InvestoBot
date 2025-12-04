"""
Data manager for OHLCV market data caching and refresh.

This module provides:
- Data caching to files (hybrid storage: metadata in DB, data in files)
- On-demand and scheduled refresh mechanisms
- Metadata management and versioning
- Integration with data quality checks
"""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.config import get_settings
from app.core.database import get_supabase_client
from app.core.logging import get_logger
from app.trading.data_quality import DataQualityChecker, DataQualityReport
from app.trading.db_models import DataMetadataDB, DataQualityReportDB, DataSourceDB

logger = get_logger(__name__)
settings = get_settings()


class DataManager:
    """Manages OHLCV data caching, refresh, and metadata."""
    
    def __init__(self):
        self.client = get_supabase_client()
        self.quality_checker = DataQualityChecker()
        self.data_dir = Path(settings.data.data_dir)
        self.cache_enabled = settings.data.cache_enabled
        self.cache_ttl_hours = settings.data.cache_ttl_hours
        self.quality_checks_enabled = settings.data.quality_checks_enabled
        self.file_format = settings.data.file_format
        
        # Ensure data directory exists
        self.ohlcv_dir = self.data_dir / "ohlcv"
        self.ohlcv_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cached_data(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[List[Dict]]:
        """
        Load data from cache if available and fresh.
        
        Args:
            symbol: Symbol to load
            start_date: Start date
            end_date: End date
        
        Returns:
            Cached data if available and fresh, None otherwise
        """
        if not self.cache_enabled:
            return None
        
        try:
            metadata = self.get_data_metadata(symbol, start_date, end_date)
            if not metadata:
                return None
            
            # Check if cache is fresh
            if not self.quality_checker.check_freshness(metadata.last_updated, self.cache_ttl_hours):
                logger.debug(f"Cache for {symbol} is stale (last updated: {metadata.last_updated})")
                return None
            
            # Load from file
            file_path = Path(metadata.file_path)
            if not file_path.exists():
                logger.warning(f"Cached file not found: {file_path}")
                return None
            
            return self._load_from_file(file_path, metadata.file_format)
        except Exception as e:
            logger.warning(f"Failed to load cached data for {symbol}: {e}", exc_info=True)
            return None
    
    def save_data(
        self,
        symbol: str,
        data: List[Dict],
        start_date: datetime,
        end_date: datetime,
        data_source: str = "yahoo",
    ) -> bool:
        """
        Save data to cache and update metadata.
        
        Args:
            symbol: Symbol
            data: OHLCV data to save
            start_date: Start date
            end_date: End date
            data_source: Data source name
        
        Returns:
            True if successful, False otherwise
        """
        if not self.cache_enabled or not data:
            return False
        
        try:
            # Run quality checks if enabled
            quality_report: Optional[DataQualityReport] = None
            if self.quality_checks_enabled:
                quality_report = self.quality_checker.validate_ohlcv_data(data)
                logger.info(
                    f"Quality check for {symbol}: {quality_report.overall_status}",
                    extra={
                        "symbol": symbol,
                        "status": quality_report.overall_status,
                        "issues": len(quality_report.issues_found),
                    }
                )
            
            # Save to file
            file_path = self._get_file_path(symbol, start_date, end_date)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            saved = self._save_to_file(file_path, data, self.file_format)
            if not saved:
                return False
            
            # Calculate checksum
            checksum = self._calculate_checksum(data)
            
            # Get or create data source
            source_id = self._get_data_source_id(data_source)
            
            # Get existing metadata to check version
            existing_metadata = self.get_data_metadata(symbol, start_date, end_date)
            new_version = (existing_metadata.data_version + 1) if existing_metadata else 1
            
            # Update metadata
            metadata_data = {
                "symbol": symbol,
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "data_source_id": str(source_id) if source_id else None,
                "file_path": str(file_path),
                "file_format": self.file_format,
                "file_size_bytes": file_path.stat().st_size if file_path.exists() else None,
                "row_count": len(data),
                "last_updated": datetime.utcnow().isoformat(),
                "data_version": new_version,
                "checksum": checksum,
                "quality_status": quality_report.overall_status if quality_report else "pending",
                "updated_at": datetime.utcnow().isoformat(),
            }
            
            # Save quality report if available
            quality_report_id = None
            if quality_report and self.client:
                quality_report_id = self._save_quality_report(metadata_data.get("id"), quality_report)
                if quality_report_id:
                    metadata_data["quality_report_id"] = str(quality_report_id)
            
            # Upsert metadata
            if self.client:
                # Check if exists
                existing = self.client.table("data_metadata").select("id").eq("symbol", symbol).eq("start_date", start_date.date().isoformat()).eq("end_date", end_date.date().isoformat()).execute()
                
                if existing.data:
                    # Update existing
                    metadata_id = existing.data[0]["id"]
                    self.client.table("data_metadata").update(metadata_data).eq("id", metadata_id).execute()
                else:
                    # Insert new
                    metadata_data["created_at"] = datetime.utcnow().isoformat()
                    self.client.table("data_metadata").insert(metadata_data).execute()
            
            logger.info(
                f"Saved data for {symbol} to cache",
                extra={
                    "symbol": symbol,
                    "rows": len(data),
                    "file_path": str(file_path),
                    "version": new_version,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to save data for {symbol}: {e}", exc_info=True)
            return False
    
    def refresh_data(
        self,
        symbols: List[str],
        start_date: datetime,
        end_date: datetime,
        force: bool = False,
        data_loader_func=None,
    ) -> Dict[str, List[Dict]]:
        """
        Refresh data for symbols (fetch from source if needed).
        
        Args:
            symbols: List of symbols to refresh
            start_date: Start date
            end_date: End date
            force: Force refresh even if cache is fresh
            data_loader_func: Function to load data from source (takes symbols, start, end)
        
        Returns:
            Dictionary mapping symbol to data
        """
        if not data_loader_func:
            logger.error("data_loader_func is required for refresh")
            return {}
        
        refreshed_data = {}
        
        for symbol in symbols:
            # Check cache first
            if not force:
                cached = self.get_cached_data(symbol, start_date, end_date)
                if cached:
                    logger.debug(f"Using cached data for {symbol}")
                    refreshed_data[symbol] = cached
                    continue
            
            # Fetch from source
            logger.info(f"Refreshing data for {symbol} from source")
            try:
                source_data = data_loader_func([symbol], start_date, end_date)
                if symbol in source_data and source_data[symbol]:
                    # Save to cache
                    self.save_data(symbol, source_data[symbol], start_date, end_date)
                    refreshed_data[symbol] = source_data[symbol]
            except Exception as e:
                logger.error(f"Failed to refresh data for {symbol}: {e}", exc_info=True)
        
        return refreshed_data
    
    def get_data_metadata(
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
    ) -> Optional[DataMetadataDB]:
        """
        Get metadata for a dataset.
        
        Args:
            symbol: Symbol
            start_date: Start date
            end_date: End date
        
        Returns:
            DataMetadataDB if found, None otherwise
        """
        if not self.client:
            return None
        
        try:
            response = (
                self.client.table("data_metadata")
                .select("*")
                .eq("symbol", symbol)
                .eq("start_date", start_date.date().isoformat())
                .eq("end_date", end_date.date().isoformat())
                .execute()
            )
            
            if response.data:
                return DataMetadataDB(**response.data[0])
            return None
        except Exception as e:
            logger.warning(f"Failed to get metadata for {symbol}: {e}", exc_info=True)
            return None
    
    def _get_file_path(self, symbol: str, start_date: datetime, end_date: datetime) -> Path:
        """Get file path for cached data."""
        symbol_dir = self.ohlcv_dir / symbol.upper()
        filename = f"{start_date.date().isoformat()}_{end_date.date().isoformat()}.{self.file_format}"
        return symbol_dir / filename
    
    def _save_to_file(self, file_path: Path, data: List[Dict], file_format: str) -> bool:
        """Save data to file."""
        try:
            if file_format == "json":
                with open(file_path, "w") as f:
                    json.dump(data, f, default=str, indent=2)
            elif file_format == "parquet":
                # Parquet support would require pandas/pyarrow
                # For now, fall back to JSON
                logger.warning("Parquet format not yet implemented, using JSON")
                file_path = file_path.with_suffix(".json")
                with open(file_path, "w") as f:
                    json.dump(data, f, default=str, indent=2)
            else:
                logger.error(f"Unsupported file format: {file_format}")
                return False
            return True
        except Exception as e:
            logger.error(f"Failed to save file {file_path}: {e}", exc_info=True)
            return False
    
    def _load_from_file(self, file_path: Path, file_format: str) -> Optional[List[Dict]]:
        """Load data from file."""
        try:
            if not file_path.exists():
                return None
            
            if file_format == "json" or file_path.suffix == ".json":
                with open(file_path, "r") as f:
                    return json.load(f)
            else:
                logger.warning(f"Unsupported file format for loading: {file_format}")
                return None
        except Exception as e:
            logger.error(f"Failed to load file {file_path}: {e}", exc_info=True)
            return None
    
    def _calculate_checksum(self, data: List[Dict]) -> str:
        """Calculate checksum for data."""
        data_str = json.dumps(data, default=str, sort_keys=True)
        return hashlib.md5(data_str.encode()).hexdigest()
    
    def _get_data_source_id(self, source_name: str) -> Optional[str]:
        """Get or create data source ID."""
        if not self.client:
            return None
        
        try:
            # Try to get existing
            response = (
                self.client.table("data_sources")
                .select("id")
                .eq("source_name", source_name)
                .execute()
            )
            
            if response.data:
                return str(response.data[0]["id"])
            
            # Create new if doesn't exist
            source_data = {
                "source_name": source_name,
                "source_type": "api" if source_name == "yahoo" else "synthetic",
                "config": {},
                "is_active": True,
            }
            response = self.client.table("data_sources").insert(source_data).execute()
            if response.data:
                return str(response.data[0]["id"])
            return None
        except Exception as e:
            logger.warning(f"Failed to get data source ID for {source_name}: {e}", exc_info=True)
            return None
    
    def _save_quality_report(
        self,
        metadata_id: Optional[str],
        quality_report: DataQualityReport,
    ) -> Optional[str]:
        """Save quality report to database."""
        if not self.client or not metadata_id:
            return None
        
        try:
            report_data = {
                "data_metadata_id": metadata_id,
                "overall_status": quality_report.overall_status,
                "checks_performed": quality_report.checks_performed,
                "issues_found": quality_report.issues_found,
                "gap_count": len(quality_report.gaps),
                "outlier_count": len(quality_report.outliers),
                "validation_errors": quality_report.validation_errors,
                "recommendations": quality_report.recommendations,
                "checked_at": datetime.utcnow().isoformat(),
            }
            
            response = self.client.table("data_quality_reports").insert(report_data).execute()
            if response.data:
                return str(response.data[0]["id"])
            return None
        except Exception as e:
            logger.warning(f"Failed to save quality report: {e}", exc_info=True)
            return None


# Global instance
_data_manager: Optional[DataManager] = None


def get_data_manager() -> DataManager:
    """Get the global data manager instance."""
    global _data_manager
    if _data_manager is None:
        _data_manager = DataManager()
    return _data_manager


def scheduled_refresh():
    """
    Scheduled data refresh function.
    Can be called by cron job or scheduler.
    Refreshes data for default universe with default lookback period.
    """
    from datetime import datetime, timedelta
    
    logger.info("Starting scheduled data refresh")
    settings = get_settings()
    data_manager = get_data_manager()
    
    # Get default universe and lookback
    symbols = settings.data.default_universe
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=settings.data.default_lookback_days)
    
    # Define data loader
    from app.trading.market_data import load_data
    
    def _load_from_source(symbols_list: List[str], start_dt: datetime, end_dt: datetime) -> Dict[str, List[Dict]]:
        return load_data(symbols_list, start_dt, end_dt, use_cache=False)
    
    # Refresh data
    refreshed = data_manager.refresh_data(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        force=False,  # Use cache if fresh
        data_loader_func=_load_from_source,
    )
    
    logger.info(
        f"Scheduled refresh completed",
        extra={
            "symbols": symbols,
            "refreshed_count": len(refreshed),
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }
    )
    
    return refreshed

