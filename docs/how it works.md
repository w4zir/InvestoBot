## InvestoBot – How It Works

This document explains:
- **How to run the current MVP** to generate candidate orders.
- **How the system works internally**, step by step, with concrete examples and code references.
- **What’s implemented vs next steps** so you can see where to extend the system.

---

## 1. Running the MVP to Generate Orders

### 1.1 Prerequisites

- Python 3.11+
- Node.js 22+ (for existing frontend/dev tooling)
- A **Google AI Studio API key** with access to Gemini models.
- Optional: **Alpaca paper trading** API keys if you want to execute orders, not just simulate.

Backend environment configuration lives in `backend/.env`. At minimum:

```bash
# Google AI Agents / GenAI
GOOGLE_API_KEY=your_google_api_key
GOOGLE_MODEL=gemini-2.0-flash

# Alpaca Paper Trading (optional if you only backtest)
ALPACA_API_KEY=your_alpaca_paper_key
ALPACA_SECRET_KEY=your_alpaca_paper_secret
ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets

# Data source
DATA_SOURCE=synthetic  # or "yahoo" for real OHLCV via yfinance

# Execution safety
APP_ENV=dev
ALLOW_EXECUTE=false  # keep false for safety; see below
```

### 1.2 Create and activate the virtual environment

From the project root:

```bash
# One-time setup (uses uv if available)
npm run setup:backend

# Or manual setup
cd backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

### 1.3 Start the backend

With the virtual environment activated:

```bash
cd backend
source venv/bin/activate        # Windows: venv\Scripts\activate
uvicorn app.main:app --reload --port 8000
```

Key endpoints:

**Health & Status:**
- Health check: `GET http://localhost:8000/health/`
- Root status: `GET http://localhost:8000/status`

**Strategy Management:**
- Run strategy: `POST http://localhost:8000/strategies/run`
- List strategy runs: `GET http://localhost:8000/strategies/history`
- Get strategy run details: `GET http://localhost:8000/strategies/history/{run_id}`
- Get strategy history: `GET http://localhost:8000/strategies/history/strategy/{strategy_id}`
- Get best strategies: `GET http://localhost:8000/strategies/best`

**Trading & Broker:**
- Trading account: `GET http://localhost:8000/trading/account`
- Broker health: `GET http://localhost:8000/trading/broker/health`
- Current positions: `GET http://localhost:8000/trading/broker/current`

**Control & Safety:**
- Enable kill switch: `POST http://localhost:8000/control/kill-switch/enable`
- Disable kill switch: `POST http://localhost:8000/control/kill-switch/disable`
- Kill switch status: `GET http://localhost:8000/control/kill-switch/status`
- Cancel all orders: `POST http://localhost:8000/control/orders/cancel-all`
- Get open orders: `GET http://localhost:8000/control/orders/open`
- Scheduler status: `GET http://localhost:8000/control/scheduler/status`

**Data Management:**
- Refresh data: `POST http://localhost:8000/data/refresh`
- Get metadata: `GET http://localhost:8000/data/metadata`
- Get quality report: `GET http://localhost:8000/data/quality/{symbol}`
- Validate data: `POST http://localhost:8000/data/validate`

### 1.4 Run a strategy using curl (backtest + order generation)

With the backend running and `GOOGLE_API_KEY` configured:

**Basic strategy run:**
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "deploy a simple SMA crossover strategy for AAPL",
        "context": {
          "universe": ["AAPL"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false
        }
      }' | jq .
```

**With walk-forward validation:**
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "deploy a simple SMA crossover strategy for AAPL",
        "context": {
          "universe": ["AAPL"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false,
          "validation": {
            "walk_forward": true,
            "train_split": 0.7,
            "validation_split": 0.15,
            "holdout_split": 0.15
          }
        }
      }' | jq .
```

**With scenario gating:**
```bash
curl -X POST http://localhost:8000/strategies/run \
  -H "Content-Type: application/json" \
  -d '{
        "mission": "deploy a simple SMA crossover strategy for AAPL",
        "context": {
          "universe": ["AAPL"],
          "data_range": "2023-01-01:2023-06-30",
          "execute": false,
          "enable_scenarios": true,
          "scenario_tags": ["crisis"]
        }
      }' | jq .
```

