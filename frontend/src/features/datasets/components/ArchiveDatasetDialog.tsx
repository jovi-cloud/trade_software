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

import type { Dataset } from '../types'

interface ArchiveDatasetDialogProps {
  dataset: Dataset | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isArchiving: boolean
}

export function ArchiveDatasetDialog({
  dataset,
  onOpenChange,
  onConfirm,
  isArchiving,
}: ArchiveDatasetDialogProps) {
  return (
    <AlertDialog open={dataset !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Archive &ldquo;{dataset?.name}&rdquo;?</AlertDialogTitle>
          <AlertDialogDescription>
            Archived datasets remain readable and historical backtests keep working, but this
            dataset will no longer appear when starting new backtests.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isArchiving}>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={onConfirm} disabled={isArchiving}>
            Archive
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
