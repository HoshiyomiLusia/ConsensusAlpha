export type Action = "BUY" | "SELL" | "HOLD";
export type AgentRole = "market_analyst" | "risk_manager" | "contrarian_critic" | "execution_specialist" | "chairperson";

export type AgentLLMConfig = {
  role: AgentRole;
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  enabled: boolean;
};

export type Settings = {
  app_env: string;
  api_auth_enabled: boolean;
  has_api_auth_token: boolean;
  broker_provider: "mock" | "webull";
  trading_mode: "paper" | "live";
  enable_live_trading: boolean;
  webull_env: "test" | "production";
  webull_region: string;
  webull_account_id: string;
  webull_trading_endpoint: string;
  webull_market_data_endpoint: string;
  webull_trading_endpoint_test: string;
  webull_market_data_endpoint_test: string;
  webull_trading_endpoint_production: string;
  webull_market_data_endpoint_production: string;
  has_webull_app_key: boolean;
  has_webull_app_secret: boolean;
  llm_provider: string;
  llm_model: string;
  llm_base_url: string;
  has_llm_api_key: boolean;
  llm_agent_configs: AgentLLMConfig[];
  mock_agent_action: Action | "";
  max_position_pct: number;
  max_single_trade_risk_pct: number;
  max_daily_loss_pct: number;
  min_agent_confidence: number;
  trade_cooldown_seconds: number;
  max_order_price_deviation_pct: number;
  live_preview_ttl_seconds: number;
  max_daily_live_order_count: number;
  max_daily_live_notional: string;
  regular_trading_hours_only: boolean;
};

export type ProviderStatus = {
  provider: "mock" | "webull";
  healthy: boolean;
  environment: string;
  trading_mode: string;
  account_id: string | null;
  message: string;
  details: Record<string, unknown>;
};

export type ConferenceListItem = {
  conference_id: string;
  symbol: string;
  final_action: Action;
  consensus_reached: boolean;
  risk_approved: boolean | null;
  order_id: string | null;
  live_preview_id: string | null;
  created_at: string;
};

export type AgentOpinion = {
  agent_id: string;
  role: string;
  symbol: string;
  action: Action;
  confidence: number;
  thesis: string;
  concerns: string[];
  blocking_concerns: string[];
  suggested_max_position_pct: number | null;
  suggested_stop_loss_pct: number | null;
  prompt_version: string | null;
};

export type RiskCheck = {
  name: string;
  passed: boolean;
  reason: string;
  data: Record<string, unknown>;
};

export type ModelUsageEvent = {
  role: string;
  operation: string;
  provider: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated: boolean;
  prompt_version: string | null;
};

export type ConferenceDetail = {
  conference_id: string;
  symbol: string;
  snapshot: null | {
    symbol: string;
    asset_type: string;
    price: string;
    open: string | null;
    high: string | null;
    low: string | null;
    previous_close: string | null;
    volume: number | null;
    timestamp: string;
    source: string;
  };
  opinions: AgentOpinion[];
  chairperson_summary: string;
  consensus_result: {
    final_action: Action;
    consensus_reached: boolean;
    consensus_reason: string;
    started_at: string;
    completed_at: string;
  };
  risk_decision: null | {
    approved: boolean;
    reason: string;
    checks: RiskCheck[];
    max_quantity: string | null;
    max_notional: string | null;
  };
  model_usage: null | {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
    estimated: boolean;
    events: ModelUsageEvent[];
  };
  order_result: null | Record<string, unknown>;
  live_preview: null | LivePreview;
};

export type PaperOrder = {
  order_id: string;
  client_order_id: string;
  conference_id: string | null;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: string;
  order_type: "MARKET" | "LIMIT";
  fill_price: string;
  notional: string;
  status: string;
  mode: "paper";
  created_at: string;
};

export type LivePreview = {
  preview_id: string;
  client_order_id: string;
  conference_id: string | null;
  symbol: string;
  side: "BUY" | "SELL";
  quantity: string;
  order_type: "MARKET" | "LIMIT";
  limit_price: string | null;
  estimated_notional: string | null;
  status: string;
  account_id: string;
  environment: string;
  created_at: string;
  confirmed_at: string | null;
};