You should see a JSON response similar to:

```json
{
  "run_id": "run_1735580000",
  "mission": "deploy a simple SMA crossover strategy for AAPL",
  "candidates": [
    {
      "strategy": {
        "strategy_id": "sma_cross_1",
        "name": "SMA Crossover",
        "description": "...",
        "universe": ["AAPL"],
        "rules": [
          {
            "type": "entry",
            "indicator": "sma_cross",
            "params": { "fast": 20, "slow": 50 }
          },
          {
            "type": "exit",
            "indicator": "sma_cross",
            "params": { "fast": 20, "slow": 50, "direction": "below" }
          }
        ],
        "params": {
          "position_sizing": "fixed_fraction",
          "fraction": 0.02,
          "timeframe": "1d"
        }
      },
      "backtest": {
        "metrics": {
          "sharpe": 1.1,
          "max_drawdown": 0.12,
          "total_return": 0.18
        },
        "trade_log": [
          { "timestamp": "...", "symbol": "AAPL", "side": "buy", "quantity": 20.0, "price": 150.2 },
          { "timestamp": "...", "symbol": "AAPL", "side": "sell", "quantity": 20.0, "price": 160.3 }
        ]
      },
      "risk": {
        "approved_trades": [
          { "symbol": "AAPL", "side": "buy", "quantity": 20.0, "type": "market" }
        ],
        "violations": []
      },
      "execution_fills": [],
      "execution_error": "Execution blocked: dev environment without ALLOW_EXECUTE flag",
      "validation": null,
      "gating": null
    }
  ],
  "created_at": "2024-12-30T12:00:00Z"
}
```

Notes:
- **If `DATA_SOURCE=synthetic`**, prices are generated; metrics are for pipeline sanity, not real P&L.
- **If `DATA_SOURCE=yahoo`**, OHLCV is loaded from Yahoo Finance via `yfinance` (must be installed).
- **`validation`** field contains walk-forward validation results if enabled (see section 2.9).
- **`gating`** field contains scenario gating results if enabled (see section 2.10).

### 1.5 Enabling real paper execution (careful!)

By default, the orchestrator will **not** send orders to Alpaca in `APP_ENV=dev`.

To allow execution against your Alpaca paper account:

1. In `backend/.env`:

   ```bash
   APP_ENV=dev
   ALLOW_EXECUTE=true      # explicitly opt into execution in dev
   ```

2. Set `context.execute` to `true` in your strategy run payload:

   ```json
   {
     "mission": "deploy a simple SMA crossover strategy for AAPL",
     "context": {
       "universe": ["AAPL"],
       "data_range": "2023-01-01:2023-06-30",
       "execute": true
     }
   }
   ```

3. Confirm you are using **paper** keys and `ALPACA_PAPER_BASE_URL=https://paper-api.alpaca.markets`.

Execution results appear in:
- `candidates[i].execution_fills` – list of fills returned by Alpaca.
- `candidates[i].execution_error` – any execution-level error message.

You can also inspect the account:

```bash
curl http://localhost:8000/trading/account | jq .
```

---

## 2. Internal Flow – Step-by-Step Example

This section walks through what happens internally for a request like:

```json
{
  "mission": "deploy a simple SMA crossover strategy for AAPL",
  "context": {
    "universe": ["AAPL"],
    "data_range": "2023-01-01:2023-06-30",
    "execute": false
  }
}
```

### 2.1 FastAPI entrypoint (`/strategies/run`)

The main router is defined in `backend/app/routes/strategies.py`:

```12:27:backend/app/routes/strategies.py
@router.post("/run", response_model=StrategyRunResponse)
async def run_strategy(payload: StrategyRunRequest) -> StrategyRunResponse:
    """
    Trigger a full strategy run:
    - Google Agent proposes strategies.
    - Each strategy is backtested.
    - Risk assessment is performed and (optionally) orders are executed.
    """
    try:
        return run_strategy_run(payload)
    except ValueError as e:
        ...
```

`StrategyRunRequest` is a Pydantic model:

```78:88:backend/app/trading/models.py
class StrategyRunRequest(BaseModel):
    mission: str
    context: Dict[str, Any] = Field(default_factory=dict)
```

