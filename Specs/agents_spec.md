# InvestoBot Agents Architecture & Implementation Status

This document provides a comprehensive overview of all agents in the InvestoBot system, their architecture, current implementation status, and what's missing.

---

## Table of Contents

1. [Overview](#overview)
2. [Agent Architecture](#agent-architecture)
3. [Google Agent Client](#google-agent-client)
4. [Strategy Planner Agent](#strategy-planner-agent)
5. [Trading Orchestrator Agent](#trading-orchestrator-agent)
6. [Future Agents (Planned)](#future-agents-planned)
7. [Agent Communication Patterns](#agent-communication-patterns)
8. [Implementation Status Summary](#implementation-status-summary)

---

## Overview

InvestoBot uses an **agent-based architecture** where specialized agents handle different aspects of the autonomous trading pipeline:

- **Strategy Planning Agent**: Uses LLM to generate trading strategy specifications
- **Trading Orchestrator Agent**: Coordinates the end-to-end strategy execution workflow
- **Risk Assessment Agent** (future): Evaluates risk of proposed trades
- **Execution Agent** (future): Manages order execution and monitoring

The system follows a **Think→Act→Observe** loop pattern where agents propose actions, evaluate them, and learn from outcomes.

---

## Agent Architecture

### High-Level Flow

```
User Request (mission + context)
    ↓
[Trading Orchestrator Agent]
    ↓
[Strategy Planner Agent] → Google LLM → Strategy Specs
    ↓
[Backtester] → Backtest Results
    ↓
[Risk Engine] → Risk Assessment
    ↓
[Alpaca Broker] → Order Execution (optional)
    ↓
Response (candidates with metrics)
```

### Agent Communication

- Agents communicate via **structured data models** (Pydantic models)
- No direct agent-to-agent calls; all coordination through the Orchestrator
- Each agent is **stateless** (except singleton client instances)
- All agent decisions are **logged** for traceability

---

## Google Agent Client

**File**: `backend/app/agents/google_client.py`

### Purpose

Thin wrapper around Google's Generative AI SDK (`google.genai`) that provides a unified interface for LLM-based agent interactions.

### Architecture

```python
GoogleAgentClient
├── __init__() → Initializes genai.Client with API key
├── plan_strategy(mission, context) → Calls LLM, returns raw response
└── get_google_agent_client() → Singleton factory
```

### Implementation Status

#### ✅ Implemented

- **Client Initialization**
  - Reads `GOOGLE_API_KEY` and `GOOGLE_MODEL` from config
  - Creates `genai.Client` instance
  - Logs warnings if credentials missing

- **Strategy Planning Method**
  - `plan_strategy(mission: str, context: Dict[str, Any])` method
  - Constructs enhanced prompt with risk constraints, template references, and few-shot examples
  - Calls `models.generate_content()` with user message
  - Extracts and validates JSON from response (handles markdown code blocks)
  - Returns `{"raw_text": <model_output>, "validated_json": <json_string>, "token_usage": {...}}`

- **Response Parsing & Validation** ✅
  - JSON extraction from markdown code blocks or plain text
  - JSON syntax validation at client level
  - Structure validation (ensures "strategies" key exists and is a list)
  - Returns validated JSON string for downstream processing

- **Retry Logic & Error Handling** ✅
  - Exponential backoff retry strategy (3 attempts, 2-10 second waits)
  - Retries on `RuntimeError` (rate limits, transient failures)
  - Specific error handling for rate limits (429), quota errors, and API key issues
  - Comprehensive error logging with context

- **Prompt Engineering** ✅
  - Enhanced prompt with risk constraints section
  - Strategy template references from template registry
  - Few-shot examples from templates
  - Prompt versioning support (via `GOOGLE_PROMPT_VERSION` config)
  - Structured prompt templates with version metadata

- **Token Usage Tracking** ✅
  - Extracts token usage from API response (`usage_metadata`)
  - Tracks input tokens (`prompt_token_count`) and output tokens (`candidates_token_count`)
  - Returns token usage in response for cost tracking
  - `get_token_usage()` method to retrieve last call's token usage

- **Health Checks** ✅
  - `health_check()` method for connection health
  - `get_health_status()` returns detailed status (provider, model, prompt_version)

- **Singleton Pattern**
  - Global `_client_instance` variable
  - `get_google_agent_client()` ensures single instance

#### ❌ Missing / Incomplete

- **Streaming Support**
  - No support for streaming responses
  - No partial result handling

- **Provider Abstraction**
  - Currently hard-coded to Google GenAI
  - Infrastructure exists for provider switching (config added), but not fully implemented
  - LLM provider interface and settings exist, but Google client doesn't implement interface yet

- **Cost Budgeting**
  - Token usage tracked but no automatic cost limits or budgeting
  - No cost estimation per request

- **Agent-Specific Methods**
  - Only `plan_strategy()` implemented
  - Could add methods for:
    - Strategy critique/evaluation
    - Market analysis
    - Risk assessment reasoning

---

## Strategy Planner Agent

**File**: `backend/app/agents/strategy_planner.py`

### Purpose

High-level agent that orchestrates strategy generation by calling the Google Agent Client and parsing/validating the returned strategy specifications.

### Architecture

```python
generate_strategy_specs(mission, context)
├── get_google_agent_client() → GoogleAgentClient
├── client.plan_strategy(mission, context) → Raw JSON text
├── json.loads(raw_text) → Parse JSON
├── payload.get("strategies", []) → Extract strategies array
├── StrategySpec.model_validate(item) → Validate each strategy
└── return List[StrategySpec]
```

### Implementation Status

#### ✅ Implemented

- **Strategy Generation Flow**
  - Calls Google Agent Client with mission and context
  - Parses JSON response expecting `{"strategies": [...]}` structure
  - Validates each strategy against `StrategySpec` Pydantic model
  - Returns list of validated `StrategySpec` objects

- **Error Handling**
  - Catches `JSONDecodeError` if agent returns invalid JSON
  - Logs warnings for strategies that fail validation
  - Raises `ValueError` if no valid strategies produced

- **Validation**
  - Uses Pydantic `model_validate()` for type checking
  - Ensures required fields present (strategy_id, rules, params, etc.)
  - Filters out invalid strategies but continues processing

- **Strategy Quality Checks** ✅
  - `_validate_strategy_constraints()` validates:
    - Position sizing fraction bounds (0.01 to 0.05)
    - Blacklisted symbols in universe
    - Non-empty universe and rules
  - `_fix_strategy_constraints()` automatically fixes common violations:
    - Clamps fraction to valid range
    - Removes blacklisted symbols from universe
    - Adds default symbols if universe becomes empty

- **Strategy Diversity** ✅
  - `_ensure_strategy_diversity()` checks for duplicate strategy IDs
  - `_calculate_strategy_similarity()` computes similarity score (0.0-1.0) based on:
    - Universe overlap
    - Rule count and types
    - Indicator matching
  - Logs warnings for strategies with >90% similarity
  - Soft check (warns but doesn't remove strategies)

- **Strategy Templates** ✅
  - Template registry system (`strategy_templates.py`)
  - Predefined templates: volatility breakout, pairs trading, intraday mean-reversion
  - Templates integrated into Google Agent Client prompts
  - LLM can reference templates for structured strategy generation
  - Template examples provided as few-shot learning

#### ❌ Missing / Incomplete

- **Context Enhancement**
  - Doesn't enrich context with market data, recent performance, etc.
  - No memory/RAG integration for past strategy performance
  - No market regime information included

- **Fallback Strategies**
  - If LLM fails, no fallback to hardcoded strategies
  - No static strategy library

- **Strategy Ranking/Scoring**
  - No initial scoring before backtesting
  - No prioritization of strategies to backtest
  - All strategies processed equally

- **Multi-Agent Collaboration**
  - Single agent approach; could benefit from:
    - Critic agent to review strategies
    - Validator agent to check feasibility

---

## Trading Orchestrator Agent

**File**: `backend/app/trading/orchestrator.py`

### Purpose

The **main orchestration agent** that coordinates the entire strategy execution pipeline: strategy generation → backtesting → risk assessment → execution.

### Architecture

```python
run_strategy_run(payload: StrategyRunRequest)
├── Extract mission & context
├── Generate strategies (via Strategy Planner Agent)
├── Load market data (OHLCV) - supports synthetic and Yahoo Finance
├── Fetch portfolio state (Alpaca if executing, synthetic otherwise)
├── Extract latest prices from OHLCV
├── For each strategy:
│   ├── Run backtest (with real OHLCV data)
│   ├── Generate orders from backtest results
│   ├── Risk assess (with latest prices)
│   └── Execute orders via Alpaca (if context.execute == True and approved)
└── Return StrategyRunResponse with execution results
```

### Implementation Status

#### ✅ Implemented

- **Orchestration Flow**
  - Complete end-to-end pipeline structure
  - Calls all required components in correct order
  - Handles date range parsing and defaults

- **Strategy Generation Integration**
  - Calls `generate_strategy_specs()` to get candidate strategies
  - Processes each strategy through the pipeline

- **Market Data Loading**
  - Calls `market_data.load_data()` with universe and date range
  - Uses config defaults if not provided in context

- **Backtesting Integration**
  - Runs backtest for each strategy
  - Passes backtest results to risk assessment

- **Risk Assessment Integration**
  - Calls `risk_assess()` with portfolio state and proposed trades
  - Includes risk assessment in candidate results

- **Conditional Execution**
  - Checks `context.execute` flag before calling broker
  - Only executes if risk assessment approves trades

- **Response Generation**
  - Creates `StrategyRunResponse` with run_id, mission, candidates, timestamp
  - Includes all backtest metrics and risk assessments

#### ✅ Recently Implemented (MVP Critical Path)

- **Order Generation** ✅
  - Implemented in `backend/app/trading/order_generator.py`
  - Converts strategy signals from backtest trade log into concrete `Order` objects
  - Supports position sizing via `StrategyParams` (fixed_fraction, fixed_size)
  - Generates buy/sell orders based on target vs current positions
  - Integrated into orchestrator pipeline

- **Portfolio State Management** ✅
  - Fetches real portfolio from Alpaca when `context.execute == True`
  - Falls back to synthetic portfolio (100k cash) for backtest-only runs
  - Uses real portfolio state for order generation and risk assessment
  - Portfolio state passed to order generator and risk engine

- **Execution Flow** ✅
  - Complete order generation → risk assessment → execution chain
  - Safety guards: execution only allowed in non-dev environments or with `ALLOW_EXECUTE=true`
  - Comprehensive logging at each stage
  - Error handling with graceful degradation
  - Execution results (fills, errors) included in `CandidateResult`

#### ❌ Missing / Incomplete

- **Strategy Selection**
  - Processes all strategies; no filtering or ranking
  - No mechanism to select "best" strategy from candidates
  - No early stopping if strategy fails basic checks

- **Parallel Processing**
  - Strategies processed sequentially
  - Could parallelize backtests for faster execution

- **Error Recovery**
  - If one strategy fails, entire run may fail
  - No partial results handling
  - No retry logic for transient failures

- **Execution Feedback Loop**
  - No mechanism to learn from execution results
  - No adjustment of strategies based on live performance

- **Run History / Persistence** ✅
  - Run results persisted to database (Supabase) via `persistence.py`
  - Run history query endpoints: `/strategies/history`, `/strategies/history/{run_id}`
  - Strategy-specific history: `/strategies/history/strategy/{strategy_id}`
  - Best strategies endpoint: `/strategies/best` for cross-run comparison
  - Run replay capability not yet implemented

- **Real-Time Updates**
  - No streaming of progress updates
  - No WebSocket/SSE for long-running runs

- **Context Enrichment**
  - Doesn't fetch current market conditions
  - No integration with news/sentiment data
  - No memory of past successful strategies

---

## Future Agents (Planned)

### Risk Assessment Agent

**Status**: Currently implemented as a simple function (`risk_engine.py`), but could be enhanced into a full agent.

**Planned Capabilities**:
- Multi-tier risk evaluation (static policies → real-time checks → adaptive limits)
- VaR calculation
- Scenario stress testing
- Portfolio-level exposure analysis
- Dynamic risk limits based on market conditions

### Execution Agent

**Status**: Broker adapter exists (`broker_alpaca.py`), but no agent wrapper.

**Planned Capabilities**:
- Order routing and optimization
- Slippage monitoring and adjustment
- Fill verification and reconciliation
- Order cancellation and modification
- Multi-broker support

### Market Analysis Agent

**Status**: Not implemented.

**Planned Capabilities**:
- Real-time market data analysis
- News/sentiment integration
- Technical indicator calculation
- Market regime detection
- Volatility forecasting

### Strategy Critic Agent

**Status**: Not implemented.

**Planned Capabilities**:
- Review and critique proposed strategies
- Identify potential flaws or edge cases
- Suggest improvements
- Compare against historical strategies

### Memory Agent

**Status**: Database module exists but not used for agent memory.

**Planned Capabilities**:
- Store strategy performance history
- RAG-based retrieval of similar strategies
- Learning from past successes/failures
- Strategy recommendation based on context

---

## Agent Communication Patterns

### Current Pattern: Orchestrator-Centric

All agents communicate through the Orchestrator. No direct agent-to-agent communication.

**Pros**:
- Simple, centralized control
- Easy to debug and trace
- Clear data flow

**Cons**:
- Orchestrator becomes bottleneck
- No parallel agent collaboration
- Limited agent autonomy

### Future Pattern: Event-Driven / Message Bus

Agents could communicate via events/messages, enabling:
- Parallel processing
- Agent autonomy
- Better scalability
- Loose coupling

---

## Implementation Status Summary

### ✅ Fully Implemented

1. **Google Agent Client** - Enhanced LLM integration with:
   - JSON validation and extraction
   - Retry logic with exponential backoff
   - Enhanced prompt engineering (templates, few-shot examples, versioning)
   - Token usage tracking
   - Health checks
2. **Strategy Planner Agent** - Strategy generation with:
   - Quality checks (fraction bounds, blacklist validation)
   - Strategy diversity checking and similarity detection
   - Strategy templates integration
   - Automatic constraint fixing
3. **Trading Orchestrator Agent** - Complete end-to-end pipeline with:
   - Order generation and execution
   - Run persistence to database
   - Strategy history and comparison endpoints
4. **Order Generation** - Signal-to-order translation with position sizing (`backend/app/trading/order_generator.py`)
5. **Backtester** - Medium-complexity implementation with real indicators and metrics (`backend/app/trading/backtester.py`)
6. **Market Data** - Supports both synthetic and Yahoo Finance data sources with quality validation
7. **Risk Engine** - Enhanced with portfolio exposure checks and latest price integration
8. **Execution Flow** - Complete Alpaca integration with safety guards and error handling
9. **Run Persistence** - Database storage and query endpoints for strategy run history

### ⚠️ Partially Implemented

1. **Risk Engine** - Basic checks implemented, but not yet a full agent with reasoning
2. **Broker Adapter** - Functional but not agent-wrapped
3. **Backtester** - Medium complexity achieved; can be enhanced with more strategies and walk-forward analysis

### ❌ Not Implemented

1. **Strategy Critic Agent**
2. **Market Analysis Agent**
3. **Memory Agent**
4. **Execution Agent** (as agent, not just adapter)
5. **Multi-agent collaboration**
6. **Agent observability/monitoring**
7. **Strategy selection/ranking** - All strategies processed, no filtering

---

## Next Steps for Agent Development

1. **Enhance Strategy Planner**
   - ✅ Strategy templates (implemented)
   - ✅ Quality checks (implemented)
   - Add fallback strategies (static library for LLM failures)
   - Add context enrichment (market data, performance history)

2. **Provider Abstraction**
   - Implement LLM provider interface for Google client
   - Add OpenAI and Anthropic client implementations
   - Enable provider failover mechanism

3. **Upgrade Risk Engine to Agent**
   - Add reasoning capabilities
   - Implement multi-tier risk checks
   - Add scenario analysis

4. **Add Memory Agent**
   - Store strategy history (partially done via persistence)
   - Implement RAG for strategy retrieval
   - Learn from past performance
   - Strategy recommendation based on context

5. **Implement Strategy Critic**
   - Review strategies before backtesting
   - Identify potential issues
   - Suggest improvements

6. **Agent Observability**
   - Add tracing for agent decisions
   - Log all agent interactions
   - Create agent performance dashboard

7. **Strategy Selection & Ranking**
   - Implement initial scoring before backtesting
   - Add strategy comparison metrics
   - Select "best" strategy from candidates

---

## Notes

- All agents are currently **stateless** (except singleton clients)
- No agent-to-agent direct communication (all via Orchestrator)
- Agent decisions are logged and run results are persisted to database
- Prompt versioning supported (via config), but full A/B testing infrastructure pending
- Health checks implemented for Google Agent Client
- Token usage tracked for cost monitoring

