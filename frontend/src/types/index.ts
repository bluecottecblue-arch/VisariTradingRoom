// VisariTradingRoom — Tipi TypeScript condivisi

export type WorkflowStatus = 'VALID' | 'NEEDS_INPUT' | 'INVALID' | 'GENERATION_FAILED'
export type FinalVerdict =
  | 'REJECT'
  | 'NEEDS_RESEARCH'
  | 'PAPER_TRADE_ONLY'
  | 'LIMITED_LIVE_TEST'
  | 'PRODUCTION_CANDIDATE'

export interface UsageInfo {
  module: string
  model: string | null
  cache_hit: boolean
  billable: boolean
  system_chars: number
  prompt_chars: number
  estimated_input_tokens: number
  input_tokens: number
  output_tokens: number
  max_tokens: number
  estimated_cost_usd: number
}

export interface ValidationInfo {
  stage?: string
  blocking_ambiguities?: number
  blocking_required_inputs?: number
  blocking_issues?: number
  llm_reviewed?: boolean
  llm_skipped?: boolean
  ready_for_formalization?: boolean
  ready_for_generation?: boolean
  ready_for_download?: boolean
}

export interface PreflightStageEstimate {
  enabled: boolean
  estimated_input_tokens: number
  estimated_output_tokens: number
  max_tokens: number
  estimated_cost_usd: number
  reason: string
}

export interface RequiredInput {
  id: string
  field: string
  label: string
  why: string
  example: string
  source_text?: string
  blocking?: boolean
}

export interface StrategyIntake {
  name: string
  market: string
  analysis_timeframe: string
  execution_timeframe: string
  long_entry: string
  short_entry?: string
  invalidation: string
  stop_loss: string
  take_profit: string
  trailing_stop?: string
  risk_per_trade_pct: number
  max_daily_trades: number
  trading_hours_start: string
  trading_hours_end: string
  trading_days: string[]
  volatility_filter?: string
  trend_filter?: string
  context_filter?: string
  news_management?: string
  valid_trade_examples?: string
  invalid_trade_examples?: string
  additional_notes?: string
}

export interface Ambiguity {
  id: string
  original_text: string
  why_ambiguous: string
  severity: 'HIGH' | 'MEDIUM' | 'LOW'
  alternatives: AmbiguityAlternative[]
  field?: string
  blocking?: boolean
}

export interface AmbiguityAlternative {
  id: string
  description: string
  implementation: string
  tradeoffs: string
}

export interface CodeableRule {
  id: string
  description: string
  condition: string
  parameters?: Record<string, unknown>
}

export interface ParseResult {
  session_id: string
  status: WorkflowStatus
  validation_status: 'VALID' | 'INVALID'
  message: string
  structured_strategy: Record<string, unknown>
  ambiguities: Ambiguity[]
  required_inputs: RequiredInput[]
  codeable_rules: CodeableRule[]
  bias_warnings: string[]
  assumptions: string[]
  completeness_score: number
  can_proceed: boolean
  can_generate_code: boolean
  validation: ValidationInfo
  usage: UsageInfo
}

export interface PreflightResult {
  status: WorkflowStatus
  message: string
  blocking_items: number
  completeness_score: number
  ambiguities: Ambiguity[]
  required_inputs: RequiredInput[]
  validation: ValidationInfo
  expected_stages: Record<'parse' | 'formalize' | 'botgen', PreflightStageEstimate>
  estimated_total_cost_usd: number
  next_recommended_action: string
}

export interface FormalSpec {
  session_id: string
  status: WorkflowStatus
  validation_status: 'VALID' | 'INVALID'
  message: string
  formal_spec: Record<string, unknown>
  state_machine: {
    states: string[]
    transitions: { from: string; to: string; condition: string }[]
  }
  parameters: Parameter[]
  non_optimizable: string[]
  assumptions: string[]
  ambiguities: Ambiguity[]
  required_inputs: RequiredInput[]
  can_generate_code: boolean
  validation: ValidationInfo
  usage: UsageInfo
}

export interface Parameter {
  id: string
  name: string
  description: string
  type: 'int' | 'double' | 'bool' | 'string'
  default_value: unknown
  min_value?: unknown
  max_value?: unknown
  optimize: boolean
  why_not_optimize?: string
}

export interface BacktestMetrics {
  total_trades: number
  winning_trades: number
  losing_trades: number
  hit_rate: number
  avg_win_r: number
  avg_loss_r: number
  expectancy_r: number
  profit_factor: number
  sharpe_ratio: number
  sortino_ratio: number
  calmar_ratio: number
  max_drawdown_pct: number
  max_consecutive_losses: number
  total_return_pct: number
  final_capital: number
  equity_curve: number[]
  data_quality_warnings?: string[]
}

export interface BiasWarning {
  type: string
  severity: 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW'
  description: string
  what_it_means: string
  how_to_mitigate: string
  detected_automatically: boolean
}

export interface BiasCheckResult {
  warnings: BiasWarning[]
  critical_count: number
  high_count: number
  overall_reliability: string
  can_trust_results: boolean
  recommendation: string
}