FastAPI validates the JSON into this model, then calls `run_strategy_run` in the orchestrator.

### 2.2 Orchestrator: coordinating the run

Core orchestration happens in `backend/app/trading/orchestrator.py`:

```40:57:backend/app/trading/orchestrator.py
def run_strategy_run(payload: StrategyRunRequest) -> StrategyRunResponse:
    mission = payload.mission
    context = payload.context

    universe = context.get("universe") or settings.data.default_universe
    data_range = context.get("data_range") or _default_date_range()

    strategies: List[StrategySpec] = generate_strategy_specs(mission=mission, context=context)

    start_dt, end_dt = _parse_date_range(data_range)
    ohlcv = market_data.load_data(universe=universe, start=start_dt, end=end_dt)

    # Determine portfolio state (Alpaca or synthetic), extract latest prices,...
    ...
    for spec in strategies:
        bt_request = BacktestRequest(...)
        backtest_result = run_backtest(bt_request, ohlcv_data=ohlcv)
        proposed_orders = generate_orders(...)
        assessment = risk_assess(portfolio=portfolio, proposed_trades=proposed_orders, latest_prices=latest_prices)
        ...
        if should_execute and assessment.approved_trades:
            broker = get_alpaca_broker()
            fills = broker.execute_orders(assessment.approved_trades)
        ...
```

High-level orchestration steps:

1. **Read mission/context**.
2. **Compute universe and date range** (defaults if not provided).
3. **Ask the Google Agent for strategy specs**.
4. **Load market data** for the requested universe/date range.
5. **Determine portfolio state** (call Alpaca if `execute=true`, otherwise use synthetic portfolio).
6. **For each candidate strategy**:
   - Run a backtest.
   - Generate proposed orders.
   - Run risk assessment on those orders.
   - Optionally execute approved trades via Alpaca.
7. Aggregate everything into a `StrategyRunResponse`.

### 2.3 LLM planner – Google Agent client and strategy parsing

The Google client is in `backend/app/agents/google_client.py`:

```20:48:backend/app/agents/google_client.py
class GoogleAgentClient:
    def __init__(self) -> None:
        if not settings.google.api_key:
            raise ValueError(
                "GOOGLE_API_KEY is not set. Please set it in your environment variables or backend/.env file. "
                "Get your API key from https://aistudio.google.com/apikey"
            )

        self._client = genai.Client(api_key=settings.google.api_key)
        self._model_name = settings.google.model

    def plan_strategy(self, mission: str, context: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "You MUST output ONLY a valid JSON object (no markdown, no code blocks, no explanations). "
            "The JSON must contain an array 'strategies', where each strategy has: "
            "strategy_id (string), ... \"params\": {\"position_sizing\": \"fixed_fraction\", ...}"
        )
        try:
            response = self._client.models.generate_content(...)
        except Exception as exc:
            ...
        ...
        return {"raw_text": text}
```

The planner that turns raw text into `StrategySpec` objects lives in `backend/app/agents/strategy_planner.py`:

```18:56:backend/app/agents/strategy_planner.py
def _extract_json_from_text(text: str) -> str:
    """
    Extract JSON from text that might contain markdown code blocks or extra prose.
    """
    json_block_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
    match = re.search(json_block_pattern, text, re.DOTALL)
    ...

def generate_strategy_specs(mission: str, context: Dict[str, Any]) -> List[StrategySpec]:
    client = get_google_agent_client()
    raw = client.plan_strategy(mission=mission, context=context)
    raw_text = raw.get("raw_text", "")
    ...
    json_text = _extract_json_from_text(raw_text)
    payload = json.loads(json_text)
    strategies_data = payload.get("strategies", [])
    ...
    for i, item in enumerate(strategies_data):
        strategies.append(StrategySpec.model_validate(item))
```

This phase:
- Asks the agent for strategies.
- Extracts JSON even if the model returns fenced code blocks.
- Validates each strategy into a strongly-typed `StrategySpec`.

### 2.4 Market data – synthetic vs Yahoo Finance

`backend/app/trading/market_data.py`:

