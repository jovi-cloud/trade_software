/**
 * The Strategy Library -> Backtest workflow, as data.
 *
 * Everything the trader has configured on the way from the library to a run
 * lives in one serialisable object. Keeping it here, as pure functions over a
 * plain value, is what lets the state survive navigating away and back, and
 * lets the rules that matter (which explainability level to use, when to warn
 * about lowering it) be tested without rendering anything.
 *
 * The React-facing store is `workflowStore.ts`; this module never touches the
 * DOM or storage.
 */

import type { ParamValue } from '@/features/strategy-library/types'
import type { components } from '@/types/api'

export type ExplainLevel = components['schemas']['ExplainLevel']
export type LibraryStrategy = components['schemas']['LibraryStrategyRead']
export type BacktestRun = components['schemas']['BacktestRunRead']

/** Which kind of strategy the run form is configured for. */
export type StrategySource = 'library' | 'user'

export const DEFAULT_CAPITAL = '100000'
export const DEFAULT_COMMISSION = '0'
export const DEFAULT_SLIPPAGE = '0'
export const DEFAULT_MAX_BARS = '500'
export const DEFAULT_MAX_TRADES_PER_DAY = '1'
export const DEFAULT_ENTRY_WINDOW_START = '09:15'
export const DEFAULT_ENTRY_WINDOW_END = '15:25'
export const DEFAULT_STOP_LOSS_PERCENT = '2'
export const DEFAULT_STOP_LOSS_ATR = '2'
export const DEFAULT_SESSION_EXIT = '14:55'

export interface WorkflowState {
  source: StrategySource
  libraryStrategyId: string
  userStrategyId: string
  /** Parameter edits for the selected library strategy. */
  params: Record<string, ParamValue>
  datasetId: string
  /** Null means use the dataset's current (latest) version. */
  datasetVersionNumber: number | null
  /** Numeric fields stay strings so a half-typed value is not clobbered. */
  initialCapital: string
  commission: string
  slippage: string
  explainLevel: ExplainLevel
  /**
   * Whether the trader chose the explainability level themselves. Until they
   * do, the level follows the selected strategy's recommendation.
   */
  explainLevelChosen: boolean
  /** When true, only the first ``maxBars`` bars are replayed. */
  limitBars: boolean
  /** Numeric field kept as a string so a half-typed value is not clobbered. */
  maxBars: string
  skipTradesOnPriceAnomalyDays: boolean
  skipTradesOnIntradayAnomalies10pct: boolean
  skipTradesOnIntradayAnomalies20pct: boolean
  skipTradesOnCrossDayAnomalies10pct: boolean
  skipTradesOnCrossDayAnomalies20pct: boolean
  /** When true, cap new entries per exchange-local session day. */
  limitMaxTradesPerDay: boolean
  maxTradesPerDay: string
  limitEntryWindow: boolean
  entryWindowStart: string
  entryWindowEnd: string
  overrideStopLoss: boolean
  stopLossOverrideMode: 'percent' | 'atr' | 'disabled'
  stopLossValue: string
  enableSessionExit: boolean
  sessionExitAt: string
}

export function createInitialWorkflow(): WorkflowState {
  return {
    source: 'library',
    libraryStrategyId: '',
    userStrategyId: '',
    params: {},
    datasetId: '',
    datasetVersionNumber: null,
    initialCapital: DEFAULT_CAPITAL,
    commission: DEFAULT_COMMISSION,
    slippage: DEFAULT_SLIPPAGE,
    explainLevel: 'full',
    explainLevelChosen: false,
    limitBars: false,
    maxBars: DEFAULT_MAX_BARS,
    skipTradesOnPriceAnomalyDays: false,
    skipTradesOnIntradayAnomalies10pct: true,
    skipTradesOnIntradayAnomalies20pct: true,
    skipTradesOnCrossDayAnomalies10pct: true,
    skipTradesOnCrossDayAnomalies20pct: true,
    limitMaxTradesPerDay: false,
    maxTradesPerDay: DEFAULT_MAX_TRADES_PER_DAY,
    limitEntryWindow: false,
    entryWindowStart: DEFAULT_ENTRY_WINDOW_START,
    entryWindowEnd: DEFAULT_ENTRY_WINDOW_END,
    overrideStopLoss: false,
    stopLossOverrideMode: 'percent',
    stopLossValue: DEFAULT_STOP_LOSS_PERCENT,
    enableSessionExit: true,
    sessionExitAt: DEFAULT_SESSION_EXIT,
  }
}

