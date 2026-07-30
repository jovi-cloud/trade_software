import { BookOpen, ExternalLink, RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ParameterEditor } from '@/features/strategy-library/components/ParameterEditor'
import { StrategyDocumentationPanel } from '@/features/strategy-library/components/StrategyDocumentationPanel'
import { ValidationPanel } from '@/features/strategy-library/components/ValidationPanel'
import { categoryLabel, riskClassName, riskLabel } from '@/features/strategy-library/categoryMeta'
import {
  useLibraryStrategy,
  useLibraryStrategyDocumentation,
  useValidateLibraryParams,
} from '@/features/strategy-library/queries'
import type {
  LibraryStrategy,
  ParamValidation,
  ParamValue,
} from '@/features/strategy-library/types'
import { getErrorMessage } from '@/lib/apiClient'

interface LibraryStrategyConfigProps {
  strategyId: string
  params: Record<string, ParamValue>
  onParamsChange: (params: Record<string, ParamValue>) => void
  /** Lets the form read the strategy's recommendation and block an invalid run. */
  onStrategyLoaded: (strategy: LibraryStrategy) => void
  onValidationChange: (validation: ParamValidation | undefined) => void
}

const VALIDATE_DEBOUNCE_MS = 400

/**
 * The library's own parameter editor, documentation and validation, embedded in
 * the run form.
 *
 * Deliberately not a second editor: the same components the Strategy Library
 * detail page renders are reused here, so a parameter only ever has one way to
 * be displayed, validated and explained.
 */
export function LibraryStrategyConfig({
  strategyId,
  params,
  onParamsChange,
  onStrategyLoaded,
  onValidationChange,
}: LibraryStrategyConfigProps) {
  const strategy = useLibraryStrategy(strategyId)
  const documentation = useLibraryStrategyDocumentation(strategyId)
  const {
    mutate: validateParams,
    data: validation,
    isPending: isValidating,
  } = useValidateLibraryParams(strategyId)
  const [showDocs, setShowDocs] = useState(false)

  const detail = strategy.data

  useEffect(() => {
    if (detail) onStrategyLoaded(detail)
  }, [detail, onStrategyLoaded])

  useEffect(() => {
    if (!strategyId || !detail) return
    const timeout = setTimeout(() => validateParams({ params }), VALIDATE_DEBOUNCE_MS)
    return () => clearTimeout(timeout)
  }, [strategyId, params, detail, validateParams])

  useEffect(() => {
    onValidationChange(validation)
  }, [validation, onValidationChange])

  if (strategy.isLoading) {
    return (
      <div className="space-y-3">
        <Skeleton className="h-6 w-48" />
        <Skeleton className="h-32 w-full" />
      </div>
    )
  }

  if (strategy.isError || !detail) {
    return (
      <p className="text-sm text-destructive">
        {getErrorMessage(strategy.error, 'Unable to load this library strategy.')}
      </p>
    )
  }

  return (
    <div className="space-y-4 rounded-lg border border-border p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{detail.name}</h3>
            <Badge variant="secondary">{categoryLabel(detail.category)}</Badge>
            <Badge className={riskClassName(detail.risk_level)}>
              {riskLabel(detail.risk_level)}
            </Badge>
            <Badge variant="outline">v{detail.version}</Badge>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">{detail.description}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setShowDocs((open) => !open)}
          >
            <BookOpen className="size-4" />
            {showDocs ? 'Hide docs' : 'Documentation'}
          </Button>
          <Button variant="ghost" size="sm" asChild>
            <Link to={`/strategy-library/${detail.id}`}>
              <ExternalLink className="size-4" />
              Full details
            </Link>
          </Button>
        </div>
      </div>

      {showDocs && documentation.data && (
        <StrategyDocumentationPanel documentation={documentation.data} />
      )}

      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold">Parameters</h4>
        <div className="flex flex-wrap items-center gap-2">
          {detail.examples?.map((example) => (
            <Button
              key={example.title}
              type="button"
              variant="outline"
              size="sm"
              onClick={() => onParamsChange(example.params as Record<string, ParamValue>)}
            >
              {example.title}
            </Button>
          ))}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => onParamsChange(detail.default_params as Record<string, ParamValue>)}
          >
            <RotateCcw className="size-4" />
            Reset to defaults
          </Button>
        </div>
      </div>

      <ParameterEditor
        groups={detail.parameter_groups ?? []}
        values={params}
        onChange={(name, value) => onParamsChange({ ...params, [name]: value })}
      />

      <ValidationPanel validation={validation} isValidating={isValidating} />
    </div>
  )
}