export interface StatisticalValidationResult {
  sample_rules: {
    trade_count: number
    hard_minimum_trades: number
    recommended_trades: number
    strong_trades: number
    status: 'TOO_SMALL' | 'LIMITED' | 'ADEQUATE' | 'STRONG'
  }
  confidence_intervals: {
    mean_return_per_trade_r: { estimate: number; ci_95_low: number; ci_95_high: number }
    hit_rate: { estimate: number; ci_95_low: number; ci_95_high: number }
    expectancy_r: { estimate: number; ci_95_low: number; ci_95_high: number }
    sharpe_like: { estimate: number; ci_95_low: number; ci_95_high: number }
  }
  bootstrap: {
    n_bootstrap: number
    mean_r: { p5: number; p50: number; p95: number }
    hit_rate: { p5: number; p50: number; p95: number }
    sharpe_like: { p5: number; p50: number; p95: number }
    positive_expectancy_probability: number
  }
  distribution_diagnostics: {
    skew: number
    kurtosis_excess: number
    tail_concentration: number
    median_r: number
    std_r: number
  }
  subperiod_stability: {
    periods: Array<{
      label: string
      trade_count: number
      expectancy_r: number
      hit_rate: number
      total_r: number
    }>
    stability_score: number
  }
  significance_proxy: {
    t_stat_like: number
    p_value_proxy: number
    confidence_label: string
    note: string
  }
  warnings: string[]
}

export interface RobustnessSuite {
  stress_scenarios: Array<{
    label: string
    spread_multiplier: number
    slippage_multiplier: number
    commission_multiplier: number
    total_return_pct: number
    expectancy_r: number
    max_drawdown_pct: number
    sharpe_ratio: number
    trade_count: number
  }>
  heatmap: Array<{
    spread_multiplier: number
    cells: Array<{
      slippage_multiplier: number
      total_return_pct: number
      expectancy_r: number
    }>
  }>
  cost_robustness_score: number
  parameter_fragility_score: number
  overfit_suspicion_score: number
  oos_degradation_score: number
  robustness_score: number
  summary: string
}

export interface RegimeAnalysisResult {
  by_regime: Array<{
    regime: string
    trend_regime: string
    volatility_regime: string
    trade_count: number
    expectancy_r: number
    win_rate: number
    drawdown_r: number
    contribution_to_total_r_pct: number
  }>
  dependence_score: number
  warning: string
  market_regime_distribution: Array<{
    regime: string
    bar_share: number
  }>
}

export interface RiskReviewResult {
  guards: {
    daily_drawdown_guard_pct: number
    equity_kill_switch_pct: number
    consecutive_losses_guard: number
    max_exposure_pct: number
  }
  metrics: {
    worst_daily_return_pct: number
    risk_concentration_pct: number
    risk_of_ruin_proxy: number
    variance_pressure_score: number
  }
  warnings: string[]
  risk_score: number
}

export interface FinalDecisionResult {
  verdict: FinalVerdict
  overall_score: number
  score_breakdown: Record<string, number>
  reasons: string[]
  blockers: string[]
  warnings: string[]
  generate_bot_allowed: boolean
  export_allowed: boolean
  confidence_label: string
  policy_snapshot?: Record<string, number>
}

export interface ResearchGovernanceResult {
  strategy_id: string
  strategy_version: number
  analysis_timestamp: string
  config_snapshot: Record<string, unknown>
  metrics_snapshot: Record<string, unknown>
  final_verdict: FinalVerdict
  reasons_for_verdict: string[]
  audit_trail: Record<string, unknown>
}

export interface BacktestResult {
  session_id?: string
  in_sample: BacktestMetrics
  out_of_sample: BacktestMetrics
  walk_forward?: {
    aggregated: {
      avg_sharpe_oos: number
      avg_return_oos: number
      avg_max_dd_oos: number
      pct_profitable_periods: number
    }
    wf_efficiency: number
    interpretation: string
  }
  monte_carlo?: {
    n_simulations: number
    final_capital: { p5: number; p25: number; median: number; p75: number; p95: number; mean: number }
    max_drawdown: { p5: number; p50: number; p95: number }
    prob_profit: number
    prob_ruin: number
    interpretation: string
  }
  bias_check: BiasCheckResult
  statistical_validation: StatisticalValidationResult
  robustness_suite: RobustnessSuite
  regime_analysis: RegimeAnalysisResult
  risk_review: RiskReviewResult
  final_decision: FinalDecisionResult
  research_governance: ResearchGovernanceResult
  data_info?: Record<string, unknown>
  methodology_notes?: string[]
}

export interface BotResult {
  session_id: string
  status: WorkflowStatus
  validation_status: 'VALID' | 'INVALID'
  message: string
  mql5_code: string
  documentation: string
  implementation_assumptions: string[]
  limitations_vs_discretionary: string[]
  required_inputs: RequiredInput[]
  code_validation: {
    is_valid: boolean
    checks: Record<string, boolean>
    errors: string[]
  }
  download_ready: boolean
  can_generate_code: boolean
  validation: ValidationInfo
  usage: UsageInfo
}