/**
 * Point the workflow at a library strategy, keeping the run settings.
 *
 * Parameter edits are dropped when the strategy changes - they belong to the
 * strategy that declared them - but kept when it does not, which is what makes
 * "back to the library, then forward again" non-destructive.
 */
export function selectLibraryStrategy(
  state: WorkflowState,
  strategyId: string,
  params?: Record<string, ParamValue>,
): WorkflowState {
  const sameStrategy = state.libraryStrategyId === strategyId
  return {
    ...state,
    source: 'library',
    libraryStrategyId: strategyId,
    params: params ?? (sameStrategy ? state.params : {}),
    // A new strategy may recommend a different level; an untouched control
    // should follow it rather than keep the previous strategy's answer.
    explainLevelChosen: sameStrategy ? state.explainLevelChosen : false,
  }
}

/** Seed the workflow to re-run a saved result with the parameters it used. */
export function workflowFromRun(state: WorkflowState, run: BacktestRun): WorkflowState {
  const isLibraryRun = Boolean(run.library_strategy_id)
  return {
    ...state,
    source: isLibraryRun ? 'library' : 'user',
    libraryStrategyId: run.library_strategy_id ?? '',
    userStrategyId: isLibraryRun ? state.userStrategyId : run.strategy_id,
    params: (run.strategy_params ?? {}) as Record<string, ParamValue>,
    datasetId: run.dataset_id,
    datasetVersionNumber: run.dataset_version_number ?? null,
    initialCapital: String(run.initial_capital),
    commission: String(run.commission),
    slippage: String(run.slippage),
    explainLevel: run.explain_level ?? 'full',
    // Reproducing a run means reproducing what it collected, not re-deriving it.
    explainLevelChosen: true,
  }
}

/**
 * The level a run will actually use.
 *
 * An explicit choice always wins. Otherwise the strategy decides: one that
 * traces its conditions is worth collecting in full, because that trace is the
 * Decision Inspector's only input.
 */
export function resolveExplainLevel(
  state: WorkflowState,
  recommended: ExplainLevel | undefined,
): ExplainLevel {
  if (state.explainLevelChosen) return state.explainLevel
  return recommended ?? state.explainLevel
}

/**
 * Warn when the chosen level throws away a trace the strategy would produce.
 * Returns null when there is nothing to say.
 */
export function explainabilityWarning(
  level: ExplainLevel,
  supportsConditionTracing: boolean | undefined,
): string | null {
  if (!supportsConditionTracing || level === 'full') return null
  if (level === 'none') {
    return 'This strategy traces every condition it evaluates. With explainability off, the run records nothing for the Trade, Bar or Decision Inspectors.'
  }
  return 'This strategy traces every condition it evaluates. At this level the run records trades but not the per-bar decisions, so the Decision Inspector will be empty.'
}

/** Values the run form still needs before it can submit. */
export function missingRequirements(state: WorkflowState): string[] {
  const missing: string[] = []
  if (state.source === 'library' && !state.libraryStrategyId) missing.push('a library strategy')
  if (state.source === 'user' && !state.userStrategyId) missing.push('a strategy')
  if (!state.datasetId) missing.push('a dataset')
  return missing
}

export interface NumericSettings {
  initialCapital: number
  commission: number
  slippage: number
}