```63:101:backend/app/trading/market_data.py
def load_data(universe: List[str], start: datetime, end: datetime) -> Dict[str, List[Dict]]:
    """
    Load OHLCV data from configured source (synthetic or Yahoo Finance).
    """
    _ensure_data_dir()
    source = settings.data.source.lower()

    logger.info(
        f"Loading market data from {source}",
        extra={"universe": universe, "start": start.isoformat(), "end": end.isoformat(), "source": source},
    )

    if source == "yahoo":
        return _load_data_yahoo(universe, start, end)
    else:
        return _load_data_synthetic(universe, start, end)
```

- `DATA_SOURCE=synthetic` → generates a simple random-walk-like price series.
- `DATA_SOURCE=yahoo` → uses `yfinance` to download OHLCV bars for each symbol.

### 2.5 Backtester – event-driven loop and metrics

The backtester lives in `backend/app/trading/backtester.py`. It:
- Extracts prices from OHLCV bars.
- Interprets **entry/exit rules** from `StrategySpec`.
- Simulates trades over time and tracks portfolio value.
- Produces Sharpe, max drawdown, and total return.
- Generates an **equity curve** that includes the initial portfolio value at the start of the backtest period.

Entry/exit rules are evaluated via helper functions:

```40:121:backend/app/trading/backtester.py
def _normalize_rule_type(rule_type: str, indicator: str) -> str:
    ...

def _evaluate_strategy_rule(rule_type: str, indicator: str, params: Dict, prices: List[float], current_idx: int, is_exit: bool = False) -> bool:
    if current_idx < 1:
        return False
    ...
    if normalized_type == "crossover":
        fast_window = params.get("fast_window") or params.get("fast", 10)
        slow_window = params.get("slow_window") or params.get("slow", 20)
        direction = params.get("direction", default_direction)
        fast_ma = sma(prices, fast_window)
        slow_ma = sma(prices, slow_window)
        ...
    elif normalized_type == "signal":
        indicator_values = evaluate_indicator(indicator, prices, params)
        ...
    elif normalized_type == "momentum":
        ...
    elif normalized_type == "mean_reversion":
        ...
```

The main loop:

```140:246:backend/app/trading/backtester.py
def run_backtest(request: BacktestRequest, ohlcv_data: Optional[Dict[str, List[Dict]]] = None) -> BacktestResult:
    ...
    prices = [bar["close"] for bar in bars]
    timestamps = [bar["timestamp"] for bar in bars]

    entry_rules = [rule for rule in strategy.rules if rule.type == "entry"]
    exit_rules = [rule for rule in strategy.rules if rule.type == "exit"]
    ...
    # Record initial portfolio value at the first bar (index 0)
    if len(bars) > 0:
        portfolio_values.append(initial_cash)
        equity_timestamps.append(timestamps[0])
    
    # Event-driven backtest loop (starts at index 1 to ensure previous bars exist for indicators)
    for i in range(1, len(bars)):
        current_price = prices[i]
        current_timestamp = timestamps[i]
        ...
        if not in_position:
            entry_signal = _evaluate_strategy_rules(entry_rules, prices, i, filter_type="entry")
        else:
            exit_signal = _evaluate_strategy_rules(exit_rules, prices, i, filter_type="exit")
        ...
        if entry_signal and not in_position:
            # enter long, apply commission + slippage
            ...
        elif exit_signal and in_position:
            # exit position, apply commission + slippage
            ...
    ...
    # compute Sharpe, max drawdown, total return
    # equity_curve is built from portfolio_values and equity_timestamps
```

This gives a realistic-enough simulation for MVP, with:
- Commission (`commission`).
- Slippage (`slippage_pct`).
- Basic position sizing from `strategy.params`.

### 2.6 Risk engine – notional and exposure limits

Risk checks are in `backend/app/trading/risk_engine.py`:

