"""
Data quality validation for OHLCV market data.

This module provides functions to validate OHLCV data quality, including:
- Gap detection (missing dates)
- Outlier detection (price/volume anomalies)
- OHLC relationship validation
- Missing value detection
- Duplicate timestamp detection
- Data freshness checks
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


class DataQualityReport:
    """Report containing quality check results."""
    
    def __init__(self):
        self.overall_status: str = "pass"  # 'pass', 'warning', 'fail'
        self.checks_performed: List[str] = []
        self.issues_found: List[Dict[str, Any]] = []
        self.gaps: List[Dict[str, Any]] = []
        self.outliers: List[Dict[str, Any]] = []
        self.validation_errors: List[str] = []
        self.recommendations: List[str] = []
    
    def add_issue(self, severity: str, check_name: str, description: str, details: Optional[Dict[str, Any]] = None):
        """Add an issue to the report."""
        issue = {
            "severity": severity,  # 'error', 'warning', 'info'
            "check": check_name,
            "description": description,
            "details": details or {},
        }
        self.issues_found.append(issue)
        
        # Update overall status (fail > warning > pass)
        if severity == "error":
            self.overall_status = "fail"
        elif severity == "warning" and self.overall_status == "pass":
            self.overall_status = "warning"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert report to dictionary."""
        return {
            "overall_status": self.overall_status,
            "checks_performed": self.checks_performed,
            "issues_found": self.issues_found,
            "gap_count": len(self.gaps),
            "outlier_count": len(self.outliers),
            "validation_errors": self.validation_errors,
            "recommendations": self.recommendations,
        }


