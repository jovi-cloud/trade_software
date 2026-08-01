import { useMemo } from 'react'

import { formatInteger, formatPercent } from '@/lib/format'

import { sessionIssueRows } from '../qualityScore'
import type { PipelineSession } from '../pipelineTypes'

interface SessionIssuesPieChartProps {
  session: PipelineSession
}

interface PieSlice {
  key: string
  label: string
  count: number
  color: string
  percent: number
  startAngle: number
  endAngle: number
}

const SIZE = 220
const RADIUS = 90
const CENTER = SIZE / 2

function polarToCartesian(angleDeg: number, radius = RADIUS): { x: number; y: number } {
  const angleRad = ((angleDeg - 90) * Math.PI) / 180
  return {
    x: CENTER + radius * Math.cos(angleRad),
    y: CENTER + radius * Math.sin(angleRad),
  }
}

function describeSlice(startAngle: number, endAngle: number): string {
  if (endAngle - startAngle >= 359.999) {
    return `M ${CENTER} ${CENTER} m -${RADIUS} 0 a ${RADIUS} ${RADIUS} 0 1 0 ${RADIUS * 2} 0 a ${RADIUS} ${RADIUS} 0 1 0 -${RADIUS * 2} 0`
  }

  const start = polarToCartesian(endAngle)
  const end = polarToCartesian(startAngle)
  const largeArc = endAngle - startAngle > 180 ? 1 : 0

  return [
    `M ${CENTER} ${CENTER}`,
    `L ${start.x} ${start.y}`,
    `A ${RADIUS} ${RADIUS} 0 ${largeArc} 0 ${end.x} ${end.y}`,
    'Z',
  ].join(' ')
}

function buildSlices(session: PipelineSession): PieSlice[] {
  const rows = sessionIssueRows(session).filter((row) => row.count > 0)
  const total = rows.reduce((sum, row) => sum + row.count, 0)
  if (total === 0) return []

  let cursor = 0
  return rows.map((row) => {
    const percent = (row.count / total) * 100
    const sweep = (row.count / total) * 360
    const startAngle = cursor
    const endAngle = cursor + sweep
    cursor = endAngle
    return {
      key: row.key,
      label: row.label,
      count: row.count,
      color: row.color,
      percent,
      startAngle,
      endAngle,
    }
  })
}

export function SessionIssuesPieChart({ session }: SessionIssuesPieChartProps) {
  const slices = useMemo(() => buildSlices(session), [session])
  const total = slices.reduce((sum, slice) => sum + slice.count, 0)

  if (slices.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">No session issues to chart.</p>
    )
  }

  return (
    <div className="flex flex-col gap-6 lg:flex-row lg:items-center">
      <div className="mx-auto shrink-0">
        <svg
          width={SIZE}
          height={SIZE}
          viewBox={`0 0 ${SIZE} ${SIZE}`}
          role="img"
          aria-label={`Session issues breakdown across ${formatInteger(total)} violations`}
        >
          {slices.map((slice) => (
            <path
              key={slice.key}
              d={describeSlice(slice.startAngle, slice.endAngle)}
              fill={slice.color}
              stroke="var(--background)"
              strokeWidth={2}
            >
              <title>
                {slice.label}: {formatInteger(slice.count)} ({formatPercent(slice.percent)})
              </title>
            </path>
          ))}
          <circle cx={CENTER} cy={CENTER} r={42} fill="var(--card)" />
          <text
            x={CENTER}
            y={CENTER - 6}
            textAnchor="middle"
            className="fill-foreground text-[11px] font-medium"
          >
            Total
          </text>
          <text
            x={CENTER}
            y={CENTER + 14}
            textAnchor="middle"
            className="fill-foreground text-sm font-semibold"
          >
            {formatInteger(total)}
          </text>
        </svg>
      </div>

      <ul className="min-w-0 flex-1 space-y-2 text-sm">
        {slices.map((slice) => (
          <li key={slice.key} className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <span
                className="size-3 shrink-0 rounded-full"
                style={{ backgroundColor: slice.color }}
                aria-hidden
              />
              <span className="truncate">{slice.label}</span>
            </div>
            <div className="tabular shrink-0 text-right">
              <span className="font-medium">{formatInteger(slice.count)}</span>
              <span className="ml-2 text-muted-foreground">
                ({formatPercent(slice.percent, 1)})
              </span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