```8:49:backend/app/trading/risk_engine.py
def risk_assess(portfolio: PortfolioState, proposed_trades: List[Order], latest_prices: Optional[Dict[str, float]] = None) -> RiskAssessment:
    """
    Simple deterministic risk checks based on notional limits and blacklist.
    """
    approved: List[Order] = []
    violations: List[str] = []
    blacklist = set(settings.risk.blacklist_symbols)

    # Portfolio value for exposure checks
    portfolio_value = portfolio.cash
    if latest_prices:
        for pos in portfolio.positions:
            if pos.symbol in latest_prices:
                portfolio_value += pos.quantity * latest_prices[pos.symbol]

    for order in proposed_trades:
        if order.symbol in blacklist:
            violations.append(f"Symbol {order.symbol} is blacklisted")
            continue

        price = order.limit_price
        if price is None and latest_prices and order.symbol in latest_prices:
            price = latest_prices[order.symbol]
        elif price is None:
            price = 100.0

        notional = abs(order.quantity) * price
        ...
        if notional > settings.risk.max_trade_notional:
            violations.append(...)
            continue

        if portfolio_value > 0:
            exposure = notional / portfolio_value
            if exposure > settings.risk.max_portfolio_exposure:
                violations.append(...)
                continue

        approved.append(order)
```

This enforces:
- **Per-trade max notional**.
- **Per-trade exposure vs portfolio**.
- **Blacklist** of symbols.

### 2.7 Broker adapter – Alpaca paper trading

The adapter lives in `backend/app/trading/broker_alpaca.py`:

```20:60:backend/app/trading/broker_alpaca.py
class AlpacaBroker:
    def __init__(self) -> None:
        ...
        base_url = str(settings.alpaca.base_url).rstrip("/")
        if base_url.endswith("/v2"):
            base_url = base_url[:-3]
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "APCA-API-KEY-ID": settings.alpaca.api_key or "",
                "APCA-API-SECRET-KEY": settings.alpaca.secret_key or "",
            },
        )

    def get_account(self) -> dict:
        resp = self._client.get("/v2/account")
        resp.raise_for_status()
        return resp.json()

    def get_positions(self) -> PortfolioState:
        resp = self._client.get("/v2/positions")
        ...

    def execute_orders(self, orders: List[Order]) -> List[Fill]:
        for order in orders:
            payload = { ... }
            resp = self._client.post("/v2/orders", json=payload)
            ...
            fills.append(Fill(...))
```

The orchestrator:
- Uses `get_positions()` when `execute=true` to seed `PortfolioState`.
- Calls `execute_orders()` only when:
  - `context.execute` is true **and**
  - The environment allows it (`ALLOW_EXECUTE` or non-dev).

### 2.8 Walk-forward validation (optional)

If `context.validation.walk_forward=true` or `context.validation.train_split > 0`, the orchestrator runs walk-forward validation via `backend/app/trading/validation.py`:

**Note**: The validation module includes robust timestamp handling to ensure date comparisons work correctly with both string and datetime timestamp formats.

```133:151:backend/app/trading/orchestrator.py
        # Run walk-forward validation if enabled
        walk_forward_result: Optional[WalkForwardResult] = None
        if validation_config.walk_forward or validation_config.train_split > 0:
            logger.info(f"Running walk-forward validation for strategy {spec.strategy_id}")
            try:
                walk_forward_result = run_walk_forward_backtest(bt_request, ohlcv, validation_config)
                # Use the aggregate metrics from walk-forward as the primary backtest result
                from app.trading.models import BacktestResult
                backtest_result = BacktestResult(
                    strategy=spec,
                    metrics=walk_forward_result.aggregate_metrics,
                    trade_log=walk_forward_result.windows[0].trade_log if walk_forward_result.windows else [],
                )
            except Exception as e:
                logger.error(f"Walk-forward validation failed for strategy {spec.strategy_id}: {e}", exc_info=True)
                # Fall back to regular backtest
                backtest_result = run_backtest(bt_request, ohlcv_data=ohlcv)
        else:
            backtest_result = run_backtest(bt_request, ohlcv_data=ohlcv)
```

Walk-forward validation:
- Splits data into train/validation/holdout sets (if `train_split > 0`).
- Generates rolling or expanding windows for time-series cross-validation (if `walk_forward=true`).
- Aggregates metrics across all windows for robust performance estimates.
- Results appear in `candidate.validation` as a `WalkForwardResult` with `aggregate_metrics`, `train_metrics`, `validation_metrics`, and `holdout_metrics`.

### 2.9 Scenario gating (optional)

If `context.enable_scenarios=true`, the orchestrator evaluates strategies against predefined crisis scenarios via `backend/app/trading/scenarios.py`:

**Note**: The scenario evaluation module includes robust timestamp handling to ensure date range filtering works correctly with both string and datetime timestamp formats.

