# InvestoBot Testing Guide

This document explains how to test the critical path of the InvestoBot trading system, including strategy generation, market data loading, backtesting, order generation, risk assessment, and (optional) execution via Alpaca paper trading.

---

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Backend Testing](#backend-testing)
4. [End-to-End Testing](#end-to-end-testing)
5. [Edge Cases & Error Handling](#edge-cases--error-handling)
6. [Known Limitations](#known-limitations)
7. [Troubleshooting](#troubleshooting)

---

## Overview

The critical path consists of:

1. **Strategy Generation** – Google GenAI-based planner proposes candidate strategies (`StrategySpec`).
2. **Market Data Loading** – Historical OHLCV data (synthetic or Yahoo Finance via `yfinance`).
3. **Backtesting** – Event-driven strategy evaluation with commission and slippage.
4. **Order Generation** – Convert backtest signals and portfolio state into concrete `Order` objects.
5. **Risk Assessment** – Validate orders against static risk rules (notional, exposure, blacklist).
6. **Execution** – Execute approved orders via Alpaca paper trading (optional, safety-gated).

This guide covers testing each component individually and the full pipeline end-to-end using the `/strategies/run` and `/trading/account` endpoints.

---

## Prerequisites

### Environment Variables

Create a `.env` file in the `backend/` directory with the following variables (see `README.md` and `docs/how it works.md` for more detail):

```bash
# Google AI (for strategy generation)
GOOGLE_API_KEY=your_google_api_key_here
GOOGLE_MODEL=gemini-2.0-flash

# Alpaca (for paper trading - optional for backtest-only testing)
ALPACA_API_KEY=your_alpaca_api_key_here
ALPACA_SECRET_KEY=your_alpaca_secret_key_here
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets

# Data source (synthetic or yahoo)
DATA_SOURCE=synthetic  # or "yahoo" for real data

# Execution safety (set to "true" to allow execution in dev mode)
ALLOW_EXECUTE=false  # Set to "true" only when testing with paper trading

# App environment
APP_ENV=dev
APP_DEBUG=true
```

### Installation

1. **Create and Activate Virtual Environment**:

   **On Linux/macOS**:
   ```bash
   cd backend
   python3 -m venv venv
   source venv/bin/activate
   ```

   **On Windows**:
   ```bash
   cd backend
   python -m venv venv
   venv\Scripts\activate
   ```

   **Alternative: Use setup scripts**:
   - Linux/macOS: `./setup_venv.sh`
   - Windows: `setup_venv.bat`

2. **Install Backend Dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

3. **Start Backend Server**:
   ```bash
   # Make sure virtual environment is activated
   uvicorn app.main:app --reload --port 8000
   ```

   The API will be available at `http://localhost:8000`

   **Note**: Always activate the virtual environment before running the server. You should see `(venv)` in your terminal prompt when it's active.

3. **Verify Health**:
   ```bash
   curl http://localhost:8000/health/
   ```
   
   Or use the Python test script:
   ```bash
   cd test
   python test_api.py --test health
   ```

   Expected response:
   ```json
   {
     "status": "ok",
     "message": "API is running"
   }
   ```

---

## Backend Testing

### Automated Testing (Recommended)

For easier testing, use the Python test script:

```bash
cd test
pip install -r requirements.txt  # Install requests library
python test_api.py              # Run all tests
python test_api.py --test health  # Run specific test
python test_api.py --test strategy  # Run strategy backtest test
python test_api.py --test account  # Run account status test
python test_api.py --test edge  # Run edge case tests
python test_api.py --execute  # Include execution test (requires confirmation)
```

See `test/README.md` for more details.

### Manual Testing (curl commands)

The following sections show both Python script and curl command options for each test. For more examples and deeper explanations of the request/response structure, see `docs/how it works.md`.

---

### Test 1: Health Check

**Python Script** (Recommended):
```bash
python test_api.py --test health
```

**Manual curl**:

This test verifies the full pipeline without executing any trades.

**Request** (curl):
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Create a simple moving average crossover strategy",
    "context": {
      "universe": ["AAPL", "MSFT"],
      "data_range": "2023-01-01:2024-01-01",
      "execute": false
    }
  }'
```

**Python Script** (Recommended):
```bash
python test_api.py --test strategy
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Create a simple moving average crossover strategy",
    "context": {
      "universe": ["AAPL", "MSFT"],
      "data_range": "2023-01-01:2024-01-01",
      "execute": false
    }
  }'
```

**Expected Response Structure**:
```json
{
  "run_id": "run_1234567890",
  "mission": "Create a simple moving average crossover strategy",
  "candidates": [
    {
      "strategy": {
        "strategy_id": "str_xxx",
        "name": "...",
        "description": "...",
        "universe": ["AAPL", "MSFT"],
        "rules": [...],
        "params": {...}
      },
      "backtest": {
        "strategy": {...},
        "metrics": {
          "sharpe": 1.23,
          "max_drawdown": 0.15,
          "total_return": 0.08
        },
        "trade_log": [
          {
            "timestamp": "2023-01-15T10:00:00",
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10.0,
            "price": 150.25
          },
          ...
        ]
      },
      "risk": {
        "approved_trades": [...],
        "violations": []
      },
      "execution_fills": [],
      "execution_error": null
    }
  ],
  "created_at": "2024-01-15T10:00:00"
}
```

**What to Verify**:
- ✅ Response contains `run_id` and `candidates` array
- ✅ Each candidate has `backtest.metrics` with realistic values (Sharpe, max_drawdown, total_return)
- ✅ `backtest.trade_log` contains trade entries (buy/sell)
- ✅ `risk.approved_trades` contains generated orders (if any)
- ✅ `execution_fills` is empty (since `execute=false`)
- ✅ No `execution_error`

### Test 2: Root Status

**Python Script** (Recommended):
```bash
python test_api.py --test status
```

**Manual curl**:
```bash
curl http://localhost:8000/status
```

**What to Verify**:
- ✅ Response contains app name, environment, and debug status
- ✅ Endpoint is accessible

---

### Test 3: Strategy Run with Real Data (Yahoo Finance)

Test with real market data instead of synthetic.

**Setup**:
1. Set `DATA_SOURCE=yahoo` in `backend/.env`
2. Restart the backend server

**Python Script** (Recommended):
```bash
python test_api.py --test strategy
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Create a momentum strategy for tech stocks",
    "context": {
      "universe": ["AAPL", "GOOGL", "MSFT"],
      "data_range": "2023-06-01:2024-01-01",
      "execute": false
    }
  }'
```

**What to Verify**:
- ✅ Data loads successfully from Yahoo Finance
- ✅ Backtest metrics are calculated (may take longer due to API calls)
- ✅ Trade log reflects actual price movements
- ✅ If data unavailable for a symbol, system handles gracefully

**Note**: Yahoo Finance may rate-limit requests. If you see errors, wait a few seconds and retry, or switch back to `DATA_SOURCE=synthetic` for testing.

**Important**: Make sure your virtual environment is activated before running the server. You should see `(venv)` in your terminal prompt.

---

### Test 4: Order Generation Verification

Verify that orders are generated correctly from backtest results.

**Python Script** (Recommended):
```bash
python test_api.py --test strategy
# The script automatically validates order generation in the response
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Simple mean reversion strategy",
    "context": {
      "universe": ["AAPL"],
      "data_range": "2023-01-01:2024-01-01",
      "execute": false
    }
  }'
```

**What to Verify**:
- ✅ Check `risk.approved_trades` array - should contain `Order` objects
- ✅ Each order has: `symbol`, `side` (buy/sell), `quantity`, `type` (market)
- ✅ Orders are based on backtest trade log signals
- ✅ Order quantities respect position sizing from `StrategyParams`

**Example Order**:
```json
{
  "symbol": "AAPL",
  "side": "buy",
  "quantity": 13.33,
  "type": "market",
  "limit_price": null
}
```

---

### Test 5: Risk Assessment

Test that risk engine properly validates orders.

**Setup**: Add a symbol to blacklist in config or test with large order sizes.

**Python Script** (Recommended):
```bash
# The strategy test automatically checks risk assessment
python test_api.py --test strategy
```

**Manual curl** (with blacklisted symbol):
```bash
# First, set RISK_BLACKLIST_SYMBOLS=TEST in backend/.env, then:
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Strategy that trades TEST symbol",
    "context": {
      "universe": ["TEST"],
      "execute": false
    }
  }'
