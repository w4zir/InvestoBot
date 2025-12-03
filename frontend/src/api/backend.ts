// API client for backend FastAPI endpoints

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Type definitions matching backend models
export interface StrategyRule {
  type: string;
  indicator: string;
  params: Record<string, any>;
}

export interface StrategyParams {
  position_sizing: 'fixed_fraction' | 'fixed_size';
  fraction?: number;
  timeframe?: string;
  evaluation_mode?: 'per_symbol' | 'portfolio_level';
  rebalancing_mode?: 'time_based' | 'signal_based' | 'both';
  rebalancing_frequency?: string | null;
  max_positions?: number | null;
}

export interface StrategySpec {
  strategy_id: string;
  name?: string | null;
  description?: string | null;
  universe: string[];
  rules: StrategyRule[];
  params: StrategyParams;
}

export interface Trade {
  timestamp: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
}

export interface BacktestMetrics {
  sharpe: number;
  max_drawdown: number;
  total_return?: number | null;
}

export interface EquityPoint {
  timestamp: string;
  value: number;
}

export interface BacktestResult {
  strategy: StrategySpec;
  metrics: BacktestMetrics;
  trade_log: Trade[];
  equity_curve?: EquityPoint[] | null;
}

export interface Order {
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  type: 'market' | 'limit';
  limit_price?: number | null;
}

export interface RiskAssessment {
  approved_trades: Order[];
  violations: string[];
}

export interface Fill {
  order_id: string;
  symbol: string;
  side: 'buy' | 'sell';
  quantity: number;
  price: number;
  timestamp: string;
}

export interface CandidateResult {
  strategy: StrategySpec;
  backtest: BacktestResult;
  risk?: RiskAssessment | null;
  execution_fills: Fill[];
  execution_error?: string | null;
  validation?: any | null;
  gating?: any | null;
}

export interface StrategyRunRequest {
  mission: string;
  context: Record<string, any>;
}

export interface StrategyRunResponse {
  run_id: string;
  mission: string;
  candidates: CandidateResult[];
  created_at: string;
}

export interface PortfolioPosition {
  symbol: string;
  quantity: number;
  average_price: number;
}

export interface PortfolioState {
  cash: number;
  positions: PortfolioPosition[];
}

export interface AccountStatus {
  account: Record<string, any>;
  portfolio: PortfolioState;
}

// API functions
async function fetchAPI<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`API error: ${response.status} ${response.statusText} - ${errorText}`);
  }

  return response.json();
}

export async function runStrategy(request: StrategyRunRequest): Promise<StrategyRunResponse> {
  return fetchAPI<StrategyRunResponse>('/strategies/run', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getAccountStatus(): Promise<AccountStatus> {
  return fetchAPI<AccountStatus>('/trading/account');
}

export async function getHealth(): Promise<{ status: string }> {
  return fetchAPI<{ status: string }>('/health/');
}

// Control endpoints
export interface KillSwitchStatus {
  enabled: boolean;
  reason?: string | null;
  activated_at?: string | null;
}

export interface CancelOrdersResponse {
  cancelled_count: number;
  total_orders: number;
  errors: string[];
  message: string;
}

export interface OpenOrdersResponse {
  count: number;
  orders: any[];
}

export interface SchedulerStatus {
  active_runs: string[];
  active_run_count: number;
  kill_switch_enabled: boolean;
}

export async function getKillSwitchStatus(): Promise<KillSwitchStatus> {
  return fetchAPI<KillSwitchStatus>('/control/kill-switch/status');
}

export async function enableKillSwitch(reason: string = 'Manual activation'): Promise<{ status: string; reason: string; activated_at: string; message: string }> {
  return fetchAPI<{ status: string; reason: string; activated_at: string; message: string }>(`/control/kill-switch/enable?reason=${encodeURIComponent(reason)}`, {
    method: 'POST',
  });
}

export async function disableKillSwitch(): Promise<{ status: string; message: string }> {
  return fetchAPI<{ status: string; message: string }>('/control/kill-switch/disable', {
    method: 'POST',
  });
}

export async function cancelAllOrders(): Promise<CancelOrdersResponse> {
  return fetchAPI<CancelOrdersResponse>('/control/orders/cancel-all', {
    method: 'POST',
  });
}

export async function getOpenOrders(): Promise<OpenOrdersResponse> {
  return fetchAPI<OpenOrdersResponse>('/control/orders/open');
}

export async function getSchedulerStatus(): Promise<SchedulerStatus> {
  return fetchAPI<SchedulerStatus>('/control/scheduler/status');
}

