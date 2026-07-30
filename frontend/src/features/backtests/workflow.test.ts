import { describe, expect, it } from 'vitest'

import {
  createInitialWorkflow,
  explainabilityWarning,
  missingRequirements,
  parseNumericSettings,
  parseWorkflow,
  resolveExplainLevel,
  selectLibraryStrategy,
  toExecuteInput,
  workflowFromRun,
  type BacktestRun,
  type WorkflowState,
} from './workflow'

function runRecord(overrides: Partial<BacktestRun> = {}): BacktestRun {
  return {
    library_strategy_id: 'ema_crossover',
    library_strategy_version: '1.0.0',
    strategy_params: { fast_period: 12, slow_period: 26 },
    strategy_id: 'container-id',
    dataset_id: 'dataset-id',
    initial_capital: 50_000,
    commission: 0.001,
    slippage: 0.0005,
    explain_level: 'trades_only',
    ...overrides,
  } as BacktestRun
}

describe('selecting a library strategy', () => {
  it('keeps parameter edits when the same strategy is re-selected', () => {
    const edited: WorkflowState = {
      ...createInitialWorkflow(),
      libraryStrategyId: 'ema_crossover',
      params: { fast_period: 5 },
    }

    const next = selectLibraryStrategy(edited, 'ema_crossover')

    expect(next.params).toEqual({ fast_period: 5 })
  })

  it('drops parameter edits that belonged to a different strategy', () => {
    const edited: WorkflowState = {
      ...createInitialWorkflow(),
      libraryStrategyId: 'ema_crossover',
      params: { fast_period: 5 },
    }

    const next = selectLibraryStrategy(edited, 'rsi_mean_reversion')

    expect(next.params).toEqual({})
  })

  it('accepts defaults supplied by the caller', () => {
    const next = selectLibraryStrategy(createInitialWorkflow(), 'ema_crossover', {
      fast_period: 12,
    })

    expect(next.params).toEqual({ fast_period: 12 })
    expect(next.source).toBe('library')
  })

  it('lets a new strategy re-decide the explainability level', () => {
    const chosen: WorkflowState = {
      ...createInitialWorkflow(),
      libraryStrategyId: 'ema_crossover',
      explainLevel: 'none',
      explainLevelChosen: true,
    }

    expect(selectLibraryStrategy(chosen, 'ema_crossover').explainLevelChosen).toBe(true)
    expect(selectLibraryStrategy(chosen, 'macd').explainLevelChosen).toBe(false)
  })
})

describe('explainability', () => {
  it('follows the strategy recommendation until the trader chooses', () => {
    const state = { ...createInitialWorkflow(), explainLevel: 'trades_only' as const }

    expect(resolveExplainLevel(state, 'full')).toBe('full')
  })

  it('honours an explicit choice over the recommendation', () => {
    const state = {
      ...createInitialWorkflow(),
      explainLevel: 'trades_only' as const,
      explainLevelChosen: true,
    }

    expect(resolveExplainLevel(state, 'full')).toBe('trades_only')
  })

  it('falls back to the current level when nothing is recommended', () => {
    const state = { ...createInitialWorkflow(), explainLevel: 'none' as const }

    expect(resolveExplainLevel(state, undefined)).toBe('none')
  })

  it('warns when a traced strategy is run below full', () => {
    expect(explainabilityWarning('trades_only', true)).toMatch(/Decision Inspector/)
    expect(explainabilityWarning('none', true)).toMatch(/records nothing/)
  })

  it('stays quiet when there is nothing to lose', () => {
    expect(explainabilityWarning('full', true)).toBeNull()
    expect(explainabilityWarning('none', false)).toBeNull()
    expect(explainabilityWarning('trades_only', undefined)).toBeNull()
  })
})

describe('re-running a saved result', () => {
  it('reloads the library strategy, its parameters and its settings', () => {
    const next = workflowFromRun(createInitialWorkflow(), runRecord())

    expect(next.source).toBe('library')
    expect(next.libraryStrategyId).toBe('ema_crossover')
    expect(next.params).toEqual({ fast_period: 12, slow_period: 26 })
    expect(next.datasetId).toBe('dataset-id')
    expect(next.initialCapital).toBe('50000')
    expect(next.explainLevel).toBe('trades_only')
    expect(next.explainLevelChosen).toBe(true)
  })

  it('reloads a hand-written strategy as a user run', () => {
    const next = workflowFromRun(
      createInitialWorkflow(),
      runRecord({ library_strategy_id: null, strategy_params: null }),
    )

    expect(next.source).toBe('user')
    expect(next.userStrategyId).toBe('container-id')
    expect(next.params).toEqual({})
  })
})

describe('submitting', () => {
  it('names what is still missing', () => {
    expect(missingRequirements(createInitialWorkflow())).toEqual([
      'a library strategy',
      'a dataset',
    ])
    expect(missingRequirements({ ...createInitialWorkflow(), source: 'user' })).toEqual([
      'a strategy',
      'a dataset',
    ])
  })

  it('rejects unusable numeric settings', () => {
    const zeroCapital = parseNumericSettings({ ...createInitialWorkflow(), initialCapital: '0' })
    const negativeCommission = parseNumericSettings({
      ...createInitialWorkflow(),
      commission: '-1',
    })

    expect(zeroCapital).toEqual({ ok: false, error: 'Initial capital must be a positive number.' })
    expect(negativeCommission.ok).toBe(false)
  })

  it('sends a library run with no strategy_id so the backend provisions one', () => {
    const state: WorkflowState = {
      ...createInitialWorkflow(),
      libraryStrategyId: 'ema_crossover',
      params: { fast_period: 5 },
      datasetId: 'dataset-id',
    }

    const input = toExecuteInput(
      state,
      { initialCapital: 100_000, commission: 0, slippage: 0 },
      'full',
    )

    expect(input.strategy_id).toBeUndefined()
    expect(input.library_strategy_id).toBe('ema_crossover')
    expect(input.strategy_params).toEqual({ fast_period: 5 })
    expect(input.explain_level).toBe('full')
  })

  it('sends a user run with no parameters, which the API rejects for saved code', () => {
    const state: WorkflowState = {
      ...createInitialWorkflow(),
      source: 'user',
      userStrategyId: 'strategy-id',
      params: { fast_period: 5 },
      datasetId: 'dataset-id',
    }

    const input = toExecuteInput(
      state,
      { initialCapital: 100_000, commission: 0, slippage: 0 },
      'trades_only',
    )

    expect(input.strategy_id).toBe('strategy-id')
    expect(input.library_strategy_id).toBeUndefined()
    expect(input.strategy_params).toBeUndefined()
  })
})

describe('restoring a persisted workflow', () => {
  it('fills in fields a stored state predates', () => {
    const restored = parseWorkflow(JSON.stringify({ libraryStrategyId: 'macd' }))

    expect(restored?.libraryStrategyId).toBe('macd')
    expect(restored?.initialCapital).toBe('100000')
    expect(restored?.source).toBe('library')
  })

  it('ignores anything that is not a stored workflow', () => {
    expect(parseWorkflow(null)).toBeNull()
    expect(parseWorkflow('not json')).toBeNull()
    expect(parseWorkflow('"a string"')).toBeNull()
  })
})
