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
  - [ ] Test order generation with different strategy types (see testing.md)

- [x] **Fix portfolio state management** ✅ (v1 implemented)
  - [x] Replace hardcoded portfolio state with real broker portfolio fetch
  - [ ] Implement portfolio state tracking over time (future enhancement)
  - [ ] Add portfolio state persistence (optional for MVP)
  - [ ] Update portfolio after order execution (future enhancement)

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

- [ ] **Backtest enhancements** (future)
  - [ ] Support walk-forward analysis
  - [ ] Add out-of-sample validation
  - [ ] Implement parameter optimization (optional for MVP)
  - [x] Add trade log with detailed entries (entry/exit, P&L per trade)

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
  - [ ] Add data validation (check for gaps, outliers) (future)

- [ ] **Data management**
  - [ ] Implement data refresh/update mechanism
  - [ ] Add data quality checks
  - [ ] Create data schema/migration for stored data
  - [ ] Add data versioning

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

- [ ] **Alpaca broker enhancements**
  - [ ] Add order status checking
  - [ ] Implement order cancellation
  - [ ] Add position monitoring
  - [ ] Implement fill verification
  - [ ] Add error handling and retries
  - [ ] Support limit orders with price adjustments

- [ ] **Broker abstraction**
  - [ ] Create broker interface/abstract class
  - [ ] Support multiple brokers (Alpaca, Interactive Brokers, etc.)
  - [ ] Add broker health checks
  - [ ] Implement broker failover (optional)

---

## Agent Enhancements

### Google Agent Client

- [ ] **Response parsing improvements**
  - [ ] Add JSON validation at client level
  - [ ] Implement retry logic for API failures
  - [ ] Add exponential backoff
  - [ ] Handle rate limiting

- [ ] **Prompt engineering**
  - [ ] Create structured prompt templates
  - [ ] Add few-shot examples
  - [ ] Implement prompt versioning
  - [ ] A/B test different prompts

- [ ] **Token tracking & cost management**
  - [ ] Track input/output tokens per request
  - [ ] Calculate cost per strategy generation
  - [ ] Add token usage limits/budgeting
  - [ ] Log token usage for analysis

- [ ] **Provider abstraction**
  - [ ] Create LLM provider interface
  - [ ] Support OpenAI, Anthropic as alternatives
  - [ ] Add provider switching logic
  - [ ] Implement fallback providers

### Strategy Planner Agent

- [ ] **Strategy quality checks**
  - [ ] Validate strategy logic (indicators, parameters)
  - [ ] Check for conflicting rules
  - [ ] Enforce parameter bounds (min/max values)
  - [ ] Validate universe symbols exist

- [ ] **Strategy diversity**
  - [ ] Ensure diverse strategy types per run
  - [ ] Deduplicate similar strategies
  - [ ] Balance strategy types (momentum, mean-reversion, etc.)

- [ ] **Context enhancement**
  - [ ] Enrich context with current market data
  - [ ] Add recent strategy performance history
  - [ ] Include market regime information
  - [ ] Add memory/RAG integration

- [ ] **Strategy templates**
  - [ ] Create predefined strategy templates
  - [ ] Allow LLM to instantiate templates with parameters
  - [ ] Validate against known strategy patterns

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

- [ ] **Run persistence**
  - [ ] Store run results to database
  - [ ] Add run history query endpoint
  - [ ] Enable strategy comparison across runs
  - [ ] Add run replay capability

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

- [ ] **Strategy Run Interface**
  - [ ] Create form to submit strategy run requests
  - [ ] Input fields: mission, universe, lookback days, execute flag
  - [ ] Call `/strategies/run` endpoint
  - [ ] Display loading state during run
  - [ ] Show run results when complete

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

- [ ] **Enhanced risk controls**
  - [ ] Multi-tier risk checks (static → real-time → adaptive)
  - [ ] Kill switch endpoint to cancel all orders
  - [ ] Daily loss limits
  - [ ] Position size limits per symbol
  - [ ] Maximum portfolio exposure limits

- [ ] **Safety features**
  - [ ] Paper trading mode enforced by default
  - [ ] Explicit confirmation for live trading
  - [ ] Audit log for all trading decisions
  - [ ] Human approval workflow for large trades

- [ ] **Monitoring & Alerts**
  - [ ] Real-time risk metric monitoring
  - [ ] Alert on risk violations
  - [ ] Alert on unusual activity
  - [ ] Daily risk summary reports

---

## Evaluation & Testing

### Evaluation Harness

- [ ] **Golden dataset creation**
  - [ ] Define 8-12 historical scenarios (bull, bear, sideways, crashes)
  - [ ] Create holdout periods for each scenario
  - [ ] Document expected behavior for each scenario

- [ ] **Automated evaluation**
  - [ ] Create `/strategies/evaluate` endpoint
  - [ ] Run backtests across all scenarios
  - [ ] Compare metrics against thresholds
  - [ ] Return pass/fail for each scenario
  - [ ] Generate evaluation report

- [ ] **Evaluation metrics**
  - [ ] Sharpe ratio threshold
  - [ ] Max drawdown threshold
  - [ ] Minimum total return
  - [ ] Maximum single-day loss
  - [ ] Exposure limit compliance

- [ ] **Strategy gating**
  - [ ] Automatic rejection of strategies failing evaluation
  - [ ] Human review for borderline cases
  - [ ] Approval workflow for production strategies

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

- [ ] **Monitoring & Logging**
  - [ ] Set up structured logging
  - [ ] Add log aggregation (ELK, CloudWatch, etc.)
  - [ ] Set up application monitoring (Sentry, DataDog, etc.)
  - [ ] Add health check endpoints
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

## Progress Tracking

**Last Updated**: [Date]

**Overall Progress**: [X]% Complete

**MVP Status**: [ ] Not Started | [ ] In Progress | [ ] Complete

**Next Milestone**: [Description]

