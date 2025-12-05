# InvestoBot Development Checklist

This checklist tracks all development tasks for the InvestoBot project, organized by priority and category.

---

## Table of Contents

1. [Critical Path (MVP Blockers)](#critical-path-mvp-blockers)
2. [Core Trading System](#core-trading-system)
3. [Agent Enhancements](#agent-enhancements)
4. [Data & Market Integration](#data--market-integration)
5. [Frontend Development](#frontend-development)
6. [Risk & Safety](#risk--safety)
7. [Evaluation & Testing](#evaluation--testing)
8. [Infrastructure & DevOps](#infrastructure--devops)
9. [Documentation](#documentation)
10. [Future Enhancements](#future-enhancements)

---

## Critical Path (MVP Blockers)

These tasks are essential for a working MVP and should be prioritized.

### Order Generation & Execution Flow

- [x] **Implement order generation from strategies** ✅ (v1 implemented)
  - [x] Create `order_generator.py` module
  - [x] Translate strategy signals/rules into concrete `Order` objects
  - [x] Implement position sizing logic (fixed_fraction, fixed_size from StrategyParams)
  - [x] Generate orders based on backtest trade log or latest signals
  - [x] Wire order generation into orchestrator (replace empty `proposed_orders` list)
  - [x] Test order generation with different strategy types ✅ (momentum, mean reversion, MA crossover tests added)

- [x] **Fix portfolio state management** ✅ (v1 implemented)
  - [x] Replace hardcoded portfolio state with real broker portfolio fetch
  - [x] Implement portfolio state tracking over time ✅ (portfolio snapshots with timestamps)
  - [x] Add portfolio state persistence ✅ (portfolio_snapshots table, persistence functions)
  - [x] Update portfolio after order execution ✅ (portfolio updated based on fills, post-execution snapshots saved)

- [x] **Complete execution flow** ✅ (v1 implemented)
  - [x] Verify order generation → risk assessment → execution chain works end-to-end
  - [x] Add execution result logging
  - [x] Include execution results in StrategyRunResponse
  - [x] Test with `context.execute=True` flag (see testing.md)

### Backtester Implementation

- [x] **Replace placeholder backtester with real implementation** ✅ (v1 implemented - medium complexity)
  - [x] Implement event-driven backtest engine
  - [x] Process OHLCV data chronologically
  - [x] Implement strategy signal generation from rules
  - [x] Track positions, cash, and P&L over time
  - [x] Calculate return series from portfolio value
  - [x] Compute real Sharpe ratio, max drawdown, total return
  - [x] Add commission and slippage modeling
  - [x] Support multiple strategy templates (mean-reversion, momentum, MA crossover)

- [x] **Strategy template implementations** ✅ (v1 implemented)
  - [x] Moving Average Crossover strategy
  - [x] Mean Reversion (Z-score) strategy
  - [x] Momentum strategy
  - [ ] Volatility Breakout strategy (future)
  - [x] Make templates configurable via StrategySpec.rules

- [x] **Backtest enhancements** ✅ (v1 implemented)
  - [x] Support walk-forward analysis
  - [x] Add out-of-sample validation (train/validation/holdout splits)
  - [ ] Implement parameter optimization (optional for MVP)
  - [x] Add trade log with detailed entries (entry/exit, P&L per trade)
  - [x] Fix equity curve to include initial portfolio value
  - [x] Support multi-symbol portfolio backtesting with per-symbol and portfolio-level modes

---

## Core Trading System

### Market Data Integration

- [x] **Replace synthetic data with real historical data** ✅ (v1 implemented)
  - [x] Integrate Yahoo Finance API (or yfinance library)
  - [ ] Add Alpha Vantage as alternative data source (future)
  - [ ] Implement data caching to disk (avoid rate limits) (future)
  - [x] Add config flag: `data.source = ["synthetic" | "yahoo"]`
  - [x] Keep synthetic data as fallback for testing
  - [ ] Support multiple timeframes (1m, 5m, 1d, etc.) (currently daily only)
  - [x] Handle missing data gracefully
  - [x] Add data validation (check for gaps, outliers) ✅ (implemented in data_quality.py)

- [x] **Data management** ✅ (v1 implemented)
  - [x] Implement data refresh/update mechanism ✅ (on-demand and scheduled refresh)
  - [x] Add data quality checks ✅ (gap detection, outlier detection, OHLC validation, missing values, duplicates)
  - [x] Create data schema/migration for stored data ✅ (unified schema with data_metadata, data_quality_reports, data_sources tables)
  - [x] Add data versioning ✅ (metadata-based versioning with checksums and timestamps)

### Risk Engine Enhancements

- [x] **Expand risk checks** ✅ (v1 implemented)
  - [x] Add portfolio-level exposure limits
  - [ ] Implement per-symbol position limits (future)
  - [ ] Add drawdown-based risk limits (future)
  - [ ] Implement correlation checks (avoid over-concentration) (future)
  - [ ] Add liquidity checks (trading volume requirements) (future)
  - [ ] Implement VaR calculation (optional for MVP) (future)

- [ ] **Risk engine as agent**
  - [ ] Convert risk_engine to agent architecture
  - [ ] Add reasoning/logging for risk decisions
  - [ ] Implement multi-tier risk assessment
  - [ ] Add scenario stress testing

### Broker Integration

- [x] **Alpaca broker enhancements**
  - [x] Add order status checking
  - [x] Implement order cancellation
  - [x] Add position monitoring
  - [x] Implement fill verification
  - [x] Add error handling and retries
  - [x] Support limit orders with price adjustments

- [x] **Broker abstraction**
  - [x] Create broker interface/abstract class
  - [x] Support multiple brokers (Alpaca, Interactive Brokers, etc.)
  - [x] Add broker health checks
  - [x] Implement broker failover (optional)

---

## Agent Enhancements

### Google Agent Client

- [x] **Response parsing improvements** ✅ (v1 implemented)
  - [x] Add JSON validation at client level
  - [x] Implement retry logic for API failures
  - [x] Add exponential backoff
  - [x] Handle rate limiting

- [x] **Prompt engineering** ✅ (v1 implemented)
  - [x] Create structured prompt templates
  - [x] Add few-shot examples
  - [x] Implement prompt versioning
  - [ ] A/B test different prompts (infrastructure ready, full system pending)

- [x] **Token tracking & cost management** ✅ (v1 implemented)
  - [x] Track input/output tokens per request
  - [x] Calculate cost per strategy generation (token_tracker.py created)
  - [x] Add token usage limits/budgeting (config added)
  - [x] Log token usage for analysis

- [x] **Provider abstraction** ✅ (v1 implemented)
  - [x] Create LLM provider interface (llm_provider_interface.py)
  - [x] Support OpenAI, Anthropic as alternatives (clients created, config added)
  - [x] Add provider switching logic (config added, LLMProviderSettings)
  - [x] Implement fallback providers (config added, manager structure created)

### Strategy Planner Agent

- [x] **Strategy quality checks** ✅ (v1 implemented)
  - [x] Validate strategy logic (indicators, parameters)
  - [x] Check for conflicting rules
  - [x] Enforce parameter bounds (min/max values) - fraction bounds, blacklist checks
  - [ ] Validate universe symbols exist (future)

- [x] **Strategy diversity** ✅ (v1 implemented)
  - [x] Ensure diverse strategy types per run (warnings logged)
  - [x] Deduplicate similar strategies (similarity checking)
  - [x] Balance strategy types (momentum, mean-reversion, etc.) - via prompt engineering

- [ ] **Context enhancement**
  - [ ] Enrich context with current market data
  - [ ] Add recent strategy performance history
  - [ ] Include market regime information
  - [ ] Add memory/RAG integration

- [x] **Strategy templates** ✅ (v1 implemented)
  - [x] Create predefined strategy templates (volatility breakout, pairs trading, intraday mean-reversion)
  - [x] Allow LLM to instantiate templates with parameters
  - [x] Validate against known strategy patterns
  - [x] Fix universe assignment for pairs trading vs other strategy types

- [ ] **Fallback strategies**
  - [ ] Create static strategy library
  - [ ] Use fallback if LLM fails
  - [ ] Add hardcoded strategies for testing

- [ ] **Strategy ranking**
  - [ ] Add initial scoring before backtesting
  - [ ] Prioritize strategies to backtest
  - [ ] Filter out obviously bad strategies early

### Trading Orchestrator Agent

- [ ] **Strategy selection**
  - [ ] Implement strategy ranking/selection logic
  - [ ] Add early stopping for failed strategies
  - [ ] Select "best" strategy from candidates
  - [ ] Add strategy comparison metrics

- [ ] **Parallel processing**
  - [ ] Parallelize backtests for multiple strategies
  - [ ] Use async/await for concurrent operations
  - [ ] Add progress tracking for long runs

- [ ] **Error recovery**
  - [ ] Handle partial failures gracefully
  - [ ] Continue processing if one strategy fails
  - [ ] Add retry logic for transient failures
  - [ ] Return partial results on errors

- [x] **Run persistence** ✅ (v1 implemented)
  - [x] Store run results to database (Supabase)
  - [x] Add run history query endpoint (`/strategies/history`)
  - [x] Enable strategy comparison across runs (`/strategies/best`)
  - [ ] Add run replay capability (future)

- [ ] **Real-time updates**
  - [ ] Add WebSocket/SSE for progress updates
  - [ ] Stream backtest progress
  - [ ] Notify on completion

- [ ] **Context enrichment**
  - [ ] Fetch current market conditions
  - [ ] Integrate news/sentiment data (optional)
  - [ ] Add memory of past successful strategies

### New Agents

- [ ] **Strategy Critic Agent**
  - [ ] Review strategies before backtesting
  - [ ] Identify potential flaws/edge cases
  - [ ] Suggest improvements
  - [ ] Compare against historical strategies

- [ ] **Market Analysis Agent**
  - [ ] Real-time market data analysis
  - [ ] News/sentiment integration
  - [ ] Technical indicator calculation
  - [ ] Market regime detection

- [ ] **Memory Agent**
  - [ ] Store strategy performance history
  - [ ] Implement RAG for strategy retrieval
  - [ ] Learn from past successes/failures
  - [ ] Strategy recommendation based on context

- [ ] **Execution Agent**
  - [ ] Wrap broker adapter in agent architecture
  - [ ] Order routing and optimization
  - [ ] Slippage monitoring
  - [ ] Fill verification and reconciliation

---

## Data & Market Integration

- [ ] **Real-time data (future)**
  - [ ] WebSocket integration for live prices
  - [ ] Real-time order book data
  - [ ] Market depth analysis

- [ ] **Alternative data sources**
  - [ ] News sentiment API integration
  - [ ] Social media sentiment
  - [ ] Economic indicators
  - [ ] Earnings calendar

- [ ] **Data pipeline**
  - [ ] ETL pipeline for data ingestion
  - [ ] Data quality monitoring
  - [ ] Data lineage tracking

---

## Frontend Development

### Dashboard Enhancements

- [x] **Strategy Run Interface** ✅ (v1 implemented)
  - [x] Create form to submit strategy run requests
  - [x] Input fields: mission, universe, lookback days, execute flag
  - [x] Call `/strategies/run` endpoint
  - [x] Display loading state during run
  - [x] Show run results when complete

- [x] **Control Panel** ✅ (v1 implemented)
  - [x] Kill switch enable/disable UI
  - [x] Open orders listing
  - [x] Cancel all orders functionality
  - [x] Scheduler status display
  - [x] Auto-refresh functionality

- [ ] **Strategy Results Display**
  - [ ] List all candidate strategies
  - [ ] Display metrics (Sharpe, max drawdown, total return)
  - [ ] Show strategy details (rules, params, universe)
  - [ ] Display risk violations (if any)
  - [ ] Add expandable sections for detailed views

- [ ] **Trade Log Visualization**
  - [ ] Table/grid of trades from backtest
  - [ ] Filter by symbol, date range
  - [ ] Show P&L per trade
  - [ ] Export trade log to CSV

- [ ] **Portfolio Dashboard**
  - [ ] Widget showing Alpaca account status
  - [ ] Display cash balance
  - [ ] Show current positions (symbol, quantity, avg price, current value)
  - [ ] Calculate unrealized P&L
  - [ ] Refresh button to update data
  - [ ] Call `/trading/account` endpoint

- [ ] **Performance Charts**
  - [ ] Equity curve chart (portfolio value over time)
  - [ ] Drawdown chart
  - [ ] Returns distribution histogram
  - [ ] Use charting library (recharts, chart.js, etc.)

- [ ] **Run History**
  - [ ] List of past strategy runs
  - [ ] Filter by date, mission, status
  - [ ] Compare runs side-by-side
  - [ ] View detailed results for each run

### UI/UX Improvements

- [ ] **Navigation**
  - [ ] Add sidebar navigation
  - [ ] Create separate pages: Dashboard, Strategies, Portfolio, History
  - [ ] Add breadcrumbs

- [ ] **Error Handling**
  - [ ] Display API errors gracefully
  - [ ] Add error boundaries
  - [ ] Show user-friendly error messages

- [ ] **Loading States**
  - [ ] Skeleton loaders for data fetching
  - [ ] Progress indicators for long operations
  - [ ] Optimistic UI updates

- [ ] **Responsive Design**
  - [ ] Mobile-friendly layouts
  - [ ] Tablet optimization
  - [ ] Test on different screen sizes

---

## Risk & Safety

- [x] **Enhanced risk controls** ✅ (v1 implemented)
  - [x] Multi-tier risk checks (static risk engine + scenario gating)
  - [x] Kill switch endpoint to cancel all orders (`/control/kill-switch/*`, `/control/orders/cancel-all`)
  - [ ] Daily loss limits (future)
  - [ ] Position size limits per symbol (future)
  - [x] Maximum portfolio exposure limits (implemented)

- [x] **Safety features** ✅ (v1 implemented)
  - [x] Paper trading mode enforced by default (APP_ENV=dev, ALLOW_EXECUTE=false)
  - [x] Explicit confirmation for live trading (ALLOW_EXECUTE flag required)
  - [x] Audit log for all trading decisions (persistence to database)
  - [ ] Human approval workflow for large trades (future)

- [ ] **Monitoring & Alerts**
  - [ ] Real-time risk metric monitoring
  - [ ] Alert on risk violations
  - [ ] Alert on unusual activity
  - [ ] Daily risk summary reports

---

## Evaluation & Testing

### Evaluation Harness

- [x] **Golden dataset creation** ✅ (v1 implemented)
  - [x] Define historical scenarios (2008 crisis, 2020 COVID, 2022 bear market)
  - [x] Create scenario definitions with date ranges and tags
  - [x] Document expected behavior for each scenario

- [x] **Automated evaluation** ✅ (v1 implemented)
  - [x] Integrated into `/strategies/run` with `enable_scenarios=true`
  - [x] Run backtests across selected scenarios
  - [x] Compare metrics against thresholds (gating rules)
  - [x] Return pass/fail for each scenario (GatingResult)
  - [ ] Generate evaluation report (future - currently in response)

- [x] **Evaluation metrics** ✅ (v1 implemented)
  - [x] Sharpe ratio threshold (configurable via GatingRule)
  - [x] Max drawdown threshold (configurable via GatingRule)
  - [x] Minimum total return (can be added via GatingRule)
  - [ ] Maximum single-day loss (future)
  - [x] Exposure limit compliance (via risk engine)

- [x] **Strategy gating** ✅ (v1 implemented)
  - [x] Automatic rejection of strategies failing evaluation (blocks execution)
  - [x] Override capability (`gating_override=true`)
  - [ ] Human review for borderline cases (future)
  - [ ] Approval workflow for production strategies (future)

### Testing

- [ ] **Unit tests**
  - [ ] Test all agent functions
  - [ ] Test backtester with known data
  - [ ] Test risk engine with various scenarios
  - [ ] Test order generation logic

- [ ] **Integration tests**
  - [ ] Test full orchestrator flow
  - [ ] Test API endpoints
  - [ ] Test broker integration (mock)
  - [ ] Test data loading

- [ ] **End-to-end tests**
  - [ ] Test complete strategy run
  - [ ] Test frontend-backend integration
  - [ ] Test authentication flow

- [ ] **Performance tests**
  - [ ] Load testing for API
  - [ ] Backtest performance benchmarks
  - [ ] Memory usage profiling

---

## Infrastructure & DevOps

### Configuration

- [ ] **Environment management**
  - [ ] Create `.env.example` template
  - [ ] Document all required environment variables
  - [ ] Add validation for required config on startup
  - [ ] Support multiple environments (dev, staging, prod)

- [ ] **Secrets management**
  - [ ] Use environment variables (current)
  - [ ] Consider secrets manager (AWS Secrets Manager, etc.)
  - [ ] Never commit secrets to git
  - [ ] Rotate API keys regularly

### Deployment

- [ ] **Docker setup**
  - [ ] Create Dockerfile for backend
  - [ ] Create Dockerfile for frontend
  - [ ] Create docker-compose.yml for local development
  - [ ] Add .dockerignore files

- [ ] **CI/CD pipeline**
  - [ ] Set up GitHub Actions / GitLab CI
  - [ ] Run tests on PR
  - [ ] Lint and format code
  - [ ] Build and push Docker images
  - [ ] Deploy to staging on merge to main

- [x] **Monitoring & Logging** ✅ (v1 implemented)
  - [x] Set up structured logging with JSON format
  - [x] Add file-based log persistence
  - [x] Fix logging configuration in main.py and scheduled_run.py
  - [ ] Add log aggregation (ELK, CloudWatch, etc.)
  - [ ] Set up application monitoring (Sentry, DataDog, etc.)
  - [x] Add health check endpoints (`/health/`, `/status`)
  - [ ] Create monitoring dashboard

- [ ] **Database setup**
  - [ ] Set up Supabase tables for run history
  - [ ] Create migrations for schema changes
  - [ ] Add database connection pooling
  - [ ] Set up database backups

### Performance

- [ ] **Optimization**
  - [ ] Add caching for market data
  - [ ] Optimize database queries
  - [ ] Add connection pooling
  - [ ] Implement rate limiting

- [ ] **Scaling**
  - [ ] Design for horizontal scaling
  - [ ] Add load balancing
  - [ ] Implement queue system for long-running tasks
  - [ ] Add auto-scaling configuration

---

## Documentation

- [ ] **API Documentation**
  - [ ] Complete OpenAPI/Swagger docs
  - [ ] Add endpoint descriptions
  - [ ] Document request/response schemas
  - [ ] Add example requests/responses

- [ ] **Code Documentation**
  - [ ] Add docstrings to all functions
  - [ ] Document complex algorithms
  - [ ] Add inline comments where needed
  - [ ] Create architecture diagrams

- [ ] **User Documentation**
  - [x] Update README with setup instructions (includes backend venv, env vars, and endpoints)
  - [ ] Create user guide for dashboard
  - [x] Document strategy creation and run process (see `docs/how it works.md`)
  - [x] Add troubleshooting guide (see README “Troubleshooting” and `test/testing.md`)

- [ ] **Developer Documentation**
  - [x] Document development setup (README: prerequisites, quick start, backend/venv)
  - [ ] Add contribution guidelines
  - [x] Document testing procedures (see `test/README.md` and `test/testing.md`)
  - [ ] Create architecture decision records (ADRs)

---

## Future Enhancements

### Advanced Features

- [ ] **Multi-strategy portfolio**
  - [ ] Run multiple strategies simultaneously
  - [ ] Allocate capital across strategies
  - [ ] Rebalance portfolio based on strategy performance

- [ ] **Strategy optimization**
  - [ ] Parameter optimization (grid search, genetic algorithms)
  - [ ] Walk-forward optimization
  - [ ] Out-of-sample validation

- [ ] **Machine learning integration**
  - [ ] Use ML for signal generation
  - [ ] Predict market regimes
  - [ ] Optimize position sizing with ML

- [ ] **Advanced analytics**
  - [ ] Monte Carlo simulation
  - [ ] Scenario analysis
  - [ ] Risk attribution
  - [ ] Performance attribution

### Production Features

- [ ] **Multi-broker support**
  - [ ] Support multiple brokers simultaneously
  - [ ] Smart order routing
  - [ ] Broker comparison and selection

- [ ] **Compliance & reporting**
  - [ ] Regulatory compliance checks
  - [ ] Automated reporting
  - [ ] Tax reporting
  - [ ] Audit trail

- [ ] **Advanced risk management**
  - [ ] Real-time VaR calculation
  - [ ] Stress testing
  - [ ] Correlation analysis
  - [ ] Dynamic hedging

- [ ] **Collaboration features**
  - [ ] Multi-user support
  - [ ] Strategy sharing
  - [ ] Team collaboration tools
  - [ ] Role-based access control

---

## Notes

- Tasks marked with [ ] are not started
- Tasks can be marked as [x] when complete
- Priority order: Critical Path → Core Trading → Agents → Frontend → Others
- Some tasks may be optional for MVP but important for production

---

## Bug Fixes & Code Quality

### Recent Bug Fixes (2024-12-30)

- [x] **Date comparison fixes** ✅
  - [x] Fixed timestamp conversion in scenario evaluation (`scenarios.py`)
  - [x] Fixed timestamp conversion in walk-forward validation (`validation.py`)
  - [x] Added `_ensure_datetime()` helper to handle both string and datetime timestamps

- [x] **Logging configuration fixes** ✅
  - [x] Fixed `configure_logging()` call in `main.py` to use `logging.INFO` instead of `None`
  - [x] Fixed `configure_logging()` call in `scheduled_run.py` to use `logging.INFO` instead of string `"INFO"`

- [x] **Strategy templates fix** ✅
  - [x] Fixed meaningless ternary expression in `strategy_templates.py`
  - [x] Pairs trading now correctly uses two symbols, other strategies use single symbol

- [x] **Equity curve fix** ✅
  - [x] Fixed equity curve to include initial portfolio value at start of backtest
  - [x] Ensures complete portfolio evolution representation from start to finish
  - [x] Applied to both single-symbol and multi-symbol backtest paths

- [x] **Multi-symbol portfolio backtesting fixes** ✅ (2024-12-30)
  - [x] Fixed portfolio valuation bug: Changed from `next()` to `max()` to find most recent bar index in multi-symbol backtesting (`backtester.py`)
  - [x] Fixed quality report persistence: Reordered operations to insert metadata first, then save quality report with metadata_id (`data_manager.py`)
  - [x] Fixed retry logic: Changed retry condition to only retry on `RuntimeError` instead of all exceptions, preventing retries on configuration errors like invalid API keys (`google_client.py`)

---

## Progress Tracking

**Last Updated**: 2024-12-30

**Overall Progress**: ~78% Complete (MVP core features implemented, agent enhancements v1 complete)

**MVP Status**: [x] Complete (core trading pipeline, backtesting, risk, execution, validation, gating, persistence)

**Recent Updates**:
- Agent Enhancements v1: Response parsing improvements, prompt versioning, token tracking, provider abstraction infrastructure
- Bug fixes: Multi-symbol portfolio valuation, quality report persistence, retry logic improvements

**Next Milestone**: Production hardening (monitoring, scaling, advanced features)

