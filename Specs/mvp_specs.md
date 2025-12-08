# Autonomous Trading Agent — Specs

This document contains mvp specs for investobot:

- **MVP Spec** — focused, runnable, and testable in weeks using paper trading and basic automation.

---

# Table of contents

1. MVP Spec
   - Summary & goals
   - Success criteria
   - Components & responsibilities
   - Data sources
   - Tool / API schemas (function-call style)
   - Key algorithms & modules
   - Evaluation & golden dataset
   - Security & guardrails
   - Roadmap (milestones & timeline)
   - Minimal deliverables
---

# 1) MVP Spec

## Summary & goals

Build a paper-trading autonomous agent that:
- Generates investment strategies (rules/signals) via an LLM planner.
- Backtests candidate strategies on historical data with slippage & transaction cost models.
- Executes trades in a paper/sandbox broker environment.
- Uses a deterministic risk engine for position sizing and portfolio constraints.
- Logs full decision trace and exposes a basic dashboard for P&L and risk.

Primary goals:
- Create a repeatable Think→Act→Observe loop.
- Ensure safety by running all strategies in paper mode with automated evaluation gates.
- Produce reproducible metrics (Sharpe, max drawdown, realized P&L) and traceability.


## Success criteria (MVP measurable)

1. Able to ingest historical OHLCV (1m/5m/1d) and run backtests across a chosen universe (10 tickers).
2. LLM planner can propose at least 3 candidate strategies per run, each backtested with a summary report.
3. **Predefined strategy templates** can be instantiated directly (bypassing LLM) for faster execution.
4. **Multiple templates** can be combined intelligently using LLM to create unified strategies.
5. Risk engine enforces per-trade max loss and portfolio exposure limits — no simulated trade exceeds set limits.
6. **Multi-source decision framework** combines strategy metrics, news sentiment, and social media sentiment for final decisions (skeleton implemented with mock providers).
7. Paper broker adapter executes orders in a sandbox and records fills with timestamps and slippage model.
8. Dashboard shows P&L, exposure, and agent trace for each strategy execution.
9. Automated evaluation harness accepts/rejects strategies against golden dataset rules.


## Components & responsibilities

- **Orchestrator (FastAPI / Python)**
  - Endpoint: /run_strategy, /evaluate, /status
  - Coordinates LLM planner → backtester → risk engine → executor.

- **LLM Planner (Hosted LLM)**
  - Inputs: mission, memory snippets, market context
  - Outputs: strategy spec (rules, params, timeframe, universe)

- **Backtester (Deterministic)**
  - Inputs: strategy spec, historical data, cost model
  - Outputs: backtest report, performance metrics, trade log

- **Risk Engine**
  - Inputs: portfolio state, proposed trades
  - Outputs: approved / adjusted trade sizes, policy violation flags

- **Execution Adapter (Paper Broker)**
  - Mock/real paper account; provides simulated fills
  - Records order/fill events and returns confirmations

- **Memory & Vector DB (optional MVP)**
  - Store strategy specs + summary + metrics for RAG

- **Observability & Dashboard**
  - Structured logs, minimal Grafana dashboard or simple Streamlit app


## Data sources

- Historical market data available for free (Alpha Vantage / Yahoo) in OHLCV format
- Fundamental/alternative data (optional MVP)
- Paper broker API (Alpaca paper) for execution


## Tool / API schemas (function-call style) — **MVP**

### 1) LLM Planner

```json
{ "name": "llm_generate_strategy", "input": {"mission": "deploy new mean-reversion strategy", "context": {"universe": ["AAPL","MSFT"], "lookback": "90d"}}, "output": {"strategy_id":"str_001","rules":[{"type":"signal","indicator":"zscore","params":{"window":20,"threshold":2}}],"params":{"position_sizing":"fixed_fraction","fraction":0.02}} }
```

### 2) Backtester

```json
{ "name": "backtest_run", "input": {"strategy_id":"str_001","data_range":"2020-01-01:2024-12-31","costs":{"commission":0.001,"slippage_pct":0.0005}}, "output": {"metrics":{"sharpe":1.2,"max_drawdown":0.12},"trade_log":[ ... ] } }
```

