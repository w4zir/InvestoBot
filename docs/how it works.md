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

- Health: `GET http://localhost:8000/health/`
- Root status: `GET http://localhost:8000/status`
- Strategy run: `POST http://localhost:8000/strategies/run`
- Trading account: `GET http://localhost:8000/trading/account`

### 1.4 Run a strategy using curl (backtest + order generation)

With the backend running and `GOOGLE_API_KEY` configured:

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
      "execution_error": "Execution blocked: dev environment without ALLOW_EXECUTE flag"
    }
  ],
  "created_at": "2024-12-30T12:00:00Z"
}
```

Notes:
- **If `DATA_SOURCE=synthetic`**, prices are generated; metrics are for pipeline sanity, not real P&L.
- **If `DATA_SOURCE=yahoo`**, OHLCV is loaded from Yahoo Finance via `yfinance` (must be installed).

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

### 2.8 Response assembly

Each candidate is summarized as:

```96:115:backend/app/trading/models.py
class CandidateResult(BaseModel):
    strategy: StrategySpec
    backtest: BacktestResult
    risk: Optional[RiskAssessment] = None
    execution_fills: List[Fill] = Field(default_factory=list)
    execution_error: Optional[str] = None
```

The top-level response:

```118:125:backend/app/trading/models.py
class StrategyRunResponse(BaseModel):
    run_id: str
    mission: str
    candidates: List[CandidateResult]
    created_at: datetime
```

This is exactly what you see as the JSON from `/strategies/run`.

---

## 3. Safety and Execution Controls

Key safety levers:

- `APP_ENV` – environment label (e.g., `dev`, `staging`, `prod`).
- `ALLOW_EXECUTE` – when `false` in `dev`, execution is blocked even if `context.execute=true`.
- Alpaca credentials – using paper keys and `ALPACA_PAPER_BASE_URL` ensures no real money is touched.
- Risk limits in `backend/app/core/config.py`:
  - `max_trade_notional`
  - `max_portfolio_exposure`
  - `blacklist_symbols`

Execution only happens when:

1. Strategies are generated and validated.
2. Backtests run successfully.
3. Risk checks approve at least one order.
4. Environment and flags permit execution.

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
- **Market data**:
  - Synthetic generator (`DATA_SOURCE=synthetic`) for fast local testing.
  - Yahoo Finance integration via `yfinance` (`DATA_SOURCE=yahoo`).
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
  - Support multi-symbol portfolios and position rebalancing.
  - Add walk-forward validation and train/validation/holdout splits.
  - Implement golden dataset scenarios (e.g., 2008 crisis, 2020 COVID shock) and automated gating.
  - Add Monte Carlo resampling of returns / parameter robustness.

- **Strategy & planner**
  - Add more strategy templates (volatility breakout, pairs trading, intraday mean-reversion).
  - Improve prompts and constraints for the planner to better respect risk/constraints.
  - Persist strategies and results to a DB for history and reuse.

- **Observability & storage**
  - Store run results (metrics, trades, risk violations, fills) in a database.
  - Add structured logging sinks and basic dashboards (e.g., Grafana, OpenTelemetry).

- **UI & UX**
  - Extend the React dashboard to:
    - Trigger `/strategies/run` from the UI with user-defined missions/context.
    - Visualize backtest equity curves, metrics, and risk violations.
    - Show live Alpaca paper positions and P&L.

- **Scheduling & automation**
  - Add a scheduler (cron/APS) to run strategies periodically or on market open/close.
  - Implement guardrails and manual overrides (kill switch, cancel-all endpoint).

- **Production hardening**
  - Secrets management (e.g., GCP Secret Manager, AWS Secrets Manager).
  - Deployment manifests and health checks for hosting platforms.
  - CI/CD integration with the test suite (`test/test_api.py`) and linting.

Use this document as a map: the current system already supports a full Think → Backtest → Risk → (Optional Execute) loop; the items above are natural extensions to move from MVP toward a robust production system.


