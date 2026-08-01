import { Link } from 'react-router-dom'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { formatInteger } from '@/lib/format'

import { useDatasetReferences } from '../queries'
import type { Dataset } from '../types'

interface DeleteDatasetDialogProps {
  dataset: Dataset | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isDeleting: boolean
  errorMessage?: string | null
}

export function DeleteDatasetDialog({
  dataset,
  onOpenChange,
  onConfirm,
  isDeleting,
  errorMessage,
}: DeleteDatasetDialogProps) {
  const referencesQuery = useDatasetReferences(dataset?.id ?? '', dataset !== null)
  const references = referencesQuery.data
  const isBlocked = (references?.reference_count ?? 0) > 0

  return (
    <AlertDialog open={dataset !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete &ldquo;{dataset?.name}&rdquo;?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3 text-sm text-muted-foreground">
              <p>
                This removes the dataset and deletes both its Parquet file and the original uploaded
                CSV from disk. This cannot be undone — you would need to import the CSV again.
              </p>

              {referencesQuery.isLoading && (
                <p className="text-xs">Checking backtest references…</p>
              )}

              {isBlocked && references && (
                <div className="rounded-md border border-loss/30 bg-loss/10 p-3 text-foreground">
                  <p className="font-medium text-loss">
                    Cannot delete — used by {formatInteger(references.reference_count)} backtest
                    {references.reference_count === 1 ? '' : 's'}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Historical backtest runs keep a permanent link to this dataset. Archive it instead
                    if you no longer want it for new backtests.
                  </p>
                  <ul className="mt-2 space-y-1 text-xs">
                    {references.backtest_runs.map((run) => (
                      <li key={run.run_id}>
                        <Link
                          to={`/backtests/runs/${run.run_id}`}
                          className="text-primary underline-offset-4 hover:underline"
                        >
                          {run.strategy_name}
                        </Link>
                        {run.dataset_version_number != null && (
                          <span className="text-muted-foreground">
                            {' '}
                            · v{run.dataset_version_number}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                  {references.reference_count > references.backtest_runs.length && (
                    <p className="mt-2 text-xs text-muted-foreground">
                      …and {references.reference_count - references.backtest_runs.length} more
                    </p>
                  )}
                </div>
              )}

              {errorMessage && !isBlocked && (
                <p className="rounded-md border border-loss/30 bg-loss/10 p-3 text-sm text-loss">
                  {errorMessage}
                </p>
              )}
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={(event) => {
              event.preventDefault()
              onConfirm()
            }}
            disabled={isDeleting || isBlocked || referencesQuery.isLoading}
            className="bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20 disabled:opacity-50"
          >
            {isDeleting ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
