"""
Tests for data quality checker.
"""
import unittest
from datetime import datetime, timedelta

from app.trading.data_quality import DataQualityChecker, DataQualityReport


class TestDataQualityChecker(unittest.TestCase):
    """Test data quality checker functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.checker = DataQualityChecker(gap_threshold_days=3, outlier_threshold_pct=0.10)
    
    def test_validate_good_data(self):
        """Test validation of good quality data."""
        data = [
            {
                "timestamp": datetime(2024, 1, 1) + timedelta(days=i),
                "open": 100.0 + i * 0.1,
                "high": 101.0 + i * 0.1,
                "low": 99.0 + i * 0.1,
                "close": 100.5 + i * 0.1,
                "volume": 1_000_000,
            }
            for i in range(30)
        ]
        
        report = self.checker.validate_ohlcv_data(data)
        self.assertEqual(report.overall_status, "pass")
        self.assertEqual(len(report.issues_found), 0)
    
    def test_validate_missing_values(self):
        """Test detection of missing values."""
        data = [
            {
                "timestamp": datetime(2024, 1, 1),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": None,  # Missing value
                "volume": 1_000_000,
            }
        ]
        
        report = self.checker.validate_ohlcv_data(data)
        self.assertEqual(report.overall_status, "fail")
        self.assertTrue(any("missing_values" in issue["check"] for issue in report.issues_found))
    
    def test_validate_ohlc_relationships(self):
        """Test OHLC relationship validation."""
        data = [
            {
                "timestamp": datetime(2024, 1, 1),
                "open": 100.0,
                "high": 95.0,  # High < Open (invalid)
                "low": 90.0,
                "close": 98.0,
                "volume": 1_000_000,
            }
        ]
        
        report = self.checker.validate_ohlcv_data(data)
        self.assertEqual(report.overall_status, "fail")
        self.assertTrue(any("ohlc_relationships" in issue["check"] for issue in report.issues_found))
        self.assertTrue(len(report.validation_errors) > 0)
    
    def test_validate_duplicate_timestamps(self):
        """Test detection of duplicate timestamps."""
        timestamp = datetime(2024, 1, 1)
        data = [
            {
                "timestamp": timestamp,
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1_000_000,
            },
            {
                "timestamp": timestamp,  # Duplicate
                "open": 100.5,
                "high": 101.5,
                "low": 99.5,
                "close": 101.0,
                "volume": 1_100_000,
            },
        ]
        
        report = self.checker.validate_ohlcv_data(data)
        self.assertEqual(report.overall_status, "warning")
        self.assertTrue(any("duplicate_timestamps" in issue["check"] for issue in report.issues_found))
    
    def test_validate_gaps(self):
        """Test gap detection."""
        data = [
            {
                "timestamp": datetime(2024, 1, 1) + timedelta(days=i),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1_000_000,
            }
            for i in [0, 1, 5, 6]  # Gap between day 1 and day 5
        ]
        
        report = self.checker.validate_ohlcv_data(data)
        # Should detect gap (threshold is 3 days, gap is 4 days)
        self.assertTrue(any("gaps" in issue["check"] for issue in report.issues_found))
        self.assertTrue(len(report.gaps) > 0)
    
    def test_validate_outliers(self):
        """Test outlier detection."""
        data = [
            {
                "timestamp": datetime(2024, 1, 1) + timedelta(days=i),
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.0 + (i * 0.01 if i != 10 else 15.0),  # Large jump at i=10
                "volume": 1_000_000,
            }
            for i in range(20)
        ]
        
        report = self.checker.validate_ohlcv_data(data)
        # Should detect outlier at index 10 (15% change > 10% threshold)
        self.assertTrue(any("outliers" in issue["check"] for issue in report.issues_found))
        self.assertTrue(len(report.outliers) > 0)
    
    def test_check_freshness(self):
        """Test data freshness check."""
        # Fresh data (1 hour old)
        fresh_time = datetime.utcnow() - timedelta(hours=1)
        self.assertTrue(self.checker.check_freshness(fresh_time, max_age_hours=24))
        
        # Stale data (25 hours old)
        stale_time = datetime.utcnow() - timedelta(hours=25)
        self.assertFalse(self.checker.check_freshness(stale_time, max_age_hours=24))
    
    def test_empty_data(self):
        """Test validation of empty data."""
        report = self.checker.validate_ohlcv_data([])
        self.assertEqual(report.overall_status, "fail")
        self.assertTrue(any("empty_data" in issue["check"] for issue in report.issues_found))


if __name__ == "__main__":
    unittest.main()