/** Parse the numeric run settings, or explain which one is unusable. */
export function parseNumericSettings(
  state: WorkflowState,
): { ok: true; values: NumericSettings } | { ok: false; error: string } {
  const initialCapital = Number(state.initialCapital)
  const commission = Number(state.commission)
  const slippage = Number(state.slippage)

  if (!Number.isFinite(initialCapital) || initialCapital <= 0) {
    return { ok: false, error: 'Initial capital must be a positive number.' }
  }
  if (!Number.isFinite(commission) || commission < 0) {
    return { ok: false, error: 'Commission must be zero or greater.' }
  }
  if (!Number.isFinite(slippage) || slippage < 0) {
    return { ok: false, error: 'Slippage must be zero or greater.' }
  }
  return { ok: true, values: { initialCapital, commission, slippage } }
}

/** Parse the optional bar limit, or explain what is wrong with it. */
export function parseMaxBars(
  state: WorkflowState,
): { ok: false; error: string } | { ok: true; value: number | null } {
  if (!state.limitBars) return { ok: true, value: null }
  const maxBars = Number(state.maxBars)
  if (!Number.isFinite(maxBars) || maxBars < 1 || !Number.isInteger(maxBars)) {
    return { ok: false, error: 'Bar limit must be a whole number of at least 1.' }
  }
  return { ok: true, value: maxBars }
}

/** Parse the optional daily entry cap, or explain what is wrong with it. */
export function parseMaxTradesPerDay(
  state: WorkflowState,
): { ok: false; error: string } | { ok: true; value: number | null } {
  if (!state.limitMaxTradesPerDay) return { ok: true, value: null }
  const maxTradesPerDay = Number(state.maxTradesPerDay)
  if (!Number.isFinite(maxTradesPerDay) || maxTradesPerDay < 1 || !Number.isInteger(maxTradesPerDay)) {
    return { ok: false, error: 'Max trades per day must be a whole number of at least 1.' }
  }
  return { ok: true, value: maxTradesPerDay }
}

const HHMM_PATTERN = /^([01]\d|2[0-3]):[0-5]\d$/

/** Parse the optional entry window, or explain what is wrong with it. */
export function parseEntryWindow(
  state: WorkflowState,
): { ok: false; error: string } | { ok: true; value: { start: string; end: string } | null } {
  if (!state.limitEntryWindow) return { ok: true, value: null }
  const start = state.entryWindowStart.trim()
  const end = state.entryWindowEnd.trim()
  if (!HHMM_PATTERN.test(start) || !HHMM_PATTERN.test(end)) {
    return {
      ok: false,
      error: 'Trading window times must use 24-hour HH:MM format (for example 09:15).',
    }
  }
  const startMinutes = Number(start.slice(0, 2)) * 60 + Number(start.slice(3, 5))
  const endMinutes = Number(end.slice(0, 2)) * 60 + Number(end.slice(3, 5))
  if (startMinutes > endMinutes) {
    return { ok: false, error: 'Trading window start must be at or before the end time.' }
  }
  return { ok: true, value: { start, end } }
}

export type StopLossOverrideInput = {
  mode: 'percent' | 'atr' | 'disabled'
  value?: number
}

/** Parse the optional stop-loss override for library strategy runs. */
export function parseStopLossOverride(
  state: WorkflowState,
): { ok: false; error: string } | { ok: true; value: StopLossOverrideInput | null } {
  if (!state.overrideStopLoss) return { ok: true, value: null }
  if (state.stopLossOverrideMode === 'disabled') {
    return { ok: true, value: { mode: 'disabled' } }
  }
  const value = Number(state.stopLossValue)
  if (!Number.isFinite(value) || value <= 0) {
    return { ok: false, error: 'Stop loss value must be a positive number.' }
  }
  if (state.stopLossOverrideMode === 'percent' && value > 25) {
    return { ok: false, error: 'Percent stop loss cannot exceed 25%.' }
  }
  if (state.stopLossOverrideMode === 'atr' && value > 10) {
    return { ok: false, error: 'ATR stop multiple cannot exceed 10.' }
  }
  return { ok: true, value: { mode: state.stopLossOverrideMode, value } }
}

