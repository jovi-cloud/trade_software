import type { Operand } from '@/features/explain/api'

interface OperandTableProps {
  operands: Operand[]
}

/**
 * The raw numbers behind a bar's verdicts.
 *
 * This is the panel that answers "the size was zero, but why". A condition table
 * shows that `Position Size Available` failed; these operands show that 20% of
 * 1,000 at a price of 995.40 sized 0.201 units and whole-unit rounding erased it.
 */
export function OperandTable({ operands }: OperandTableProps) {
  if (operands.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No calculation operands were recorded on this bar. Re-run with full
        explainability to capture them.
      </p>
    )
  }

  const groups = groupOperands(operands)

  return (
    <div className="space-y-4">
      {groups.map((group) => (
        <div key={group.label} className="space-y-2">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {group.label}
          </p>
          <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
            {group.operands.map((operand) => (
              <div key={operand.name} className="flex items-baseline justify-between gap-3">
                <dt className="text-sm text-muted-foreground">{operand.label}</dt>
                <dd className="font-mono text-sm tabular-nums">
                  {formatOperand(operand)}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
    </div>
  )
}

interface OperandGroup {
  label: string
  operands: Operand[]
}

/** Grouped by prefix so sizing arithmetic reads as one calculation, not a list. */
function groupOperands(operands: Operand[]): OperandGroup[] {
  const sizing = operands.filter((item) => item.name.startsWith('size_'))
  const risk = operands.filter((item) => item.name.startsWith('risk_'))
  const named = new Set([...sizing, ...risk].map((item) => item.name))
  const portfolio = operands.filter((item) => !named.has(item.name))

  return [
    { label: 'Portfolio', operands: portfolio },
    { label: 'Position sizing', operands: sizing },
    { label: 'Risk levels', operands: risk },
  ].filter((group) => group.operands.length > 0)
}

function formatOperand(operand: Operand): string {
  const value = operand.value
  // Sub-unit sizes are the interesting case for sizing operands, and rounding
  // them to two places would render the whole problem as "0.00".
  const digits = Math.abs(value) > 0 && Math.abs(value) < 1 ? 6 : 2
  const formatted = value.toLocaleString(undefined, {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
  return operand.unit ? `${formatted} ${operand.unit}` : formatted
}