### 3) Risk Engine

```json
{ "name": "risk_assess", "input": {"portfolio": {...}, "proposed_trades": [...]}, "output": {"approved_trades": [...], "violations": [] } }
```

### 4) Executor (Paper)

```json
{ "name": "execute_orders", "input": {"orders": [...]}, "output": {"fills": [...], "timestamps": [...] } }
```


## Key algorithms & modules (implementation notes)

- **Strategy templates**: mean-reversion, momentum, moving-average cross, volatility breakout. These are *templates* LLM populates with parameters.
- **Position sizing**: fixed fractional (MVP), with deterministic fallback to 0 position if risk engine blocks.
- **Backtester**: event-driven simulation, includes commission and slippage model, supports walk-forward split.
- **Evaluation**: use out-of-sample metrics. Require > baseline Sharpe and lower drawdown to pass gate.


## Evaluation & golden dataset

- Create 8–12 historical scenarios (including 2008-like drawdown, 2020 COVID spike, sideways market) as holdouts.
- For each candidate strategy, run:
  - In-sample backtest (train window)
  - Walk-forward out-of-sample (validation + holdout)
  - Monte Carlo resampling of returns / parameter robustness
- Golden dataset checks:
  - No single-day drawdown > X
  - Sharpe above baseline Y on holdout
  - Max exposure rules satisfied


## Security & guardrails (MVP)

- Use paper-only keys by default. Secrets stored in environment variables or a secrets manager.
- Hard-coded limits: max per-trade notional, max portfolio exposure, blacklist instrument list.
- Human override endpoint to cancel all orders.


## Roadmap (milestones & timeline)

1. Week 1–2: Data ingestion, simple backtester and demo strategies.
2. Week 2–4: LLM planner integration + 3 strategy templates + risk engine.
3. Week 4–6: Paper execution adapter, logging, dashboard.
4. Week 6–8: Evaluation harness + golden dataset, automated gating.

---

## Current implementation notes (MVP)

- **Orchestrator (FastAPI / Python)**  
  - Implemented in `backend/app/main.py` and `backend/app/trading/orchestrator.py`.  
  - Exposed via `POST /strategies/run` and `GET /trading/account` (see `README.md` and `docs/how it works.md`).

- **LLM Planner (Hosted LLM)**  
  - Implemented using Google GenAI via `backend/app/agents/google_client.py` and `backend/app/agents/strategy_planner.py`.  
  - Strategies are returned as `StrategySpec` models (`backend/app/trading/models.py`).

- **Backtester (Deterministic)**  
  - Implemented in `backend/app/trading/backtester.py` using OHLCV data from `backend/app/trading/market_data.py`.  
  - Supports synthetic data or Yahoo Finance (`DATA_SOURCE` flag), commission, slippage, and basic metrics (Sharpe, max drawdown, total return).

- **Risk Engine**  
  - Implemented in `backend/app/trading/risk_engine.py`.  
  - Enforces per-trade notional limits, portfolio exposure constraints, and symbol blacklist, using settings from `backend/app/core/config.py`.

- **Execution Adapter (Paper Broker)**  
  - Implemented as an Alpaca paper-trading adapter in `backend/app/trading/broker_alpaca.py`.  
  - Integrated into the orchestrator with safety flags (`APP_ENV`, `ALLOW_EXECUTE`) to block execution in dev by default.

- **Data sources**  
  - Synthetic data: fast local testing (`DATA_SOURCE=synthetic`).  
  - Yahoo Finance: real historical OHLCV via `yfinance` (`DATA_SOURCE=yahoo`).

- **Evaluation & golden dataset**  
  - Basic backtest metrics are in place; the full golden dataset harness (multiple historical scenarios, Monte Carlo resampling, automated gating) is **not yet implemented** and remains a next step.

- **Observability & Dashboard**  
  - Backend logs decisions and metrics; the React dashboard exists as a Supabase-authenticated shell but is not yet wired to show strategy runs and P&L.  
  - Dashboard and richer observability (Grafana/OTel) are future work.

For a detailed walkthrough of the current implementation, including example requests and code snippets, see [`docs/how it works.md`](../docs/how%20it%20works.md).
