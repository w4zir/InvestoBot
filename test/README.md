# InvestoBot Test Suite

This directory contains testing tools and documentation for the InvestoBot project.

## Files

- `testing.md` - Comprehensive testing guide with manual curl commands
- `test_api.py` - Python script for automated API testing
- `requirements.txt` - Python dependencies for test scripts

## Quick Start

### 1. Install Test Dependencies

```bash
# Activate your virtual environment first
cd backend
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Install test dependencies
cd ../test
pip install -r requirements.txt
```

### 2. Run Tests

Make sure the backend server is running first:

```bash
# In one terminal, start the backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Then in another terminal:

```bash
# Run all tests
python test_api.py

# Run specific test
python test_api.py --test health
python test_api.py --test strategy
python test_api.py --test account

# Run with execution test (requires confirmation)
python test_api.py --execute

# Use different base URL
python test_api.py --base-url http://localhost:8001
```

## Available Tests

1. **Health Check** - Tests `/health/` endpoint
2. **Root Status** - Tests `/status` endpoint
3. **Strategy Run (Backtest)** - Tests strategy generation and backtesting without execution
4. **Account Status** - Tests `/trading/account` endpoint
5. **Edge Case - Missing Data** - Tests error handling for invalid symbols
6. **Strategy Run (Execution)** - Tests full pipeline with execution (requires confirmation)

## Test Output

The script provides color-coded output:
- ✓ Green: Success
- ✗ Red: Failure
- ⚠ Yellow: Warning
- ℹ Blue: Info

Test results are saved to `test_strategy_response.json` for inspection.

## Integration with CI/CD

The test script exits with code 0 on success and non-zero on failure, making it suitable for CI/CD pipelines:

```bash
python test_api.py && echo "All tests passed" || echo "Tests failed"
```

## See Also

- `testing.md` - Detailed manual testing guide
- `../README.md` - Project setup and documentation
- `../Specs/testing.md` - Architecture and testing specifications

