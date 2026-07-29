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

interface DeleteDatasetDialogProps {
  dataset: Dataset | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isDeleting: boolean
}

export function DeleteDatasetDialog({
  dataset,
  onOpenChange,
  onConfirm,
  isDeleting,
}: DeleteDatasetDialogProps) {
  return (
    <AlertDialog open={dataset !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete &ldquo;{dataset?.name}&rdquo;?</AlertDialogTitle>
          <AlertDialogDescription>
            This removes the dataset and deletes both its Parquet file and the original uploaded CSV
            from disk. This cannot be undone — you would need to import the CSV again.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            disabled={isDeleting}
            className="bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20"
          >
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
