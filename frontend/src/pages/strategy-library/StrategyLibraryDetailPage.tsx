import { ArrowLeft, Play, Star } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Breadcrumbs } from '@/components/common/Breadcrumbs'
import { ErrorState } from '@/components/common/ErrorState'
import { PageHeader } from '@/components/common/PageHeader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { selectLibraryStrategy } from '@/features/backtests/workflow'
import { updateWorkflow, useWorkflow } from '@/features/backtests/workflowStore'
import { useScrollRestoration } from '@/hooks/useScrollRestoration'
import { ParameterEditor } from '@/features/strategy-library/components/ParameterEditor'
import { StrategyDocumentationPanel } from '@/features/strategy-library/components/StrategyDocumentationPanel'
import { ValidationPanel } from '@/features/strategy-library/components/ValidationPanel'
import {
  categoryLabel,
  humanise,
  riskClassName,
  riskLabel,
} from '@/features/strategy-library/categoryMeta'
import {
  useLibraryStrategy,
  useLibraryStrategyDocumentation,
  useValidateLibraryParams,
} from '@/features/strategy-library/queries'
import {
  isFavoriteStrategy,
  recordRecentStrategy,
  toggleFavoriteStrategy,
} from '@/features/strategy-library/storage'
import type { ParamValue } from '@/features/strategy-library/types'
import { getErrorMessage } from '@/lib/apiClient'

const EMPTY_PARAMS: Record<string, ParamValue> = {}