```

**What to Verify**:
- ✅ `risk.violations` array contains rejection reasons
- ✅ `risk.approved_trades` excludes blacklisted symbols
- ✅ Violation messages are descriptive

**Example Violation**:
```json
{
  "violations": [
    "Symbol TEST is blacklisted"
  ],
  "approved_trades": []
}
```

---

### Test 6: Execution Flow (Paper Trading)

**⚠️ WARNING**: This will execute real orders in your Alpaca paper trading account. Only test with paper trading credentials.

**Prerequisites**:
1. Valid Alpaca paper trading API credentials
2. `ALLOW_EXECUTE=true` in `backend/.env` OR `APP_ENV=staging` (not `dev`)
3. Paper trading account has sufficient cash

**Python Script** (Recommended):
```bash
python test_api.py --execute
# The script will prompt for confirmation before executing
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Small test strategy",
    "context": {
      "universe": ["AAPL"],
      "data_range": "2023-01-01:2024-01-01",
      "execute": true
    }
  }'
```

**What to Verify**:
- ✅ Portfolio is fetched from Alpaca (check logs)
- ✅ Orders are generated and risk-assessed
- ✅ `execution_fills` array contains `Fill` objects (if orders executed)
- ✅ Check Alpaca paper account to confirm orders were placed
- ✅ Logs show execution details

**Example Fill**:
```json
{
  "execution_fills": [
    {
      "order_id": "abc123",
      "symbol": "AAPL",
      "side": "buy",
      "quantity": 10.0,
      "price": 150.25,
      "timestamp": "2024-01-15T10:00:00"
    }
  ],
  "execution_error": null
}
```

**Verify in Alpaca Dashboard**:
- Log into Alpaca paper trading dashboard
- Check "Orders" section for recent orders
- Verify order details match `execution_fills`

### Test 7: Account Status Endpoint

Check current Alpaca account and portfolio status.

**Python Script** (Recommended):
```bash
python test_api.py --test account
```

**Manual curl**:
```bash
curl http://localhost:8000/trading/account
```

**Expected Response**:
```json
{
  "account": {
    "cash": "50000.00",
    "buying_power": "100000.00",
    ...
  },
  "portfolio": {
    "cash": 50000.0,
    "positions": [
      {
        "symbol": "AAPL",
        "quantity": 10.0,
        "average_price": 150.25
      }
    ]
  }
}
```

**What to Verify**:
- ✅ Account data is returned
- ✅ Portfolio positions match current Alpaca positions
- ✅ Cash balance is accurate

---

## End-to-End Testing

### Full Pipeline Test (Recommended Flow)

1. **Start with backtest-only** (`execute=false`) to verify strategy generation and backtesting
2. **Verify order generation** by checking `risk.approved_trades`
3. **Test risk assessment** with edge cases (blacklist, large orders)
4. **Only then test execution** (`execute=true`) with small orders in paper trading

### Automated End-to-End Test

**Python Script** (Recommended):
```bash
# Run all tests except execution
python test_api.py

