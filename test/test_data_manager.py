"""
Tests for data manager (caching, refresh, metadata).
"""
import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.trading.data_manager import DataManager, get_data_manager
from app.trading.db_models import DataMetadataDB


class TestDataManager(unittest.TestCase):
    """Test data manager functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create temporary directory for test data
        self.temp_dir = tempfile.mkdtemp()
        self.data_dir = Path(self.temp_dir) / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Mock settings
        with patch("app.trading.data_manager.get_settings") as mock_settings:
            mock_settings.return_value.data.data_dir = str(self.data_dir)
            mock_settings.return_value.data.cache_enabled = True
            mock_settings.return_value.data.cache_ttl_hours = 24
            mock_settings.return_value.data.quality_checks_enabled = True
            mock_settings.return_value.data.file_format = "json"
            
            # Mock Supabase client
            with patch("app.trading.data_manager.get_supabase_client") as mock_client:
                mock_client.return_value = MagicMock()
                self.manager = DataManager()
                self.manager.client = MagicMock()
    
    def test_save_and_load_data(self):
        """Test saving and loading data from cache."""
        symbol = "AAPL"
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        test_data = [
            {
                "timestamp": (start_date + timedelta(days=i)).isoformat(),
                "open": 100.0 + i,
                "high": 101.0 + i,
                "low": 99.0 + i,
                "close": 100.5 + i,
                "volume": 1_000_000,
            }
            for i in range(30)
        ]
        
        # Mock metadata query (no existing metadata) - includes timeframe
        self.manager.client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        
        # Mock data source query
        self.manager.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        self.manager.client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "source-id-1"}]
        
        # Save data with timeframe
        saved = self.manager.save_data(symbol, test_data, start_date, end_date, timeframe="1d")
        self.assertTrue(saved)
        
        # Load data with timeframe
        loaded = self.manager.get_cached_data(symbol, start_date, end_date, timeframe="1d")
        self.assertIsNotNone(loaded)
        self.assertEqual(len(loaded), len(test_data))
    
    def test_get_cached_data_miss(self):
        """Test cache miss scenario."""
        symbol = "MSFT"
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        # No metadata exists (includes timeframe in query)
        self.manager.client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        
        cached = self.manager.get_cached_data(symbol, start_date, end_date, timeframe="1d")
        self.assertIsNone(cached)
    
    def test_get_cached_data_stale(self):
        """Test stale cache scenario."""
        symbol = "GOOGL"
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        # Mock stale metadata (last updated 48 hours ago)
        stale_time = datetime.utcnow() - timedelta(hours=48)
        metadata = DataMetadataDB(
            id="test-id",
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            timeframe="1d",
            file_path=str(self.data_dir / "ohlcv" / symbol / "test.json"),
            file_format="json",
            last_updated=stale_time,
            data_version=1,
            quality_status="pass",
            created_at=stale_time,
            updated_at=stale_time,
        )
        
        self.manager.client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [metadata.dict()]
        
        cached = self.manager.get_cached_data(symbol, start_date, end_date, timeframe="1d")
        # Should return None because cache is stale (TTL is 24 hours)
        self.assertIsNone(cached)
    
    def test_refresh_data(self):
        """Test data refresh functionality."""
        symbols = ["AAPL", "MSFT"]
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        # Mock data loader function
        def mock_loader(syms, start, end):
            return {
                sym: [
                    {
                        "timestamp": start.isoformat(),
                        "open": 100.0,
                        "high": 101.0,
                        "low": 99.0,
                        "close": 100.5,
                        "volume": 1_000_000,
                    }
                ]
                for sym in syms
            }
        
        # Mock no existing cache (includes timeframe in query)
        self.manager.client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        self.manager.client.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        self.manager.client.table.return_value.insert.return_value.execute.return_value.data = [{"id": "source-id-1"}]
        
        refreshed = self.manager.refresh_data(symbols, start_date, end_date, force=False, data_loader_func=mock_loader, timeframe="1d")
        
        self.assertEqual(len(refreshed), len(symbols))
        self.assertIn("AAPL", refreshed)
        self.assertIn("MSFT", refreshed)
    
    def test_get_data_metadata(self):
        """Test metadata retrieval."""
        symbol = "AAPL"
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        # Mock metadata response
        metadata_dict = {
            "id": "test-id",
            "symbol": symbol,
            "start_date": start_date.date().isoformat(),
            "end_date": end_date.date().isoformat(),
            "timeframe": "1d",
            "file_path": "data/ohlcv/AAPL/test.json",
            "file_format": "json",
            "last_updated": datetime.utcnow().isoformat(),
            "data_version": 1,
            "quality_status": "pass",
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        self.manager.client.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.eq.return_value.execute.return_value.data = [metadata_dict]
        
        metadata = self.manager.get_data_metadata(symbol, start_date, end_date, timeframe="1d")
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.symbol, symbol)
        self.assertEqual(metadata.timeframe, "1d")


if __name__ == "__main__":
    unittest.main()