export type ProductionReadinessCheck = {
  name: string;
  passed: boolean;
  severity: "blocker" | "warning";
  summary: string;
  details: Record<string, unknown>;
};

export type ProductionReadiness = {
  ready: boolean;
  live_trading_ready: boolean;
  checks: ProductionReadinessCheck[];
};

export type Position = {
  symbol: string;
  asset_type: string;
  quantity: string;
  average_price: string;
  market_value: string;
  side: string;
};

export type CandidateScanItem = {
  symbol: string;
  asset_type: "equity" | "etf";
  snapshot: {
    symbol: string;
    asset_type: string;
    price: string;
    open: string | null;
    high: string | null;
    low: string | null;
    previous_close: string | null;
    volume: number | null;
    timestamp: string;
    source: string;
  };
  change_pct: number;
  intraday_range_pct: number;
  volume: number | null;
  score: number;
  reasons: string[];
};

export type MarketProposal = {
  symbol: string;
  asset_type: "equity" | "etf";
  proposed_action: Action;
  confidence: number;
  thesis: string;
  risks: string[];
  suggested_max_notional: string;
  source: string;
  rank: number;
  scan_score: number;
};

export type ProposalRunPayload = {
  symbols: string[];
  max_proposals: number;
  max_notional: string;
  use_llm: boolean;
};

export type ProposalRunResponse = {
  proposal_run_id: string;
  created_at: string;
  candidate_count: number;
  proposals: MarketProposal[];
  scanned: CandidateScanItem[];
  used_llm: boolean;
  llm_provider: string;
  message: string;
};

export type ProposalConferenceItem = {
  conference_id: string;
  symbol: string;
  final_action: Action;
  consensus_reached: boolean;
  risk_approved: boolean | null;
  created_at: string;
};

export type ProposalRunDetail = ProposalRunResponse & {
  conferences: ProposalConferenceItem[];
};

export type ProposalListItem = {
  proposal_run_id: string;
  created_at: string;
  candidate_count: number;
  proposal_count: number;
  used_llm: boolean;
  llm_provider: string;
};