# Run all tests including execution (requires confirmation)
python test_api.py --execute
```

The script will:
- Test health and status endpoints
- Run strategy backtest and validate response structure
- Check account status
- Test edge cases
- Optionally test execution (with confirmation)

### Manual End-to-End Test Scenario

```bash
# Step 1: Backtest only
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Create a diversified portfolio strategy",
    "context": {
      "universe": ["AAPL", "MSFT", "GOOGL"],
      "data_range": "2023-01-01:2024-01-01",
      "execute": false
    }
  }' > response_backtest.json

# Step 2: Inspect results
cat response_backtest.json | jq '.candidates[0].backtest.metrics'
cat response_backtest.json | jq '.candidates[0].risk.approved_trades'

# Step 3: If satisfied, execute (with ALLOW_EXECUTE=true)
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Create a diversified portfolio strategy",
    "context": {
      "universe": ["AAPL"],
      "data_range": "2023-01-01:2024-01-01",
      "execute": true
    }
  }' > response_execute.json

# Step 4: Verify execution
cat response_execute.json | jq '.candidates[0].execution_fills'
```

**Note**: The Python test script automatically saves responses to `test_strategy_response.json` for inspection.

---

## Testing Predefined Strategies

### Test: List Available Templates

**Python Script**:
```bash
python test_api.py --test templates
```

**Manual curl**:
```bash
curl http://localhost:8000/strategies/templates | jq .
```

**Expected Response**:
```json
[
  {
    "template_id": "volatility_breakout",
    "name": "Volatility Breakout",
    "description": "Entry on volatility expansion above threshold, exit on reversion...",
    "type": "volatility_breakout",
    "required_params": {
      "volatility_indicator": "atr",
      "lookback_period": 20,
      "volatility_threshold": 1.5
    },
    "optional_params": {
      "entry_threshold": 1.5,
      "exit_threshold": 0.8,
      "stop_loss_pct": 0.02,
      "take_profit_pct": 0.05
    }
  },
  ...
]
```

### Test: Run Strategy with Single Template

**Python Script**:
```bash
python test_api.py --test template
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "Using predefined strategies",
        "template_ids": ["volatility_breakout"],
        "context": {
          "universe": ["AAPL", "MSFT"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false
        }
      }' | jq .