export function parseSessionExit(
  state: WorkflowState,
): { ok: false; error: string } | { ok: true; value: { enabled: boolean; at: string } } {
  if (!state.enableSessionExit) {
    return { ok: true, value: { enabled: false, at: DEFAULT_SESSION_EXIT } }
  }
  const at = state.sessionExitAt.trim()
  if (!/^\d{1,2}:\d{2}$/.test(at)) {
    return { ok: false, error: 'Session exit time must be HH:MM (24-hour).' }
  }
  const [hours = 0, minutes = 0] = at.split(':').map(Number)
  if (hours > 23 || minutes > 59) {
    return { ok: false, error: 'Session exit time must be a valid 24-hour HH:MM value.' }
  }
  return {
    ok: true,
    value: { enabled: true, at: `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}` },
  }
}

export type ExecuteInput = components['schemas']['BacktestExecuteRequest']

/**
 * Turn the workflow into an execute request.
 *
 * A library run deliberately sends no `strategy_id`: the backend resolves (and
 * on the first run creates) the research container for that strategy, so
 * launching from the library needs no strategy record made by hand.
 */
export function toExecuteInput(
  state: WorkflowState,
  values: NumericSettings,
  explainLevel: ExplainLevel,
  maxBars: number | null,
  maxTradesPerDay: number | null,
  entryWindow: { start: string; end: string } | null,
  stopLossOverride: StopLossOverrideInput | null,
  sessionExit: { enabled: boolean; at: string },
): ExecuteInput {
  const shared = {
    dataset_id: state.datasetId,
    ...(state.datasetVersionNumber !== null
      ? { dataset_version: state.datasetVersionNumber }
      : {}),
    initial_capital: values.initialCapital,
    commission: values.commission,
    slippage: values.slippage,
    explain_level: explainLevel,
    ...(maxBars !== null ? { max_bars: maxBars } : {}),
    ...(maxTradesPerDay !== null ? { max_trades_per_day: maxTradesPerDay } : {}),
    ...(entryWindow !== null
      ? {
          entry_window_start: entryWindow.start,
          entry_window_end: entryWindow.end,
        }
      : {}),
    override_stop_loss: stopLossOverride !== null,
    ...(stopLossOverride !== null
      ? {
          stop_loss_override_mode: stopLossOverride.mode,
          ...(stopLossOverride.value !== undefined
            ? { stop_loss_value: stopLossOverride.value }
            : {}),
        }
      : {}),
    enable_session_exit: sessionExit.enabled,
    session_exit_at: sessionExit.at,
    skip_trades_on_price_anomaly_days: state.skipTradesOnPriceAnomalyDays,
    skip_trades_on_intraday_anomalies_10pct: state.skipTradesOnIntradayAnomalies10pct,
    skip_trades_on_intraday_anomalies_20pct: state.skipTradesOnIntradayAnomalies20pct,
    skip_trades_on_cross_day_anomalies_10pct: state.skipTradesOnCrossDayAnomalies10pct,
    skip_trades_on_cross_day_anomalies_20pct: state.skipTradesOnCrossDayAnomalies20pct,
  }
  if (state.source === 'library') {
    return {
      ...shared,
      library_strategy_id: state.libraryStrategyId,
      strategy_params: state.params,
    }
  }
  return { ...shared, strategy_id: state.userStrategyId }
}

/** Restore a persisted workflow, ignoring anything that is not one. */
export function parseWorkflow(raw: string | null): WorkflowState | null {
  if (!raw) return null
  try {
    const parsed: unknown = JSON.parse(raw)
    if (typeof parsed !== 'object' || parsed === null) return null
    // Merged over a fresh value so a state written by an older build - or a
    // hand-edited one - cannot leave a field undefined.
    return { ...createInitialWorkflow(), ...(parsed as Partial<WorkflowState>) }
  } catch {
    return null
  }
}
