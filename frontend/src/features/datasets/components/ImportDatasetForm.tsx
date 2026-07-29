import { Upload } from 'lucide-react'
import { useRef, useState, type DragEvent, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

import { REQUIRED_CSV_COLUMNS, TIMEFRAMES } from '../types'
import type { DatasetImportInput, Timeframe } from '../types'

interface ImportDatasetFormProps {
  onSubmit: (input: DatasetImportInput) => Promise<void>
  isSubmitting: boolean
  onCancel?: () => void
}

export function ImportDatasetForm({ onSubmit, isSubmitting, onCancel }: ImportDatasetFormProps) {
  const [name, setName] = useState('')
  const [symbol, setSymbol] = useState('')
  const [exchange, setExchange] = useState('')
  const [timeframe, setTimeframe] = useState<Timeframe | undefined>(undefined)
  const [file, setFile] = useState<File | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [fieldError, setFieldError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  function selectFile(selected: File | null) {
    if (!selected) return
    setFile(selected)
    // Default the dataset name to the filename so the common case is one click.
    if (!name.trim()) setName(selected.name.replace(/\.csv$/i, ''))
  }

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault()
    setIsDragging(false)
    selectFile(event.dataTransfer.files[0] ?? null)
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()

    if (!file) return setFieldError('Choose a CSV file to import.')
    if (!name.trim()) return setFieldError('Name is required.')
    if (!symbol.trim()) return setFieldError('Symbol is required.')
    if (!exchange.trim()) return setFieldError('Exchange is required.')
    if (!timeframe) return setFieldError('Timeframe is required.')
    setFieldError(null)

    await onSubmit({
      name: name.trim(),
      symbol: symbol.trim(),
      exchange: exchange.trim(),
      timeframe,
      file,
    })
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-5">
      <div className="space-y-2">
        <Label htmlFor="file">CSV File</Label>
        {/* Drop target only: the Browse button and hidden input remain the
            keyboard-accessible path, so this div needs no role of its own. */}
        <div
          onDragOver={(e) => {
            e.preventDefault()
            setIsDragging(true)
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          className={`flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-10 text-center transition-colors ${
            isDragging ? 'border-primary bg-primary/5' : 'border-border'
          }`}
        >
          <Upload className="size-5 text-muted-foreground" />
          {file ? (
            <p className="text-sm font-medium">{file.name}</p>
          ) : (
            <p className="text-sm text-muted-foreground">Drag a CSV here, or</p>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => inputRef.current?.click()}
          >
            {file ? 'Choose a different file' : 'Browse files'}
          </Button>
          <Input
            id="file"
            ref={inputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => selectFile(e.target.files?.[0] ?? null)}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          Required columns: {REQUIRED_CSV_COLUMNS.join(', ')}. Timestamps may be ISO8601 or
          <span className="tabular"> YYYY-MM-DD HH:MM:SS</span>.
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="name">Name</Label>
        <Input
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="NIFTY 1-minute 2024"
          maxLength={200}
          required
        />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <div className="space-y-2">
          <Label htmlFor="symbol">Symbol</Label>
          <Input
            id="symbol"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            placeholder="NIFTY"
            maxLength={50}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="exchange">Exchange</Label>
          <Input
            id="exchange"
            value={exchange}
            onChange={(e) => setExchange(e.target.value)}
            placeholder="NSE"
            maxLength={50}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="timeframe">Timeframe</Label>
          <Select value={timeframe} onValueChange={(value) => setTimeframe(value as Timeframe)}>
            <SelectTrigger id="timeframe" className="w-full">
              <SelectValue placeholder="Select" />
            </SelectTrigger>
            <SelectContent>
              {TIMEFRAMES.map((tf) => (
                <SelectItem key={tf} value={tf}>
                  {tf}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        The timeframe you choose is what missing-bar detection is measured against.
      </p>

      {fieldError && <p className="text-sm text-destructive">{fieldError}</p>}

      <div className="flex items-center gap-2 pt-2">
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? 'Importing…' : 'Import Dataset'}
        </Button>
        {onCancel && (
          <Button type="button" variant="ghost" onClick={onCancel} disabled={isSubmitting}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  )
}