```

**Notes**:
- This bypasses LLM for strategy generation (faster execution)
- Template is instantiated directly with provided universe
- Response structure is same as custom mission runs

### Test: Run Strategy with Multiple Templates (Combined)

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "Using predefined strategies",
        "template_ids": ["volatility_breakout", "intraday_mean_reversion"],
        "context": {
          "universe": ["AAPL"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false
        }
      }' | jq .
```

**Notes**:
- Multiple templates are instantiated and backtested individually
- LLM is called to combine them into a unified strategy
- Final result is a single combined strategy

### Test: Mixed Mode (Templates + Custom Mission)

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "Find momentum strategies for tech stocks",
        "template_ids": ["volatility_breakout"],
        "context": {
          "universe": ["AAPL", "MSFT", "GOOGL"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false
        }
      }' | jq .
```

**Notes**:
- Both template strategies and LLM-generated strategies are included
- All strategies are backtested and evaluated together

## Testing Multi-Source Decision Framework

### Test: Enable Multi-Source Decision

**Python Script**:
```bash
python test_api.py --test multi-source
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "Find momentum strategies",
        "template_ids": ["volatility_breakout"],
        "enable_multi_source_decision": true,
        "context": {
          "universe": ["AAPL", "MSFT"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false
        }
      }' | jq .
```

**Expected Behavior**:
1. Strategy is backtested as usual
2. Risk assessment is performed
3. News data is fetched (mock provider generates synthetic news)
4. Social media sentiment is fetched (mock provider generates synthetic sentiment)
5. Decision engine analyzes all sources and makes final recommendations
6. Final orders reflect decision engine output (may differ from risk assessment)

**Notes**:
- Currently uses mock data providers (synthetic news and sentiment)
- Decision engine uses LLM to analyze all sources
- Check logs for decision engine reasoning and adjustments
- If decision engine fails, system falls back to risk assessment orders

### Test: Multi-Source Decision with Custom Mission

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "Find momentum strategies for tech stocks",
        "enable_multi_source_decision": true,
        "context": {
          "universe": ["AAPL", "MSFT", "GOOGL"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false
        }
      }' | jq .
```

## Edge Cases & Error Handling

### Test 8: Missing Market Data

**Scenario**: Request data for a symbol that doesn't exist or has no data.