export default function StrategyLibraryDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const strategy = useLibraryStrategy(id)
  const documentation = useLibraryStrategyDocumentation(id)
  const validate = useValidateLibraryParams(id)
  const { mutate: validateParams, data: validation, isPending: isValidating } = validate

  // Parameter edits live in the run workflow, not this page: the trader will
  // carry them to the run form, and may come back here from it.
  const workflow = useWorkflow()
  // Memoised so the empty fallback keeps its identity: the validation effect
  // below depends on it and would otherwise re-fire on every render.
  const params = useMemo(
    () => (workflow.libraryStrategyId === id ? workflow.params : EMPTY_PARAMS),
    [workflow.libraryStrategyId, workflow.params, id],
  )
  const [isFavorite, setIsFavorite] = useState(false)

  useScrollRestoration(`strategy-library-${id}`, Boolean(id))

  useEffect(() => {
    if (!id) return
    recordRecentStrategy(id)
    setIsFavorite(isFavoriteStrategy(id))
  }, [id])

  useEffect(() => {
    const defaults = strategy.data?.default_params
    if (!defaults) return
    updateWorkflow((current) =>
      current.libraryStrategyId === id && Object.keys(current.params).length > 0
        ? current
        : selectLibraryStrategy(current, id, defaults as Record<string, ParamValue>),
    )
  }, [id, strategy.data?.default_params])

  useEffect(() => {
    if (!id || !strategy.data) return
    const timeout = setTimeout(() => {
      validateParams({ params })
    }, 400)
    return () => clearTimeout(timeout)
  }, [id, params, strategy.data, validateParams])

  const groups = useMemo(
    () => strategy.data?.parameter_groups ?? [],
    [strategy.data?.parameter_groups],
  )

  if (strategy.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (strategy.isError || !strategy.data) {
    return (
      <ErrorState
        message={getErrorMessage(strategy.error, 'Unable to load this strategy.')}
        onRetry={() => strategy.refetch()}
      />
    )
  }

  const item = strategy.data

  function setParams(next: Record<string, ParamValue>) {
    updateWorkflow((current) => selectLibraryStrategy(current, item.id, next))
  }

  function updateParam(name: string, value: ParamValue) {
    setParams({ ...params, [name]: value })
  }

  function loadExample(exampleParams: Record<string, boolean | number | string>) {
    setParams(exampleParams as Record<string, ParamValue>)
  }

  function handleToggleFavorite() {
    const next = toggleFavoriteStrategy(item.id)
    setIsFavorite(next.includes(item.id))
  }

  const canRun = item.validation.is_valid && (validation?.is_valid ?? true)
  // Both finding lists are omitted from the payload when empty.
  const declarationErrors = item.validation.errors ?? []
  const declarationWarnings = item.validation.warnings ?? []

  return (
    <div>
      <Breadcrumbs
        items={[{ label: 'Strategy Library', to: '/strategy-library' }, { label: item.name }]}
      />

      <div className="mb-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/strategy-library">
            <ArrowLeft className="size-4" />
            Back to library
          </Link>
        </Button>
      </div>

      <PageHeader
        title={item.name}
        description={item.description}
        actions={
          <>
            <Button variant="outline" size="sm" onClick={handleToggleFavorite}>
              <Star
                className={
                  isFavorite
                    ? 'size-4 fill-amber-400 text-amber-400'
                    : 'size-4 text-muted-foreground'
                }
              />
              {isFavorite ? 'Favourited' : 'Add to favourites'}
            </Button>
            <Button
              size="sm"
              disabled={!canRun}
              title={canRun ? undefined : 'Fix the parameter errors first'}
              onClick={() => {
                setParams(params)
                navigate(`/backtests?library=${item.id}`)
              }}
            >
              <Play className="size-4" />
              Run backtest
            </Button>
          </>
        }
      />

      <div className="mb-6 flex flex-wrap gap-2">
        <Badge variant="secondary">{categoryLabel(item.category)}</Badge>
        <Badge className={riskClassName(item.risk_level)}>{riskLabel(item.risk_level)}</Badge>
        <Badge variant="outline">v{item.version}</Badge>
        <Badge variant="outline">{item.direction}</Badge>
        {item.styles.map((style) => (
          <Badge key={style} variant="outline">
            {humanise(style)}
          </Badge>
        ))}
        {item.tags.map((tag) => (
          <Badge key={tag} variant="outline">
            {tag}
          </Badge>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-[2fr_1fr]">
        <div className="space-y-8">
          <section>
            <h2 className="mb-2 text-base font-semibold">Overview</h2>
            <p className="text-sm leading-relaxed text-muted-foreground">{item.overview}</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
              <span>Markets: {item.markets.join(', ')}</span>
              <span>Timeframes: {item.timeframes.join(', ')}</span>
              <span>Author: {item.author}</span>
            </div>
          </section>

          <section>
            <div className="mb-3 flex items-center justify-between gap-2">
              <h2 className="text-base font-semibold">Parameters</h2>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setParams(item.default_params as Record<string, ParamValue>)}
              >
                Reset to defaults
              </Button>
            </div>
            <ParameterEditor groups={groups} values={params} onChange={updateParam} />
          </section>

          {item.examples.length > 0 && (
            <section>
              <h2 className="mb-3 text-base font-semibold">Example configurations</h2>
              <div className="flex flex-wrap gap-2">
                {item.examples.map((example) => (
                  <Button
                    key={example.title}
                    variant="outline"
                    size="sm"
                    onClick={() => loadExample(example.params ?? {})}
                  >
                    {example.title}
                  </Button>
                ))}
              </div>
            </section>
          )}

          {documentation.data && (
            <section>
              <h2 className="mb-3 text-base font-semibold">Documentation</h2>
              <StrategyDocumentationPanel documentation={documentation.data} />
            </section>
          )}
        </div>

        <div className="space-y-4">
          <ValidationPanel validation={validation} isValidating={isValidating} />

          {!item.validation.is_valid && (
            <section className="rounded-lg border border-destructive/40 bg-destructive/5 p-4">
              <h3 className="mb-2 text-sm font-semibold text-destructive">Declaration issues</h3>
              <ul className="space-y-1 text-sm text-destructive">
                {declarationErrors.map((finding) => (
                  <li key={finding.code}>{finding.message}</li>
                ))}
              </ul>
            </section>
          )}

          {declarationWarnings.length > 0 && (
            <section className="rounded-lg border border-amber-500/40 bg-amber-500/10 p-4">
              <h3 className="mb-2 text-sm font-semibold">Warnings</h3>
              <ul className="space-y-1 text-sm text-amber-800 dark:text-amber-300">
                {declarationWarnings.map((finding) => (
                  <li key={finding.code}>{finding.message}</li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
