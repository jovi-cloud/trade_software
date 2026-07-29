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

import type { BacktestRunListItem } from '../types'

interface DeleteBacktestRunDialogProps {
  run: BacktestRunListItem | null
  onOpenChange: (open: boolean) => void
  onConfirm: () => void
  isDeleting: boolean
}

export function DeleteBacktestRunDialog({
  run,
  onOpenChange,
  onConfirm,
  isDeleting,
}: DeleteBacktestRunDialogProps) {
  return (
    <AlertDialog open={run !== null} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Delete this backtest run?</AlertDialogTitle>
          <AlertDialogDescription>
            Run <span className="font-mono text-xs">{run?.id}</span> for{' '}
            <strong>{run?.strategy_name}</strong> will be permanently removed. This cannot be
            undone.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Cancel</AlertDialogCancel>
          <AlertDialogAction disabled={isDeleting} onClick={onConfirm}>
            {isDeleting ? 'Deleting…' : 'Delete'}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