```153:169:backend/app/trading/orchestrator.py
        # Run scenario evaluation and gating if enabled
        gating_result: Optional[GatingResult] = None
        if enable_scenarios:
            logger.info(f"Running scenario evaluation for strategy {spec.strategy_id}")
            try:
                scenarios = list_scenarios(tags=scenario_tags) if scenario_tags else list_scenarios()
                if scenarios:
                    gating_result = evaluate_gates(bt_request, scenarios, ohlcv)
                    logger.info(
                        f"Scenario gating for strategy {spec.strategy_id}: passed={gating_result.overall_passed}, "
                        f"violations={len(gating_result.blocking_violations)}"
                    )
                else:
                    logger.warning("No scenarios found for evaluation")
            except Exception as e:
                logger.error(f"Scenario evaluation failed for strategy {spec.strategy_id}: {e}", exc_info=True)
```

Scenario gating:
- Evaluates strategies on historical crisis periods (2008 financial crisis, 2020 COVID, etc.).
- Applies gating rules (e.g., Sharpe > 0.5, max drawdown < 0.3) to each scenario.
- Blocks execution if `gating_result.overall_passed=false` unless `context.gating_override=true`.
- Results appear in `candidate.gating` as a `GatingResult` with `overall_passed`, `blocking_violations`, and per-scenario results.

### 2.10 Kill switch

Before any strategy execution, the orchestrator checks the kill switch:

```71:75:backend/app/trading/orchestrator.py
    # Check kill switch before proceeding
    if is_kill_switch_enabled():
        error_msg = "Strategy execution blocked: kill switch is enabled"
        logger.warning(error_msg, extra={"mission": payload.mission})
        raise ValueError(error_msg)
```

The kill switch is managed via `backend/app/routes/control.py`:
- `POST /control/kill-switch/enable` – Enable kill switch (blocks all strategy runs).
- `POST /control/kill-switch/disable` – Disable kill switch.
- `GET /control/kill-switch/status` – Get current kill switch status.

When enabled, all strategy runs are blocked at the orchestrator entry point, preventing any backtesting or execution.

### 2.11 Persistence and repository

After generating results, the orchestrator attempts to persist them to the database (non-blocking):

```249:260:backend/app/trading/orchestrator.py
    # Persist to database (non-blocking - failures are logged but don't fail the run)
    try:
        with LogContext(run_id=run_id, mission=mission):
            logger.info("Persisting strategy run to database", extra={"run_id": run_id, "candidate_count": len(candidates)})
            success = _repository.save_strategy_run(response, context)
            if success:
                logger.info("Successfully persisted strategy run", extra={"run_id": run_id})
            else:
                logger.warning("Failed to persist strategy run (database may be unavailable)", extra={"run_id": run_id})
    except Exception as e:
        # Log but don't fail the run if persistence fails
        logger.error(f"Error persisting strategy run: {e}", exc_info=True, extra={"run_id": run_id})
```

Persistence is handled by:
- `backend/app/core/repository.py` – `RunRepository` saves strategy runs, backtests, trades, risk violations, and execution fills.
- `backend/app/trading/persistence.py` – `PersistenceService` provides query operations (list runs, get run details, get best strategies).

If Supabase is unavailable, persistence fails gracefully without affecting the strategy run.

### 2.12 Data Management and Caching

The system includes a comprehensive data management layer for OHLCV market data:

**Data Manager (`backend/app/trading/data_manager.py`)**:
- **Hybrid storage**: Metadata stored in Supabase database, actual data cached in files (JSON format)
- **Automatic caching**: Data loaded from source (Yahoo Finance or synthetic) is automatically cached after first load
- **Cache freshness**: Cached data is used if it's within the TTL (default 24 hours), otherwise refreshed from source
- **Quality checks**: Data quality validation runs automatically on load, checking for gaps, outliers, OHLC relationships, missing values, and duplicate timestamps
- **Versioning**: Each dataset has a version number and checksum for change detection
- **Metadata tracking**: Database tracks file paths, last update times, quality status, and data source information