class DataQualityChecker:
    """Quality checker for OHLCV data."""
    
    def __init__(self, gap_threshold_days: int = 3, outlier_threshold_pct: float = 0.10):
        """
        Initialize quality checker.
        
        Args:
            gap_threshold_days: Maximum allowed gap in days before flagging
            outlier_threshold_pct: Percentage change threshold for outlier detection
        """
        self.gap_threshold_days = gap_threshold_days
        self.outlier_threshold_pct = outlier_threshold_pct
    
    def validate_ohlcv_data(self, data: List[Dict]) -> DataQualityReport:
        """
        Run all quality checks on OHLCV data.
        
        Args:
            data: List of OHLCV bars (dicts with timestamp, open, high, low, close, volume)
        
        Returns:
            DataQualityReport with all check results
        """
        report = DataQualityReport()
        
        if not data:
            report.add_issue("error", "empty_data", "Data is empty")
            return report
        
        # Run all checks
        self._check_missing_values(data, report)
        self._check_ohlc_relationships(data, report)
        self._check_duplicate_timestamps(data, report)
        self._check_gaps(data, report)
        self._check_outliers(data, report)
        
        # Generate recommendations
        self._generate_recommendations(report)
        
        return report
    
    def _check_missing_values(self, data: List[Dict], report: DataQualityReport):
        """Check for missing/null values in required fields."""
        report.checks_performed.append("missing_values")
        
        required_fields = ["timestamp", "open", "high", "low", "close", "volume"]
        missing_count = 0
        
        for i, bar in enumerate(data):
            for field in required_fields:
                if field not in bar or bar[field] is None:
                    missing_count += 1
                    report.add_issue(
                        "error",
                        "missing_values",
                        f"Missing {field} at index {i}",
                        {"index": i, "field": field}
                    )
        
        if missing_count == 0:
            logger.debug("No missing values found")
    
    def _check_ohlc_relationships(self, data: List[Dict], report: DataQualityReport):
        """Validate OHLC price relationships."""
        report.checks_performed.append("ohlc_relationships")
        
        errors = []
        for i, bar in enumerate(data):
            try:
                open_price = float(bar.get("open", 0))
                high_price = float(bar.get("high", 0))
                low_price = float(bar.get("low", 0))
                close_price = float(bar.get("close", 0))
                
                # Check relationships
                if high_price < low_price:
                    errors.append(f"Index {i}: high ({high_price}) < low ({low_price})")
                    report.add_issue(
                        "error",
                        "ohlc_relationships",
                        f"High < Low at index {i}",
                        {"index": i, "high": high_price, "low": low_price}
                    )
                
                if high_price < open_price:
                    errors.append(f"Index {i}: high ({high_price}) < open ({open_price})")
                    report.add_issue(
                        "error",
                        "ohlc_relationships",
                        f"High < Open at index {i}",
                        {"index": i, "high": high_price, "open": open_price}
                    )
                
                if high_price < close_price:
                    errors.append(f"Index {i}: high ({high_price}) < close ({close_price})")
                    report.add_issue(
                        "error",
                        "ohlc_relationships",
                        f"High < Close at index {i}",
                        {"index": i, "high": high_price, "close": close_price}
                    )
                
                if low_price > open_price:
                    errors.append(f"Index {i}: low ({low_price}) > open ({open_price})")
                    report.add_issue(
                        "error",
                        "ohlc_relationships",
                        f"Low > Open at index {i}",
                        {"index": i, "low": low_price, "open": open_price}
                    )
                
                if low_price > close_price:
                    errors.append(f"Index {i}: low ({low_price}) > close ({close_price})")
                    report.add_issue(
                        "error",
                        "ohlc_relationships",
                        f"Low > Close at index {i}",
                        {"index": i, "low": low_price, "close": close_price}
                    )
            except (ValueError, TypeError) as e:
                report.add_issue(
                    "error",
                    "ohlc_relationships",
                    f"Invalid price values at index {i}: {e}",
                    {"index": i, "error": str(e)}
                )
        
        report.validation_errors = errors
        if not errors:
            logger.debug("OHLC relationships validated successfully")
    
    def _check_duplicate_timestamps(self, data: List[Dict], report: DataQualityReport):
        """Check for duplicate timestamps."""
        report.checks_performed.append("duplicate_timestamps")
        
        seen_timestamps = {}
        duplicates = []
        
        for i, bar in enumerate(data):
            timestamp = bar.get("timestamp")
            if timestamp:
                # Convert to string for comparison
                ts_key = str(timestamp)
                if ts_key in seen_timestamps:
                    duplicates.append({
                        "index": i,
                        "timestamp": timestamp,
                        "previous_index": seen_timestamps[ts_key],
                    })
                    report.add_issue(
                        "warning",
                        "duplicate_timestamps",
                        f"Duplicate timestamp at index {i}",
                        {"index": i, "timestamp": timestamp}
                    )
                else:
                    seen_timestamps[ts_key] = i
        
        if not duplicates:
            logger.debug("No duplicate timestamps found")
    
    def _check_gaps(self, data: List[Dict], report: DataQualityReport):
        """Check for gaps in time series (missing dates)."""
        report.checks_performed.append("gaps")
        
        if len(data) < 2:
            return
        
        gaps = []
        sorted_data = sorted(data, key=lambda x: self._get_timestamp(x))
        
        for i in range(len(sorted_data) - 1):
            current_ts = self._get_timestamp(sorted_data[i])
            next_ts = self._get_timestamp(sorted_data[i + 1])
            
            if isinstance(current_ts, datetime) and isinstance(next_ts, datetime):
                gap_days = (next_ts - current_ts).days
                if gap_days > self.gap_threshold_days:
                    gaps.append({
                        "start": current_ts,
                        "end": next_ts,
                        "gap_days": gap_days,
                    })
                    report.add_issue(
                        "warning",
                        "gaps",
                        f"Gap of {gap_days} days between {current_ts} and {next_ts}",
                        {"start": current_ts.isoformat(), "end": next_ts.isoformat(), "gap_days": gap_days}
                    )
        
        report.gaps = gaps
        if not gaps:
            logger.debug("No significant gaps found")
    
    def _check_outliers(self, data: List[Dict], report: DataQualityReport):
        """Check for price and volume outliers."""
        report.checks_performed.append("outliers")
        
        if len(data) < 2:
            return
        
        outliers = []
        sorted_data = sorted(data, key=lambda x: self._get_timestamp(x))
        
        for i in range(1, len(sorted_data)):
            prev_bar = sorted_data[i - 1]
            curr_bar = sorted_data[i]
            
            try:
                prev_close = float(prev_bar.get("close", 0))
                curr_close = float(curr_bar.get("close", 0))
                
                if prev_close > 0:
                    pct_change = abs((curr_close - prev_close) / prev_close)
                    if pct_change > self.outlier_threshold_pct:
                        outliers.append({
                            "index": i,
                            "timestamp": self._get_timestamp(curr_bar),
                            "pct_change": pct_change,
                            "prev_close": prev_close,
                            "curr_close": curr_close,
                        })
                        report.add_issue(
                            "warning",
                            "outliers",
                            f"Large price change: {pct_change:.2%} at {self._get_timestamp(curr_bar)}",
                            {
                                "index": i,
                                "pct_change": pct_change,
                                "prev_close": prev_close,
                                "curr_close": curr_close,
                            }
                        )
                
                # Check volume outliers (volume > 10x average of previous 5 bars)
                if i >= 5:
                    recent_volumes = [float(b.get("volume", 0)) for b in sorted_data[max(0, i-5):i]]
                    avg_volume = sum(recent_volumes) / len(recent_volumes) if recent_volumes else 0
                    curr_volume = float(curr_bar.get("volume", 0))
                    
                    if avg_volume > 0 and curr_volume > avg_volume * 10:
                        report.add_issue(
                            "warning",
                            "outliers",
                            f"Unusual volume spike at {self._get_timestamp(curr_bar)}",
                            {
                                "index": i,
                                "volume": curr_volume,
                                "avg_volume": avg_volume,
                                "ratio": curr_volume / avg_volume,
                            }
                        )
            except (ValueError, TypeError) as e:
                logger.warning(f"Error checking outliers at index {i}: {e}")
        
        report.outliers = outliers
        if not outliers:
            logger.debug("No significant outliers found")
    
    def _generate_recommendations(self, report: DataQualityReport):
        """Generate recommendations based on issues found."""
        if report.overall_status == "pass":
            report.recommendations.append("Data quality is good, no action needed")
            return
        
        if report.gaps:
            report.recommendations.append(f"Found {len(report.gaps)} gaps - consider filling missing data")
        
        if report.outliers:
            report.recommendations.append(f"Found {len(report.outliers)} outliers - verify data source accuracy")
        
        if report.validation_errors:
            report.recommendations.append(f"Found {len(report.validation_errors)} validation errors - data may be corrupted")
        
        if report.issues_found:
            error_count = sum(1 for issue in report.issues_found if issue["severity"] == "error")
            warning_count = sum(1 for issue in report.issues_found if issue["severity"] == "warning")
            report.recommendations.append(
                f"Review {error_count} errors and {warning_count} warnings before using data"
            )
    
    def _get_timestamp(self, bar: Dict) -> datetime:
        """Extract timestamp from bar, handling both datetime and string formats."""
        timestamp = bar.get("timestamp")
        if isinstance(timestamp, datetime):
            return timestamp
        elif isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                return datetime.fromisoformat(timestamp)
        else:
            raise ValueError(f"Invalid timestamp format: {timestamp}")
    
    def check_freshness(self, last_updated: datetime, max_age_hours: int = 24) -> bool:
        """
        Check if data is fresh (not stale).
        
        Args:
            last_updated: Timestamp when data was last updated
            max_age_hours: Maximum age in hours before data is considered stale
        
        Returns:
            True if data is fresh, False if stale
        """
        age = datetime.utcnow() - last_updated.replace(tzinfo=None) if last_updated.tzinfo else datetime.utcnow() - last_updated
        return age.total_seconds() / 3600 <= max_age_hours

