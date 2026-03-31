/** Typed API client for TradeOS backend. */

const BASE = '/api'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const token = localStorage.getItem('tradeos_token')
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`)
  const json = await res.json()
  if (!json.success) throw new Error(json.error ?? 'Unknown API error')
  return json.data as T
}

export const api = {
  // Signals
  getLiveSignals:    ()                            => request<Signal[]>('GET', '/signals/live'),
  getSignalHistory:  (page = 1, pageSize = 50)    => request<PagedResult<Signal>>('GET', `/signals/history?page=${page}&pageSize=${pageSize}`),
  recordOutcome:     (id: string, outcome: string, pnlPips?: number, rrActual?: number) =>
    request<boolean>('POST', `/signals/${id}/outcome?outcome=${outcome}${pnlPips ? `&pnlPips=${pnlPips}` : ''}${rrActual ? `&rrActual=${rrActual}` : ''}`),

  // Theories
  listTheories:      ()                            => request<Theory[]>('GET', '/theories'),
  getTheory:         (id: string)                  => request<TheoryDetail>('GET', `/theories/${id}`),
  createTheory:      (body: CreateTheoryBody)      => request<Theory>('POST', '/theories', body),
  updateTheory:      (id: string, body: CreateTheoryBody) => request<Theory>('PUT', `/theories/${id}`, body),
  deleteTheory:      (id: string)                  => request<boolean>('DELETE', `/theories/${id}`),
  getVersions:       (id: string)                  => request<TheoryVersion[]>('GET', `/theories/${id}/versions`),
  rollbackTheory:    (id: string, v: number)       => request<Theory>('POST', `/theories/${id}/rollback/${v}`),
  addFactor:         (id: string, body: unknown)   => request<unknown>('POST', `/theories/${id}/factors`, body),
  removeFactor:      (id: string, factorId: string) => request<boolean>('DELETE', `/theories/${id}/factors/${factorId}`),

  // Patterns
  listPatterns:      ()                            => request<Pattern[]>('GET', '/patterns'),
  createPattern:     (body: unknown)               => request<Pattern>('POST', '/patterns', body),
  deletePattern:     (id: string)                  => request<boolean>('DELETE', `/patterns/${id}`),

  // Trade Log
  listTrades:        (page = 1, pageSize = 50, instrument?: string) =>
    request<PagedResult<Trade>>('GET', `/trades?page=${page}&pageSize=${pageSize}${instrument ? `&instrument=${instrument}` : ''}`),
  getTrade:          (id: string)                  => request<Trade>('GET', `/trades/${id}`),
  getRecap:          (instrument?: string)         => request<TradeRecap>('GET', `/trades/recap${instrument ? `?instrument=${instrument}` : ''}`),

  // Backtest
  runBacktest:          (body: RunBacktestRequest) => request<string>('POST', '/backtest/run', body),
  listSessions:         (theoryId?: string)        => request<BacktestSession[]>('GET', `/backtest/sessions${theoryId ? `?theoryId=${theoryId}` : ''}`),
  getResults:           (id: string)               => request<BacktestResultResponse>('GET', `/backtest/sessions/${id}/results`),
  getBacktestTrades:    (id: string)               => request<BacktestTradeRecord[]>('GET', `/backtest/sessions/${id}/trades`),
  deleteBacktestSession:(id: string)               => request<boolean>('DELETE', `/backtest/sessions/${id}`),

  // HMM
  trainHmm:          (body: unknown)               => request<string>('POST', '/hmm/train', body),
  listHmmModels:     ()                            => request<HmmModel[]>('GET', '/hmm/models'),
  classifyState:     (instrument: string, tf: string) =>
    request<ClassifyResult>('GET', `/hmm/classify?instrument=${instrument}&timeframe=${tf}`),
  hmmStateProfile:   (instrument: string, tf: string) =>
    request<HmmStateProfile>('GET', `/hmm/state-profile?instrument=${instrument}&timeframe=${tf}&recentBars=60`),

  // Bayesian
  getProbability:    (theoryId: string, instrument: string, tf: string, seqRepr: string) =>
    request<ProbabilityResult>('GET', `/bayes/probability?theoryId=${theoryId}&instrument=${instrument}&timeframe=${tf}&seqRepr=${seqRepr}`),

  // Auth
  login: (username: string, password: string) =>
    fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }).then(async r => {
      const j = await r.json()
      if (!r.ok || !j.success) throw new Error(j.error ?? 'Login failed')
      return j.data as LoginResponse
    }),

  // Evaluate theory (trigger EvaluateTheoryAsync)
  evaluateTheory: (theoryId: string, instrument: string, timeframe: string) =>
    request<EvaluateResult>('POST', '/signals/evaluate', { theoryId, instrument, timeframe }),

  // OHLC Data Store
  ohlcDataStatus: () =>
    request<{ syncs: OhlcSyncStatus[]; count: number }>('GET', '/ohlc-data/status'),
  ohlcDataSync: (instrument?: string, timeframe?: string) =>
    request<{ results: OhlcSyncResult[]; total_bars_added: number }>('POST', '/ohlc-data/sync', { instrument, timeframe }),

  // Signal Engine (live candle loop)
  engineStart:  (theoryId: string, timeframe?: string, autoExecute?: boolean, volume?: number) =>
    request<EngineStartResult>('POST', '/engine/start', { theoryId, timeframe, autoExecute, volume }),
  engineStop:   (sessionId: string) =>
    request<unknown>('POST', '/engine/stop', { sessionId }),
  engineStatus: () =>
    request<EngineStatusResult>('GET', '/engine/status'),
  engineLastSignal: (symbol: string) =>
    request<HmmAdvisory>('GET', `/engine/last-signal?symbol=${encodeURIComponent(symbol)}`),

  // Aggressive Engine
  aggressiveStart:  (body: AggressiveStartRequest) =>
    request<AggressiveStartResult>('POST', '/aggressive/start', body),
  aggressiveStop:   (sessionId: string) =>
    request<unknown>('POST', '/aggressive/stop', { sessionId }),
  aggressiveStatus: () =>
    request<AggressiveStatusResult>('GET', '/aggressive/status'),

  // Smart Aggressive Engine
  smartStart:  (body: SmartStartRequest) =>
    request<SmartStartResult>('POST', '/smart-aggressive/start', body),
  smartStop:    (sessionId: string) =>
    request<unknown>('POST', '/smart-aggressive/stop', { sessionId }),
  smartResumeAi:(sessionId: string) =>
    request<unknown>('POST', '/smart-aggressive/resume-ai', { sessionId }),
  smartStatus: () =>
    request<SmartStatusResult>('GET', '/smart-aggressive/status'),
  smartLogs:   (sessionId?: string, symbol?: string, limit = 200) =>
    request<SmartTradeLog[]>('GET', `/smart-aggressive/logs?limit=${limit}${sessionId ? `&sessionId=${sessionId}` : ''}${symbol ? `&symbol=${symbol}` : ''}`),
  smartStats:  (sessionId?: string) =>
    request<SmartTradeStats>('GET', `/smart-aggressive/stats${sessionId ? `?sessionId=${sessionId}` : ''}`),

  // Cascade Engine
  cascadeStart:  (body: CascadeStartRequest)  => request<{ session_id: string; status: string }>('POST', '/cascade/start', {
    symbol:               body.symbol,
    initialBatch:         body.initialBatch,
    topupBatch:           body.topupBatch,
    volume:               body.volume,
    profitTarget:         body.profitTarget,
    hardSlPips:           body.hardSlPips,
    slLossMultiplier:     body.slLossMultiplier,
    maxPositions:         body.maxPositions,
    evalInterval:         body.evalInterval,
    mcLevelPct:           body.mcLevelPct,
    safetyMultiplier:     body.safetyMultiplier,
    emergencyMultiplier:  body.emergencyMultiplier,
    maxSessionLossUsd:    body.maxSessionLossUsd,
    maxDrawdownFromPeak:  body.maxDrawdownFromPeak,
  }),
  cascadeStop:   (sessionId: string)           => request<unknown>('POST', '/cascade/stop', { sessionId }),
  cascadeStatus: ()                            => request<CascadeStatusResult>('GET', '/cascade/status'),

  // Analysis (live alert log)
  getMultiTfAnalysis: (instrument: string, timeframes: string[]) =>
    request<AlertItem[]>('POST', '/analysis/multi-tf', { instrument, timeframes }),

  // Theory detail
  getTheoryDetail: (id: string) => request<TheoryDetail>('GET', `/theories/${id}`),

  // MT5
  mt5Connect:    (body: MT5ConnectRequest)  => request<MT5AccountInfo>('POST', '/mt5/connect', body),
  mt5Account:    ()                         => request<MT5AccountInfo>('GET', '/mt5/account'),
  mt5Order:      (body: MT5OrderRequest)    => request<MT5OrderResult>('POST', '/mt5/order', body),
  mt5Close:      (body: MT5CloseRequest)    => request<MT5CloseResult>('POST', '/mt5/close', body),
  mt5CloseAll:   (filter: 'all' | 'profit' | 'loss') => request<MT5CloseAllResult>('POST', '/mt5/close-all', { filter }),
  mt5Positions:  ()                         => request<MT5Position[]>('GET', '/mt5/positions'),
  mt5Disconnect: ()                         => request<unknown>('DELETE', '/mt5/disconnect'),
}

// ── Types ──────────────────────────────────────────────────────────────────

export interface Signal {
  tradeLogId: string
  theoryId: string
  theoryName: string
  instrument: string
  timeframe: string
  direction: 'LONG' | 'SHORT'
  entryPrice: number | null
  slPrice: number | null
  tpPrice: number | null
  compositeScore: number
  pWin: number
  confidenceTier: string
  stateSeqRepr: string
  decision: 'SIGNAL' | 'WATCH'
  signalTime: string
}

export interface Theory {
  id: string
  name: string
  description: string | null
  instrument: string
  direction: string
  threshold: number
  minConfidence: number
  version: number
  isActive: boolean
  createdAt: string
}

export interface TheoryDetail { theory: Theory; factors: TheoryFactor[] }
export interface TheoryFactor { id: string; factorCode: string; factorType: string; decisionPoint: number; isRequired: boolean; timeframe?: string }
export interface TheoryVersion { id: string; versionNumber: number; changeNotes: string | null; winRateAtSave: number | null; savedAt: string }
export interface CreateTheoryBody { name: string; description?: string; instrument: string; direction: string; threshold: number; minConfidence: number }

export interface Pattern { id: string; code: string; name: string; description?: string | null; patternType: string; stateSeqRepr?: string; timeframe?: string; source: string }
export interface Trade { id: string; theoryId: string; instrument: string; timeframe: string; direction: string; compositeScore: number; pWinAtSignal?: number; outcome?: string; pnlPips?: number; signalTime: string }
export interface TradeRecap { total: number; wins: number; losses: number; breakEven: number; winRate: number; totalPips: number }
export interface BacktestSession {
  id: string; theoryId: string; instrument: string; timeframe: string
  status: string; createdAt: string; completedAt?: string
  slType: string; slValue: number; tpType: string; tpValue: number; maxHoldBars: number
}
export interface BacktestResultStats {
  totalSignals: number; wins: number; losses: number; breakeven: number
  winRate: number; profitFactor: number; sharpeRatio: number; sortinoRatio: number
  maxDrawdown: number; avgRr: number; totalPips: number
  equityCurve: number[]; stateDistribution: Record<string, number>
  bestSeqRepr?: string; worstSeqRepr?: string
}
export interface BacktestResultResponse { session: BacktestSession; result: BacktestResultStats | null }
export interface BacktestTradeRecord {
  id: string; sessionId: string; barIndex: number; time: string
  direction: string; entry: number; sl: number; tp: number
  slType: string; tpType: string; atr: number
  outcome: string; exitBar: number; exitPrice: number
  pnlPips: number; rrAchieved: number; seqRepr?: string; similarity: number
}
export interface RunBacktestRequest {
  theoryId: string; instrument: string; timeframe: string
  dateFrom: Date; dateTo: Date; dataSource: 'db' | 'mt5'
  slType: 'atr' | 'fixed'; slValue: number
  tpType: 'atr' | 'fixed'; tpValue: number
  maxHoldBars: number
}
export interface HmmModel { id: string; instrument: string; timeframe: string; version: string; nStates: number; bicScore?: number; isActive: boolean }
export interface ClassifyResult { state: number; stateLabel: string; modelVersion: string }
export interface HmmStateFeature { name: string; desc: string; value: number }
export interface HmmStateInfo { state: number; label: string; frequency: number; features: HmmStateFeature[] }
export interface HmmRecentBar { bar_index: number; time: string; state: number; label: string }
export interface HmmStateProfile {
  instrument: string; timeframe: string; model_version: string; n_states: number
  states: HmmStateInfo[]; recent_sequence: HmmRecentBar[]
}
export interface ProbabilityResult { pWin: number; total: number; wins: number; confidenceTier: string }
export interface PagedResult<T> { items: T[]; total: number; page: number; pageSize: number }

export interface OhlcSyncStatus {
  instrument: string; timeframe: string
  last_bar: string | null; total_bars: number
  last_sync: string | null; status: string; error_msg: string | null
}
export interface OhlcSyncResult { instrument: string; timeframe: string; bars_added: number; status: string; error?: string }

export interface LoginResponse { token: string; username: string; expiresAt: string }
export interface EngineStartResult { session_id: string; status: string; instrument: string; timeframe: string }
export interface EngineSession {
  session_id: string; theory_id: string; instrument: string; timeframe: string
  direction: string; status: 'running' | 'stopped' | 'error'
  started_at: string; last_checked: string | null; last_signal: string | null
  signals_fired: number; bars_evaluated: number; no_signal_warning: boolean
  error_msg: string | null
}
export interface EngineStatusResult { sessions: EngineSession[] }
export interface EvaluateResult { decision: string; compositeScore: number; pWin: number; stateSeqRepr: string; tradeLogId: string | null }

// MT5 types
export interface MT5ConnectRequest { login: number; password: string; server: string }
export interface MT5AccountInfo { login: number; name: string; server: string; currency: string; balance: number; equity: number; margin: number; freeMargin: number; profit: number; leverage: number; tradeAllowed: boolean }
export interface MT5OhlcBar { time: string; open: number; high: number; low: number; close: number; tickVolume: number }
export interface MT5OhlcResponse { symbol: string; timeframe: string; bars: MT5OhlcBar[] }
export interface MT5OrderRequest { symbol: string; action: 'BUY' | 'SELL'; volume: number; slPips?: number; tpPips?: number; comment?: string }
export interface MT5OrderResult { success: boolean; orderId: number; retcode: number; retcodeDesc: string; symbol: string; action: string; volume: number; price: number; sl: number; tp: number; comment: string }
export interface MT5Position { ticket: number; symbol: string; type: 'BUY' | 'SELL'; volume: number; openPrice: number; sl: number; tp: number; profit: number; swap: number; comment: string; openTime: string }
export interface MT5CloseRequest { ticket: number; volume?: number; comment?: string }
export interface MT5CloseResult { success: boolean; ticket: number; retcode: number; retcodeDesc: string; profit: number }
export interface MT5CloseAllResult { closed: number; failed: number; totalProfit: number }

// Aggressive Engine types
export interface HmmAdvisory {
  found: boolean
  symbol: string
  direction: string        // LONG | SHORT
  similarity: number
  age_s: number
  timeframe: string
  session_id: string
}

export interface AggressiveStartRequest {
  symbol: string; direction: string; layers: number
  volume: number; profitTarget: number; slPips: number; tpPips: number
  flipMode: string; flipPercentile: number; flipAfter: number; lookbackBars: number
  // Cascade merge + MCGuard + per-position SL
  trendGuided: boolean
  mcGuard: boolean; mcLevelPct: number; safetyMultiplier: number; emergencyMultiplier: number
  slLossMultiplier: number
  slCooldownSec: number
  maxSessionLossUsd: number; maxDrawdownFromPeak: number
  // HMM Gate (default false)
  hmmGateEnabled: boolean; hmmCooldownSec: number
  autoDirectionHmm: boolean
  // Limit Order (default false)
  limitAtrMult: number; pendingExpirySec: number
}
export interface AggressiveStartResult { session_id: string; status: string }
export interface AggressiveSession {
  session_id: string; symbol: string; direction: string; current_direction: string
  layers: number; volume: number; profit_target: number
  flip_mode: string; flip_percentile: number; flip_after: number; lookback_bars: number
  consecutive_tp: number; total_flips: number
  // Cascade merge + MCGuard
  trend_guided: boolean
  mc_guard: boolean; mc_level_pct: number; safety_multiplier: number; emergency_multiplier: number
  mc_status: 'OK' | 'CAUTION' | 'WARNING' | 'DANGER' | 'EMERGENCY'
  sl_loss_multiplier: number
  sl_cooldown_sec: number; sl_cooldown_remaining: number
  max_session_loss_usd: number; max_drawdown_from_peak: number
  peak_profit: number; floating_pnl: number; total_net: number
  next_recommendation: string
  consecutive_connection_failures: number
  active: boolean; open_positions: number; active_tickets: number[]
  total_opened: number; total_closed_win: number; total_closed_other: number
  total_closed_sl: number; total_closed_emergency: number
  total_profit: number; last_action: string; error: string | null; uptime_s: number
  // HMM Gate
  hmm_gate_enabled: boolean; hmm_cooldown_sec: number
  hmm_cooldown_remaining: number; hmm_cooldown_reason: string; hmm_vote_last: string
  auto_direction_hmm: boolean
  // Limit Order
  limit_atr_mult: number; pending_expiry_sec: number; pending_orders: number
}
export interface AggressiveStatusResult { sessions: AggressiveSession[] }

// Smart Aggressive Engine types
export interface SmartStartRequest {
  symbol: string; timeframe: string; maxLayers: number
  openPerInterval: number; evalIntervalS: number; volume: number
  tpAtrMult: number; slAtrMult: number; minAtr: number; maxAtr: number
  minConfidence: number
  allowShort: boolean
  aiEnabled: boolean; entriesPerDecision: number; maxCallsPerHour: number
}
export interface SmartStartResult { session_id: string; status: string; ai_enabled: boolean }
export interface SmartSession {
  session_id: string; symbol: string; timeframe: string
  max_layers: number; open_per_interval: number; eval_interval_s: number
  volume: number; tp_atr_mult: number; sl_atr_mult: number
  min_atr: number; max_atr: number
  active: boolean; open_positions: number; active_tickets: number[]
  total_opened: number; total_closed_win: number; total_closed_loss: number; total_closed_other: number
  total_profit: number; last_action: string; last_direction: string; last_score: number
  allow_short: boolean
  error: string | null; uptime_s: number
  // AI fields
  ai_enabled: boolean; ai_status: string
  entries_per_decision: number; max_calls_per_hour: number
  ai_calls_this_hour: number; ai_calls_total: number
  ai_last_reasoning: string; ai_last_decision: string; ai_last_confidence: number
}
export interface SmartStatusResult { sessions: SmartSession[] }
export interface SmartTradeLog {
  id: string; sessionId: string; symbol: string
  direction: string; directionScore: number
  atrValue: number | null; hmmState: number | null; hmmStateLabel: string | null; hmmConfidence: number | null
  voteHmm: number | null; voteEma: number | null; voteMomentum: number | null
  entryPrice: number | null; tpPrice: number | null; slPrice: number | null
  mt5Ticket: number | null; exitPrice: number | null; profitUsd: number | null
  outcome: string | null; closeReason: string | null; durationS: number | null
  openedAt: string; closedAt: string | null
  // AI fields
  aiEnabled: boolean; llmModel: string | null; llmReasoning: string | null
  llmConfidence: number | null; llmLatencyMs: number | null; llmSkipReason: string | null
}
export interface SmartTradeStats {
  total: number; wins: number; losses: number; breakEven: number; open: number
  winRate: number; totalProfitUsd: number; avgProfitUsd: number; avgDurationS: number
}

// Cascade Engine types
export interface CascadeStartRequest {
  symbol: string
  initialBatch: number; topupBatch: number
  volume: number; profitTarget: number; hardSlPips: number; slLossMultiplier: number
  maxPositions: number; evalInterval: number
  mcLevelPct: number; safetyMultiplier: number; emergencyMultiplier: number
  maxSessionLossUsd: number; maxDrawdownFromPeak: number
}
export interface CascadeBatch {
  batch_id: string; direction: string; open: number
  closed_tp: number; closed_sl: number; opened_at: string
}
export type McStatus = 'OK' | 'CAUTION' | 'WARNING' | 'DANGER' | 'EMERGENCY'
export interface CascadeSession {
  session_id: string; symbol: string
  initial_batch: number; topup_batch: number
  volume: number; profit_target: number; hard_sl_pips: number; sl_loss_multiplier: number
  max_positions: number; eval_interval: number
  mc_level_pct: number; safety_multiplier: number; emergency_multiplier: number
  max_session_loss_usd: number; max_drawdown_from_peak: number
  peak_profit: number; floating_pnl: number; total_net: number
  next_recommendation: string
  active: boolean; mc_status: McStatus; current_direction: string
  open_positions: number
  total_opened: number; total_closed_tp: number; total_closed_sl: number; total_closed_emergency: number
  total_profit: number; last_eval: string; last_action: string
  error: string | null; uptime_s: number
  batches: CascadeBatch[]
}
export interface CascadeStatusResult { sessions: CascadeSession[] }

export interface AlertItem {
  tf:         string   // "M1,M5,H1" (merged) | "--" (cross-TF)
  tag:        string
  severity:   'info' | 'warning' | 'danger' | 'divergence' | 'system'
  msg:        string
  confidence: number   // 0.0–1.0
  action:     'BUY' | 'SELL' | 'NEUTRAL'
}