**Data Quality Checker (`backend/app/trading/data_quality.py`)**:
- **Gap detection**: Identifies missing dates in time series (configurable threshold)
- **Outlier detection**: Flags price spikes (>10% daily change) and volume anomalies
- **OHLC validation**: Ensures high >= low, high >= open/close, low <= open/close
- **Missing values**: Detects null or NaN values in required fields
- **Duplicate timestamps**: Identifies duplicate entries
- **Quality reports**: Generates detailed reports with severity levels and recommendations

**Integration with Market Data**:
- `load_data()` in `market_data.py` automatically uses the data manager if caching is enabled
- Cache hit: Loads from file if metadata exists and data is fresh
- Cache miss: Fetches from source, runs quality checks, saves to cache, updates metadata
- Force refresh: Can bypass cache for on-demand updates

**API Endpoints** (`/data/*`):
- `POST /data/refresh`: Trigger on-demand refresh for symbols and date range
- `GET /data/metadata`: Query data metadata with filters
- `GET /data/quality/{symbol}`: Get quality report for a dataset
- `POST /data/validate`: Validate a specific dataset and return quality report

**Scheduled Refresh**:
- `scheduled_refresh()` function can be called by cron jobs or schedulers
- Refreshes data for default universe with default lookback period
- Only updates stale data (respects cache TTL)

**Configuration** (`backend/app/core/config.py`):
- `DATA_CACHE_ENABLED`: Enable/disable caching (default: true)
- `DATA_CACHE_TTL_HOURS`: Cache time-to-live in hours (default: 24)
- `DATA_QUALITY_CHECKS_ENABLED`: Enable/disable quality checks (default: true)
- `DATA_FILE_FORMAT`: File format for cached data (json or parquet, default: json)

### 2.13 Response assembly

Each candidate is summarized as:

```114:122:backend/app/trading/models.py
class CandidateResult(BaseModel):
    strategy: StrategySpec
    backtest: BacktestResult
    risk: Optional[RiskAssessment] = None
    execution_fills: List[Fill] = Field(default_factory=list)
    execution_error: Optional[str] = None
    validation: Optional[WalkForwardResult] = None
    gating: Optional[GatingResult] = None
```

The top-level response:

```124:129:backend/app/trading/models.py
class StrategyRunResponse(BaseModel):
    run_id: str
    mission: str
    candidates: List[CandidateResult]
    created_at: datetime
```

This is exactly what you see as the JSON from `/strategies/run`.

---

## 3. Database Schema

The system uses a unified database schema stored in Supabase. The schema includes:

### Core Tables

- **strategy_runs**: Main run records with mission, context, and status
- **strategies**: Individual strategy specifications
- **backtest_results**: Backtest metrics and trade logs
- **risk_assessments**: Risk assessment results
- **execution_results**: Execution fills and errors
- **portfolio_snapshots**: Portfolio state snapshots over time

### Observability Tables

- **trades**: Individual trade records from backtests
- **risk_violations**: Risk assessment violations
- **fills**: Order execution fills
- **run_metrics**: Aggregated metrics per run

### Data Management Tables

- **data_sources**: Data source configurations (yahoo, synthetic, etc.)
- **data_metadata**: Metadata about loaded datasets (includes timeframe support)
- **data_quality_reports**: Quality check results per dataset

### Schema Migration

For new deployments, use the unified schema:

1. Run `backend/migrations/004_unified_schema.sql` in Supabase SQL Editor
2. Run `backend/migrations/005_add_timeframe_support.sql` to add timeframe support

The unified schema includes all features:
- Status field for strategy runs (`running`, `completed`, `failed`)
- Timeframe support for data metadata (1m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 1wk, 1mo, 3mo)
- Observability tables for detailed tracking
- Data management tables for caching and quality checks

See `backend/migrations/004_unified_schema.sql` for the complete schema definition.

## 4. Safety and Execution Controls

Key safety levers:

- **Kill switch** – `POST /control/kill-switch/enable` blocks all strategy runs immediately.
- `APP_ENV` – environment label (e.g., `dev`, `staging`, `prod`).
- `ALLOW_EXECUTE` – when `false` in `dev`, execution is blocked even if `context.execute=true`.
- Alpaca credentials – using paper keys and `ALPACA_PAPER_BASE_URL` ensures no real money is touched.
- Risk limits in `backend/app/core/config.py`:
  - `max_trade_notional`
  - `max_portfolio_exposure`
  - `blacklist_symbols`
