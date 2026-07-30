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