**Python Script** (Recommended):
```bash
python test_api.py --test edge
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Test strategy",
    "context": {
      "universe": ["INVALID_SYMBOL_XYZ"],
      "execute": false
    }
  }'
```

**Expected Behavior**:
- ✅ System handles missing data gracefully
- ✅ Backtest returns empty trade log or error message
- ✅ No crash, error logged

---

### Test 9: LLM Failure

**Scenario**: Google API key invalid or rate-limited.

**Expected Behavior**:
- ✅ Error logged with details
- ✅ Request fails with appropriate HTTP status (500)
- ✅ Error message indicates LLM issue

**Note**: This is automatically detected by the Python test script when running strategy tests.

---

### Test 10: Risk Violations

**Scenario**: Strategy generates orders that violate risk rules.

**Setup**: Set `RISK_MAX_TRADE_NOTIONAL=100` (very low) in `backend/.env`

**Python Script** (Recommended):
```bash
python test_api.py --test strategy
# The script will show risk violations in the output
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Large position strategy",
    "context": {
      "universe": ["AAPL"],
      "execute": false
    }
  }'
```

**Expected Behavior**:
- ✅ Orders generated but rejected by risk engine
- ✅ `risk.violations` contains rejection reasons
- ✅ `risk.approved_trades` is empty or reduced

---

### Test 11: Execution Blocked in Dev Mode

**Scenario**: Try to execute in dev mode without `ALLOW_EXECUTE=true`.

**Python Script** (Recommended):
```bash
python test_api.py --execute
# The script will show execution errors if blocked
```

**Manual curl**:
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
    "mission": "Test",
    "context": {
      "execute": true
    }
  }'