- **Scenario gating** – strategies must pass crisis scenario tests (unless `gating_override=true`).

Execution only happens when:

1. Kill switch is disabled.
2. Strategies are generated and validated.
3. Backtests run successfully.
4. Walk-forward validation passes (if enabled).
5. Scenario gating passes (if enabled, unless overridden).
6. Risk checks approve at least one order.
7. Environment and flags permit execution.

---

## 4. What’s Implemented vs Next Steps

### 4.1 Implemented in the current MVP

- **LLM planner (Google Agent)**:
  - Prompted via `google-genai` using `GOOGLE_MODEL` (e.g., `gemini-2.0-flash`).
  - Returns structured `StrategySpec` objects via JSON parsing and validation.
- **Backtester**:
  - Event-driven loop over OHLCV prices.
  - Support for SMA crossover, simple signals, momentum, mean-reversion logic.
  - Commission and slippage modeling.
  - Sharpe, max drawdown, and total return metrics.
  - Equity curve generation with complete portfolio evolution from start to finish.
  - Multi-symbol portfolio support with per-symbol and portfolio-level evaluation modes.
- **Market data**:
  - Synthetic generator (`DATA_SOURCE=synthetic`) for fast local testing.
  - Yahoo Finance integration via `yfinance` (`DATA_SOURCE=yahoo`).
  - ✅ Data caching with hybrid storage (metadata in DB, data in files) (implemented).
  - ✅ Data quality validation (gaps, outliers, OHLC validation) (implemented).
  - ✅ Data versioning and metadata tracking (implemented).
  - ✅ On-demand and scheduled data refresh (implemented).
- **Risk engine**:
  - Per-trade notional and exposure checks.
  - Blacklist support.
- **Execution adapter (Alpaca)**:
  - Account and positions fetching.
  - Order placement via `/v2/orders` for paper trading.
- **Orchestrator + API**:
  - `/strategies/run` end-to-end pipeline.
  - `/trading/account` for current account/portfolio snapshot.
  - `/health/` and `/status` for service health and environment info.

### 4.2 Next steps and improvements

- **Backtesting & evaluation**
  - ✅ Walk-forward validation and train/validation/holdout splits (implemented).
  - ✅ Golden dataset scenarios (2008 crisis, 2020 COVID, 2022 bear market) and automated gating (implemented).
  - Add Monte Carlo resampling of returns / parameter robustness.
  - Support more scenario types (bull markets, sideways markets, sector-specific events).

- **Strategy & planner**
  - ✅ Strategy templates (volatility breakout, pairs trading, intraday mean-reversion) (implemented).
  - ✅ Strategy validation and constraint fixing (implemented).
  - ✅ Strategy diversity checking (implemented).
  - ✅ Persist strategies and results to a DB for history and reuse (implemented).
  - Improve prompts and constraints for the planner to better respect risk/constraints.

- **Observability & storage**
  - ✅ Store run results (metrics, trades, risk violations, fills) in a database (implemented).
  - ✅ Query endpoints for run history and best strategies (implemented).
  - ✅ Structured JSON logging with file persistence (implemented).
  - Add basic dashboards (e.g., Grafana, OpenTelemetry).

- **UI & UX**
  - ✅ Control Panel component for kill switch and order management (implemented).
  - Extend the React dashboard to:
    - ✅ Trigger `/strategies/run` from the UI with user-defined missions/context (implemented).
    - ✅ Visualize backtest equity curves, metrics, and risk violations (implemented).
    - ✅ Show live Alpaca paper positions and P&L (implemented).

- **Scheduling & automation**
  - ✅ Kill switch and cancel-all endpoint (implemented).
  - ✅ Scheduler utilities for market hours detection (implemented).
  - Add automated scheduling (cron/APS) to run strategies periodically or on market open/close.

- **Production hardening**
  - Secrets management (e.g., GCP Secret Manager, AWS Secrets Manager).
  - Deployment manifests and health checks for hosting platforms.
  - CI/CD integration with the test suite (`test/test_api.py`) and linting.

Use this document as a map: the current system already supports a full Think → Backtest → Risk → (Optional Execute) loop; the items above are natural extensions to move from MVP toward a robust production system.


