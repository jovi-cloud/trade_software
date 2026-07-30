import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import type { ParamSpec, ParamValue } from '../types'

interface ParameterEditorProps {
  groups: { name: string; parameters: ParamSpec[] }[]
  values: Record<string, ParamValue>
  onChange: (name: string, value: ParamValue) => void
}

export function ParameterEditor({ groups, values, onChange }: ParameterEditorProps) {
  return (
    <div className="space-y-6">
      {groups.map((group) => (
        <section key={group.name}>
          <h3 className="mb-3 text-sm font-semibold">{group.name}</h3>
          <div className="grid gap-4 md:grid-cols-2">
            {group.parameters.map((param) => (
              <div key={param.name} className="space-y-1.5">
                <Label htmlFor={param.name} title={param.tooltip || undefined}>
                  {param.label}
                  {param.unit ? ` (${param.unit})` : ''}
                </Label>
                {renderField(param, values[param.name] ?? param.default, (value) =>
                  onChange(param.name, value),
                )}
                <p className="text-xs text-muted-foreground">{param.description}</p>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function renderField(param: ParamSpec, value: ParamValue, onChange: (value: ParamValue) => void) {
  switch (param.type) {
    case 'boolean':
      return (
        <Select
          value={value ? 'true' : 'false'}
          onValueChange={(next) => onChange(next === 'true')}
        >
          <SelectTrigger id={param.name}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="true">Yes</SelectItem>
            <SelectItem value="false">No</SelectItem>
          </SelectContent>
        </Select>
      )
    case 'choice':
      return (
        <Select value={String(value)} onValueChange={(next) => onChange(next)}>
          <SelectTrigger id={param.name}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(param.choices ?? []).map((choice) => (
              <SelectItem key={choice.value} value={choice.value}>
                {choice.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )
    case 'integer':
    case 'float':
    case 'percentage':
    case 'price':
      return (
        <Input
          id={param.name}
          type="number"
          value={String(value)}
          min={param.minimum ?? undefined}
          max={param.maximum ?? undefined}
          step={param.step ?? (param.type === 'integer' ? 1 : 'any')}
          onChange={(event) => {
            const raw = event.target.value
            if (raw === '') return
            const parsed = param.type === 'integer' ? Number.parseInt(raw, 10) : Number(raw)
            if (!Number.isNaN(parsed)) onChange(parsed)
          }}
        />
      )
    case 'time':
    case 'string':
    default:
      return (
        <Input
          id={param.name}
          type="text"
          value={String(value)}
          placeholder={param.type === 'time' ? 'HH:MM' : undefined}
          onChange={(event) => onChange(event.target.value)}
        />
      )
  }
}