```

**Expected Behavior**:
- ✅ Execution blocked
- ✅ `execution_error` contains safety message
- ✅ `execution_fills` is empty
- ✅ Logs show blocking reason

---

### Test 12: Alpaca API Failure

**Scenario**: Invalid Alpaca credentials or network issue.

**Setup**: Set invalid `ALPACA_API_KEY` in `backend/.env`

**Python Script** (Recommended):
```bash
python test_api.py --test account
# The script will show appropriate warnings for API failures
```

**Expected Behavior**:
- ✅ Error caught and logged
- ✅ Falls back to synthetic portfolio
- ✅ Execution skipped with error message
- ✅ Request completes (doesn't crash)

---

## Known Limitations

### Current MVP Limitations

1. **Single Symbol Focus**: Backtester currently focuses on first symbol in universe. Multi-symbol portfolio optimization is future work.

2. **Daily Timeframe Only**: Currently supports daily bars only. Intraday (1m, 5m) support is planned.

3. **Simple Strategy Templates**: Only basic strategies (MA crossover, momentum, mean reversion) are implemented. More complex strategies require extending the rule evaluator.

4. **No Walk-Forward Analysis**: Backtests run on full date range. Walk-forward validation is future work.

5. **Limited Risk Checks**: Basic risk checks (blacklist, notional, exposure) are implemented. Advanced checks (VaR, correlation) are planned.

6. **No Strategy Selection**: All generated strategies are processed. No automatic selection of "best" strategy yet.

7. **Execution Safety**: Execution is blocked in dev mode by default. Always test with paper trading first.

### Data Source Limitations

- **Yahoo Finance**: Rate-limited, may fail for some symbols or date ranges
- **Synthetic Data**: Very simple random walk, not realistic for production testing
- **No Caching**: Data is fetched fresh each time (may be slow)

---

## Troubleshooting

### Issue: "ModuleNotFoundError" or "No module named 'app'"

**Causes**:
- Virtual environment not activated
- Running from wrong directory
- Dependencies not installed

**Solutions**:
- Activate virtual environment: `source backend/venv/bin/activate` (Linux/macOS) or `backend\venv\Scripts\activate` (Windows)
- Verify you see `(venv)` in terminal prompt
- Install dependencies: `pip install -r requirements.txt`
- Run server from project root or use `npm run backend`

### Issue: "No data found for symbol X"

**Causes**:
- Symbol doesn't exist
- Date range has no trading days
- Yahoo Finance API issue

**Solutions**:
- Verify symbol is valid (e.g., "AAPL" not "APPLE")
- Use shorter date range
- Switch to `DATA_SOURCE=synthetic` for testing
- Check Yahoo Finance directly: https://finance.yahoo.com/quote/AAPL

### Issue: "Failed to fetch portfolio from Alpaca"

**Causes**:
- Invalid API credentials
- Network issue
- Alpaca API down

**Solutions**:
- Verify `ALPACA_API_KEY` and `ALPACA_SECRET_KEY` in `.env`
- Check Alpaca status page
- System falls back to synthetic portfolio (100k cash)

### Issue: "Execution blocked: dev environment"

**Cause**: Safety guard prevents execution in dev mode.

**Solution**: Set `ALLOW_EXECUTE=true` in `.env` (only for paper trading testing)

### Issue: Backtest returns zero trades

**Causes**:
- Strategy rules never trigger (check indicator parameters)
- Date range too short
- Data quality issues

**Solutions**:
- Inspect strategy rules in response
- Try longer date range
- Check logs for indicator evaluation issues

### Issue: "Google API error" or "Invalid response from Google Agent"

**Causes**:
- Invalid `GOOGLE_API_KEY`
- Rate limiting
- Model unavailable

**Solutions**:
- Verify API key in Google Cloud Console
- Wait and retry (rate limits)
- Check `GOOGLE_MODEL` is valid (e.g., "gemini-2.0-flash")

### Issue: Orders generated but all rejected by risk engine

**Causes**:
- Risk limits too strict
- Blacklist includes symbols
- Portfolio exposure limits exceeded

**Solutions**:
- Check `risk.violations` for specific reasons
- Adjust `RISK_MAX_TRADE_NOTIONAL` or `RISK_MAX_PORTFOLIO_EXPOSURE` in `.env`
- Remove symbols from `RISK_BLACKLIST_SYMBOLS`

---

## Test Summary

The Python test script (`test_api.py`) provides automated testing for all endpoints:

| Test # | Test Name | Python Command | Status |
|--------|-----------|----------------|--------|
| 1 | Health Check | `python test_api.py --test health` | ✅ Automated |
| 2 | Root Status | `python test_api.py --test status` | ✅ Automated |
| 3 | Strategy Run (Backtest) | `python test_api.py --test strategy` | ✅ Automated |
| 4 | Order Generation | Included in Test 3 | ✅ Automated |
| 5 | Risk Assessment | Included in Test 3 | ✅ Automated |
| 6 | Execution Flow | `python test_api.py --execute` | ✅ Automated (with confirmation) |
| 7 | Account Status | `python test_api.py --test account` | ✅ Automated |
| 8 | Missing Data | `python test_api.py --test edge` | ✅ Automated |
| 9-12 | Error Handling | Included in above tests | ✅ Automated |

**Run all tests**:
```bash
python test_api.py  # All tests except execution
python test_api.py --execute  # All tests including execution
```

## Additional Resources

- **Python Test Script**: `test/test_api.py` - Automated API testing
- **Test Documentation**: `test/README.md` - Quick reference for test script
- **API Documentation**: Visit `http://localhost:8000/docs` for interactive Swagger UI
- **Logs**: Check backend console output for detailed execution traces
- **Alpaca Dashboard**: https://app.alpaca.markets/paper/dashboard/overview
- **Architecture Docs**: See `Specs/agents_spec.md` for system architecture
- **Progress Tracking**: See `Specs/checklist.md` for implementation status

---

## Next Steps

After verifying the critical path works:

1. **Frontend Integration**: Test strategy runs from the dashboard UI
2. **Performance Testing**: Test with larger universes and longer date ranges
3. **Strategy Validation**: Test with different strategy types and parameters
4. **Production Readiness**: Review safety guards, error handling, and monitoring

---

**Last Updated**: [Date of last update]
**Version**: MVP v1