export type AuditEvent = {
  event_id: string;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  summary: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type RunConferencePayload = {
  symbol: string;
  asset_type: "equity" | "etf";
  max_notional: string;
  order_type: "MARKET" | "LIMIT";
  limit_price?: string | null;
  mock_agent_action?: Action | null;
  proposal_run_id?: string | null;
};

export type RunConferenceResponse = {
  conference_id: string;
  symbol: string;
  final_action: Action;
  consensus_reached: boolean;
  risk_approved: boolean;
  order_id: string | null;
  live_preview_id: string | null;
};

export type DecisionRunPayload = {
  symbols: string[];
  max_proposals: number;
  max_notional: string;
  use_llm: boolean;
  order_type: "MARKET" | "LIMIT";
  limit_price?: string | null;
};

export type PortfolioReviewAction = "KEEP" | "ADD" | "REDUCE" | "EXIT" | "STOP_LOSS" | "TAKE_PROFIT";

export type PortfolioReviewItem = {
  symbol: string;
  asset_type: "equity" | "etf";
  quantity: string;
  average_price: string;
  market_value: string;
  last_price: string;
  unrealized_pnl_pct: string;
  review_action: PortfolioReviewAction;
  proposed_action: Action;
  priority_score: number;
  thesis: string;
  risk_notes: string[];
  suggested_max_notional: string;
};

export type DecisionPlanItem = {
  source: "portfolio_review" | "opportunity_scan";
  symbol: string;
  asset_type: "equity" | "etf";
  intent: string;
  proposed_action: Action;
  confidence: number;
  priority_score: number;
  thesis: string;
  suggested_max_notional: string;
  conference_id: string | null;
  final_action: Action | null;
  risk_approved: boolean | null;
  order_id: string | null;
  live_preview_id: string | null;
};

export type DecisionPlan = {
  plan_id: string;
  summary: string;
  next_step: string;
  selected_source: "portfolio_review" | "opportunity_scan";
  selected_symbol: string;
  selected_intent: string;
  final_action: Action;
  order_required: boolean;
  risk_approved: boolean;
  order_id: string | null;
  live_preview_id: string | null;
  portfolio_review_count: number;
  opportunity_count: number;
  items: DecisionPlanItem[];
};

export type DecisionRunResponse = {
  proposal_run: ProposalRunResponse;
  portfolio_review: PortfolioReviewItem[];
  decision_plan: DecisionPlan;
  selected_proposal: MarketProposal;
  conference: RunConferenceResponse;
};

export type ResetPaperStateResponse = {
  message: string;
  deleted: Record<string, number>;
};

export type SettingsUpdatePayload = Partial<{
  app_env: string;
  api_auth_enabled: boolean;
  api_auth_token: string;
  broker_provider: "mock" | "webull";
  trading_mode: "paper" | "live";
  enable_live_trading: boolean;
  webull_env: "test" | "production";
  webull_app_key: string;
  webull_app_secret: string;
  webull_region: string;
  webull_account_id: string;
  webull_trading_endpoint_test: string;
  webull_market_data_endpoint_test: string;
  webull_trading_endpoint_production: string;
  webull_market_data_endpoint_production: string;
  llm_provider: string;
  llm_model: string;
  llm_api_key: string;
  llm_base_url: string;
  llm_agent_configs: Array<{
    role: AgentRole;
    provider: string;
    model: string;
    base_url: string;
    api_key?: string;
    enabled: boolean;
  }>;
  mock_agent_action: Action | "";
  max_position_pct: number;
  max_single_trade_risk_pct: number;
  max_daily_loss_pct: number;
  min_agent_confidence: number;
  trade_cooldown_seconds: number;
  max_order_price_deviation_pct: number;
  live_preview_ttl_seconds: number;
  max_daily_live_order_count: number;
  max_daily_live_notional: string;
  regular_trading_hours_only: boolean;
}>;

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
const API_TOKEN_STORAGE_KEY = "consensusalpha.api_token";

export function getApiToken(): string {
  return window.localStorage.getItem(API_TOKEN_STORAGE_KEY) ?? "";
}

export function setApiToken(token: string): void {
  const trimmed = token.trim();
  if (trimmed) {
    window.localStorage.setItem(API_TOKEN_STORAGE_KEY, trimmed);
  } else {
    window.localStorage.removeItem(API_TOKEN_STORAGE_KEY);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getApiToken();
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init?.headers ?? {})
    },
    ...init
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = body.detail?.message ?? body.detail ?? response.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Record<string, unknown>>("/health"),
  settings: () => request<Settings>("/settings"),
  updateSettings: (payload: SettingsUpdatePayload) =>
    request<Settings>("/settings", {
      method: "PATCH",
      body: JSON.stringify(payload)
    }),
  providerStatus: () => request<ProviderStatus>("/provider/status"),
  productionReadiness: () => request<ProductionReadiness>("/production/readiness"),
  runDecision: (payload: DecisionRunPayload, init?: Pick<RequestInit, "signal">) =>
    request<DecisionRunResponse>("/decision/run", {
      method: "POST",
      body: JSON.stringify(payload),
      ...init
    }),
  proposals: () => request<ProposalListItem[]>("/proposals"),
  proposal: (id: string) => request<ProposalRunDetail>(`/proposals/${id}`),
  runProposals: (payload: ProposalRunPayload) =>
    request<ProposalRunResponse>("/proposals/run", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  conferences: () => request<ConferenceListItem[]>("/conference"),
  conference: (id: string) => request<ConferenceDetail>(`/conference/${id}`),
  runConference: (payload: RunConferencePayload) =>
    request<RunConferenceResponse>("/conference/run", {
      method: "POST",
      body: JSON.stringify(payload)
    }),
  paperOrders: () => request<PaperOrder[]>("/orders/paper"),
  livePreviews: () => request<LivePreview[]>("/orders/live/previews"),
  rejectLivePreview: (previewId: string) =>
    request<LivePreview>(`/orders/live/${previewId}/reject`, { method: "POST" }),
  confirmLivePreview: (previewId: string, body: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/orders/live/${previewId}/confirm`, {
      method: "POST",
      body: JSON.stringify(body)
    }),
  positions: () => request<Position[]>("/portfolio/positions"),
  auditEvents: () => request<AuditEvent[]>("/audit"),
  resetTestPaperState: () =>
    request<ResetPaperStateResponse>("/test/paper/reset", {
      method: "POST"
    })
};
