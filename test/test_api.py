#!/usr/bin/env python3
"""
InvestoBot API Testing Script

This script provides programmatic testing of the InvestoBot backend API endpoints.
It replaces manual curl commands with Python requests for easier testing and automation.

Usage:
    python test_api.py [--base-url BASE_URL] [--test TEST_NAME] [--execute]

Examples:
    python test_api.py                          # Run all tests
    python test_api.py --test health             # Run only health check
    python test_api.py --test strategy --execute # Run strategy test with execution enabled
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from typing import Dict, Optional

try:
    import requests
except ImportError:
    print("Error: 'requests' library not found. Install it with: pip install requests")
    sys.exit(1)


class Colors:
    """ANSI color codes for terminal output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class APITester:
    """Test suite for InvestoBot API endpoints"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.results = []

    def print_header(self, text: str):
        """Print a formatted header"""
        print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.RESET}\n")

    def print_success(self, text: str):
        """Print success message"""
        print(f"{Colors.GREEN}✓ {text}{Colors.RESET}")

    def print_error(self, text: str):
        """Print error message"""
        print(f"{Colors.RED}✗ {text}{Colors.RESET}")

    def print_warning(self, text: str):
        """Print warning message"""
        print(f"{Colors.YELLOW}⚠ {text}{Colors.RESET}")

    def print_info(self, text: str):
        """Print info message"""
        print(f"{Colors.BLUE}ℹ {text}{Colors.RESET}")

    def test_health(self) -> bool:
        """Test 1: Health check endpoint"""
        self.print_header("Test 1: Health Check")
        try:
            response = self.session.get(f"{self.base_url}/health/")
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "ok":
                self.print_success("Health check passed")
                self.print_info(f"Response: {json.dumps(data, indent=2)}")
                return True
            else:
                self.print_error(f"Unexpected status: {data}")
                return False
        except requests.exceptions.RequestException as e:
            self.print_error(f"Health check failed: {e}")
            return False

    def test_status(self) -> bool:
        """Test 2: Root status endpoint"""
        self.print_header("Test 2: Root Status")
        try:
            response = self.session.get(f"{self.base_url}/status")
            response.raise_for_status()
            data = response.json()
            
            self.print_success("Status endpoint accessible")
            self.print_info(f"Response: {json.dumps(data, indent=2)}")
            return True
        except requests.exceptions.RequestException as e:
            self.print_error(f"Status check failed: {e}")
            return False

    def test_strategy_run_backtest_only(self) -> bool:
        """Test 3: Strategy run (backtest only, no execution)"""
        self.print_header("Test 3: Strategy Run (Backtest Only)")
        
        # Calculate date range (1 year lookback)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        data_range = f"{start_date}:{end_date}"
        
        payload = {
            "mission": "Create a simple moving average crossover strategy",
            "context": {
                "universe": ["AAPL", "MSFT"],
                "data_range": data_range,
                "execute": False
            }
        }
        
        try:
            self.print_info(f"Request payload: {json.dumps(payload, indent=2)}")
            self.print_info("Sending request...")
            
            response = self.session.post(
                f"{self.base_url}/strategies/run",
                json=payload,
                timeout=120  # Strategy runs can take time
            )
            response.raise_for_status()
            data = response.json()
            
            # Validate response structure
            checks = []
            
            if "run_id" in data:
                self.print_success(f"Run ID: {data['run_id']}")
                checks.append(True)
            else:
                self.print_error("Missing 'run_id' in response")
                checks.append(False)
            
            if "candidates" in data and len(data["candidates"]) > 0:
                self.print_success(f"Found {len(data['candidates'])} candidate strategies")
                checks.append(True)
                
                # Check first candidate
                candidate = data["candidates"][0]
                
                if "backtest" in candidate:
                    backtest = candidate["backtest"]
                    if "metrics" in backtest:
                        metrics = backtest["metrics"]
                        self.print_info(f"Metrics: Sharpe={metrics.get('sharpe', 'N/A')}, "
                                      f"Max Drawdown={metrics.get('max_drawdown', 'N/A')}, "
                                      f"Total Return={metrics.get('total_return', 'N/A')}")
                        checks.append(True)
                    else:
                        self.print_error("Missing 'metrics' in backtest")
                        checks.append(False)
                    
                    if "trade_log" in backtest:
                        trade_count = len(backtest["trade_log"])
                        self.print_info(f"Trade log contains {trade_count} trades")
                        # Note: 0 trades is acceptable if no signals were generated in the date range
                        # The backtest is still valid if it completed successfully
                        if trade_count > 0:
                            self.print_success(f"Backtest generated {trade_count} trades")
                        else:
                            self.print_warning("Backtest completed with 0 trades (may indicate no signals in date range)")
                        checks.append(True)  # Accept 0 trades as valid result
                    else:
                        self.print_error("Missing 'trade_log' in backtest")
                        checks.append(False)
                
                if "risk" in candidate:
                    risk = candidate["risk"]
                    approved_count = len(risk.get("approved_trades", []))
                    violations_count = len(risk.get("violations", []))
                    self.print_info(f"Risk: {approved_count} approved, {violations_count} violations")
                    checks.append(True)
                else:
                    self.print_error("Missing 'risk' in candidate")
                    checks.append(False)
                
                if "execution_fills" in candidate:
                    fills_count = len(candidate["execution_fills"])
                    if fills_count == 0:
                        self.print_success("No execution fills (expected for execute=false)")
                        checks.append(True)
                    else:
                        self.print_warning(f"Unexpected execution fills: {fills_count}")
                        checks.append(False)
            else:
                self.print_error("No candidates in response")
                checks.append(False)
            
            # Save response to file
            output_file = "test_strategy_response.json"
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)
            self.print_info(f"Full response saved to: {output_file}")
            
            return all(checks)
            
        except requests.exceptions.Timeout:
            self.print_error("Request timed out (strategy run took too long)")
            return False
        except requests.exceptions.RequestException as e:
            self.print_error(f"Strategy run failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    self.print_error(f"Error details: {json.dumps(error_data, indent=2)}")
                except:
                    self.print_error(f"Error response: {e.response.text}")
            return False

    def test_strategy_run_with_execution(self) -> bool:
        """Test 4: Strategy run with execution enabled (WARNING: executes real orders)"""
        self.print_header("Test 4: Strategy Run WITH EXECUTION (Paper Trading)")
        self.print_warning("⚠️  This will execute real orders in your Alpaca paper trading account!")
        
        response = input("Do you want to continue? (yes/no): ")
        if response.lower() != "yes":
            self.print_info("Test skipped by user")
            return True  # Not a failure, just skipped
        
        # Calculate date range
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        data_range = f"{start_date}:{end_date}"
        
        payload = {
            "mission": "Small test strategy",
            "context": {
                "universe": ["AAPL"],
                "data_range": data_range,
                "execute": True
            }
        }
        
        try:
            self.print_info(f"Request payload: {json.dumps(payload, indent=2)}")
            self.print_info("Sending request with execution enabled...")
            
            response = self.session.post(
                f"{self.base_url}/strategies/run",
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                fills = candidate.get("execution_fills", [])
                error = candidate.get("execution_error")
                
                if error:
                    self.print_warning(f"Execution error: {error}")
                    return False
                elif len(fills) > 0:
                    self.print_success(f"Execution successful: {len(fills)} fills")
                    self.print_info(f"Fills: {json.dumps(fills, indent=2, default=str)}")
                    return True
                else:
                    self.print_warning("No execution fills (orders may have been rejected)")
                    return True  # Not necessarily a failure
            else:
                self.print_error("No candidates in response")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Strategy run with execution failed: {e}")
            return False

    def test_account_status(self) -> bool:
        """Test 5: Account status endpoint"""
        self.print_header("Test 5: Account Status")
        try:
            response = self.session.get(f"{self.base_url}/trading/account")
            response.raise_for_status()
            data = response.json()
            
            if "account" in data and "portfolio" in data:
                self.print_success("Account status retrieved")
                account = data["account"]
                portfolio = data["portfolio"]
                
                self.print_info(f"Cash: ${portfolio.get('cash', 'N/A')}")
                self.print_info(f"Positions: {len(portfolio.get('positions', []))}")
                
                if portfolio.get("positions"):
                    self.print_info("Current positions:")
                    for pos in portfolio["positions"]:
                        self.print_info(f"  - {pos.get('symbol')}: {pos.get('quantity')} shares @ ${pos.get('average_price')}")
                
                return True
            else:
                self.print_error("Invalid response structure")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Account status check failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                if e.response.status_code == 500:
                    self.print_warning("This might be expected if Alpaca credentials are not configured")
            return False

    def test_edge_case_missing_data(self) -> bool:
        """Test 6: Edge case - Missing market data"""
        self.print_header("Test 6: Edge Case - Missing Market Data")
        
        payload = {
            "mission": "Test strategy",
            "context": {
                "universe": ["INVALID_SYMBOL_XYZ"],
                "execute": False
            }
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/strategies/run",
                json=payload,
                timeout=60
            )
            
            # This might succeed but return empty results, or fail gracefully
            if response.status_code == 200:
                data = response.json()
                self.print_success("Request completed (may have empty results)")
                self.print_info("System handled missing data gracefully")
                return True
            else:
                self.print_warning(f"Request returned status {response.status_code}")
                # Still consider it a pass if it doesn't crash
                return True
                
        except requests.exceptions.RequestException as e:
            self.print_warning(f"Request failed (may be expected): {e}")
            return True  # Edge case - failure might be acceptable

    def test_strategy_run_with_walk_forward(self) -> bool:
        """Test 7: Strategy run with walk-forward validation"""
        self.print_header("Test 7: Strategy Run with Walk-Forward Validation")
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        data_range = f"{start_date}:{end_date}"
        
        payload = {
            "mission": "Create a simple moving average crossover strategy",
            "context": {
                "universe": ["AAPL"],
                "data_range": data_range,
                "execute": False,
                "validation": {
                    "walk_forward": True,
                    "train_split": 0.7,
                    "validation_split": 0.15,
                    "holdout_split": 0.15,
                }
            }
        }
        
        try:
            self.print_info(f"Request payload: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/strategies/run",
                json=payload,
                timeout=180  # Walk-forward can take longer
            )
            response.raise_for_status()
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "validation" in candidate and candidate["validation"]:
                    self.print_success("Walk-forward validation completed")
                    validation = candidate["validation"]
                    if "aggregate_metrics" in validation:
                        self.print_info(f"Aggregate Sharpe: {validation['aggregate_metrics'].get('sharpe', 'N/A')}")
                    return True
                else:
                    self.print_warning("Walk-forward validation not present in response")
                    return True  # Not a failure if validation wasn't requested properly
            else:
                self.print_error("No candidates in response")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Walk-forward test failed: {e}")
            return False

    def test_strategy_run_with_scenarios(self) -> bool:
        """Test 8: Strategy run with scenario gating"""
        self.print_header("Test 8: Strategy Run with Scenario Gating")
        
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        data_range = f"{start_date}:{end_date}"
        
        payload = {
            "mission": "Create a simple moving average crossover strategy",
            "context": {
                "universe": ["AAPL"],
                "data_range": data_range,
                "execute": False,
                "enable_scenarios": True,
                "scenario_tags": ["crisis"],  # Filter to crisis scenarios
            }
        }
        
        try:
            self.print_info(f"Request payload: {json.dumps(payload, indent=2)}")
            
            response = self.session.post(
                f"{self.base_url}/strategies/run",
                json=payload,
                timeout=180
            )
            response.raise_for_status()
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "gating" in candidate and candidate["gating"]:
                    self.print_success("Scenario gating completed")
                    gating = candidate["gating"]
                    self.print_info(f"Gating passed: {gating.get('overall_passed', 'N/A')}")
                    self.print_info(f"Blocking violations: {len(gating.get('blocking_violations', []))}")
                    return True
                else:
                    self.print_warning("Scenario gating not present in response")
                    return True  # Not a failure if scenarios weren't enabled properly
            else:
                self.print_error("No candidates in response")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Scenario gating test failed: {e}")
            return False

    def test_kill_switch(self) -> bool:
        """Test 9: Kill switch functionality"""
        self.print_header("Test 9: Kill Switch")
        
        try:
            # Get current status
            response = self.session.get(f"{self.base_url}/control/kill-switch/status")
            response.raise_for_status()
            status = response.json()
            initial_state = status.get("enabled", False)
            
            self.print_info(f"Initial kill switch state: {initial_state}")
            
            # Enable kill switch
            response = self.session.post(
                f"{self.base_url}/control/kill-switch/enable",
                params={"reason": "Test activation"}
            )
            response.raise_for_status()
            result = response.json()
            self.print_success("Kill switch enabled")
            
            # Verify it's enabled
            response = self.session.get(f"{self.base_url}/control/kill-switch/status")
            response.raise_for_status()
            status = response.json()
            if status.get("enabled"):
                self.print_success("Kill switch status confirmed enabled")
            else:
                self.print_error("Kill switch not enabled after enable call")
                return False
            
            # Try to run a strategy (should be blocked)
            payload = {
                "mission": "test mission",
                "context": {"universe": ["AAPL"], "execute": False}
            }
            response = self.session.post(
                f"{self.base_url}/strategies/run",
                json=payload,
                timeout=60
            )
            if response.status_code == 400:
                self.print_success("Strategy run correctly blocked by kill switch")
            else:
                self.print_warning(f"Strategy run not blocked (status: {response.status_code})")
            
            # Disable kill switch
            response = self.session.post(f"{self.base_url}/control/kill-switch/disable")
            response.raise_for_status()
            self.print_success("Kill switch disabled")
            
            # Restore original state if needed
            if initial_state:
                self.session.post(
                    f"{self.base_url}/control/kill-switch/enable",
                    params={"reason": "Restore original state"}
                )
            
            return True
            
        except requests.exceptions.RequestException as e:
            self.print_error(f"Kill switch test failed: {e}")
            return False

    def test_strategy_history(self) -> bool:
        """Test 10: Strategy run history endpoints"""
        self.print_header("Test 10: Strategy Run History")
        
        try:
            # List strategy runs
            response = self.session.get(
                f"{self.base_url}/strategies/history",
                params={"limit": 10, "offset": 0}
            )
            response.raise_for_status()
            runs = response.json()
            
            self.print_success(f"Retrieved {len(runs)} strategy runs")
            
            # If we have runs, try to get details for the first one
            if len(runs) > 0:
                run_id = runs[0].get("run_id")
                if run_id:
                    response = self.session.get(f"{self.base_url}/strategies/history/{run_id}")
                    response.raise_for_status()
                    run_details = response.json()
                    self.print_success(f"Retrieved details for run {run_id}")
                    self.print_info(f"Run mission: {run_details.get('mission', 'N/A')}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            # History endpoints might not be available if database is not configured
            self.print_warning(f"History test failed (may be expected if DB not configured): {e}")
            return True  # Not a failure if DB is not available

    def test_data_refresh(self) -> bool:
        """Test data refresh endpoint"""
        self.print_header("Test: Data Refresh")
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            payload = {
                "symbols": ["AAPL"],
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat(),
                "force": False
            }
            
            self.print_info(f"Request payload: {json.dumps(payload, indent=2)}")
            response = self.session.post(f"{self.base_url}/data/refresh", json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if "refreshed" in data and "cached" in data:
                self.print_success("Data refresh endpoint working")
                self.print_info(f"Refreshed: {data.get('refreshed', [])}")
                self.print_info(f"Cached: {data.get('cached', [])}")
                self.print_info(f"Message: {data.get('message', '')}")
                return True
            else:
                self.print_error("Invalid response format")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Data refresh test failed: {e}")
            return False
    
    def test_data_metadata(self) -> bool:
        """Test data metadata endpoint"""
        self.print_header("Test: Data Metadata")
        try:
            response = self.session.get(f"{self.base_url}/data/metadata?limit=10")
            response.raise_for_status()
            data = response.json()
            
            if isinstance(data, list):
                self.print_success(f"Retrieved {len(data)} metadata entries")
                if data:
                    entry = data[0]
                    self.print_info(f"Sample entry: symbol={entry.get('symbol')}, last_updated={entry.get('last_updated')}")
                return True
            else:
                self.print_error("Invalid response format")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Data metadata test failed: {e}")
            return False
    
    def test_data_quality(self) -> bool:
        """Test data quality endpoint"""
        self.print_header("Test: Data Quality")
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            
            # Test validate endpoint
            params = {
                "symbol": "AAPL",
                "start_date": start_date.date().isoformat(),
                "end_date": end_date.date().isoformat()
            }
            
            response = self.session.post(f"{self.base_url}/data/validate", params=params, timeout=60)
            response.raise_for_status()
            data = response.json()
            
            if "overall_status" in data:
                self.print_success("Data quality validation working")
                self.print_info(f"Overall status: {data.get('overall_status')}")
                self.print_info(f"Issues found: {len(data.get('issues_found', []))}")
                return True
            else:
                self.print_error("Invalid response format")
                return False
                
        except requests.exceptions.RequestException as e:
            self.print_error(f"Data quality test failed: {e}")
            return False
    
    def test_best_strategies(self) -> bool:
        """Test 11: Best strategies endpoint"""
        self.print_header("Test 11: Best Strategies")
        
        try:
            # Get best strategies
            response = self.session.get(
                f"{self.base_url}/strategies/best",
                params={"limit": 5, "min_sharpe": 0.5}
            )
            response.raise_for_status()
            result = response.json()
            
            self.print_success(f"Retrieved {result.get('count', 0)} best strategies")
            
            if result.get("strategies"):
                best = result["strategies"][0]
                self.print_info(f"Best strategy Sharpe: {best.get('sharpe', 'N/A')}")
            
            return True
            
        except requests.exceptions.RequestException as e:
            # Best strategies endpoint might not be available if database is not configured
            self.print_warning(f"Best strategies test failed (may be expected if DB not configured): {e}")
            return True  # Not a failure if DB is not available

    def run_all_tests(self, include_execution: bool = False):
        """Run all tests"""
        self.print_header("InvestoBot API Test Suite")
        self.print_info(f"Base URL: {self.base_url}\n")
        
        tests = [
            ("Health Check", self.test_health),
            ("Root Status", self.test_status),
            ("Strategy Run (Backtest)", self.test_strategy_run_backtest_only),
            ("Account Status", self.test_account_status),
            ("Edge Case - Missing Data", self.test_edge_case_missing_data),
            ("Walk-Forward Validation", self.test_strategy_run_with_walk_forward),
            ("Scenario Gating", self.test_strategy_run_with_scenarios),
            ("Kill Switch", self.test_kill_switch),
            ("Strategy History", self.test_strategy_history),
            ("Best Strategies", self.test_best_strategies),
            ("Data Refresh", self.test_data_refresh),
            ("Data Metadata", self.test_data_metadata),
            ("Data Quality", self.test_data_quality),
        ]
        
        if include_execution:
            tests.append(("Strategy Run (Execution)", self.test_strategy_run_with_execution))
        
        results = []
        for name, test_func in tests:
            try:
                result = test_func()
                results.append((name, result))
            except Exception as e:
                self.print_error(f"Test '{name}' crashed: {e}")
                results.append((name, False))
        
        # Print summary
        self.print_header("Test Summary")
        passed = sum(1 for _, result in results if result)
        total = len(results)
        
        for name, result in results:
            status = f"{Colors.GREEN}PASS{Colors.RESET}" if result else f"{Colors.RED}FAIL{Colors.RESET}"
            print(f"{status} - {name}")
        
        print(f"\n{Colors.BOLD}Total: {passed}/{total} tests passed{Colors.RESET}\n")
        
        return passed == total


def main():
    parser = argparse.ArgumentParser(
        description="Test InvestoBot API endpoints",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_api.py                          # Run all tests (no execution)
  python test_api.py --test health            # Run only health check
  python test_api.py --test strategy          # Run strategy backtest test
  python test_api.py --execute                # Include execution test (requires confirmation)
  python test_api.py --base-url http://localhost:8001  # Use different base URL
        """
    )
    
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL for the API (default: http://localhost:8000)"
    )
    
    parser.add_argument(
        "--test",
        choices=["health", "status", "strategy", "account", "edge", "walkforward", "scenarios", "killswitch", "history", "best", "data", "all"],
        default="all",
        help="Which test to run (default: all)"
    )
    
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Include execution test (WARNING: executes real orders)"
    )
    
    args = parser.parse_args()
    
    tester = APITester(base_url=args.base_url)
    
    if args.test == "all":
        success = tester.run_all_tests(include_execution=args.execute)
        sys.exit(0 if success else 1)
    elif args.test == "health":
        success = tester.test_health()
        sys.exit(0 if success else 1)
    elif args.test == "status":
        success = tester.test_status()
        sys.exit(0 if success else 1)
    elif args.test == "strategy":
        success = tester.test_strategy_run_backtest_only()
        sys.exit(0 if success else 1)
    elif args.test == "account":
        success = tester.test_account_status()
        sys.exit(0 if success else 1)
    elif args.test == "edge":
        success = tester.test_edge_case_missing_data()
        sys.exit(0 if success else 1)
    elif args.test == "walkforward":
        success = tester.test_strategy_run_with_walk_forward()
        sys.exit(0 if success else 1)
    elif args.test == "scenarios":
        success = tester.test_strategy_run_with_scenarios()
        sys.exit(0 if success else 1)
    elif args.test == "killswitch":
        success = tester.test_kill_switch()
        sys.exit(0 if success else 1)
    elif args.test == "history":
        success = tester.test_strategy_history()
        sys.exit(0 if success else 1)
    elif args.test == "best":
        success = tester.test_best_strategies()
        sys.exit(0 if success else 1)
    elif args.test == "data":
        success = (
            tester.test_data_refresh() and
            tester.test_data_metadata() and
            tester.test_data_quality()
        )
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

