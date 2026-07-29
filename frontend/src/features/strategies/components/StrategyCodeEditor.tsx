import Editor, { loader } from '@monaco-editor/react'
// The bare `monaco-editor` entrypoint eagerly bundles all ~90 languages it
// ships with. Importing the core API plus only the Python language keeps the
// production bundle to what this editor actually uses.
import * as monaco from 'monaco-editor/editor/editor.api'
import 'monaco-editor/languages/definitions/python/register'

/**
 * Bundles Monaco locally instead of the @monaco-editor/react default of
 * fetching from a CDN - this is a local-first desktop tool (ARCHITECTURE.md
 * 0.6) and must work without internet access.
 *
 * No web worker is wired up: Monaco falls back to running its worker code on
 * the main thread (one console warning, no functional loss) for the plain
 * syntax highlighting this editor needs - simpler than bundling a worker
 * through Vite for one feature (ARCHITECTURE.md guiding principle 5).
 */
loader.config({ monaco })

interface StrategyCodeEditorProps {
  value: string
  onChange: (value: string) => void
  readOnly?: boolean
}

/** The only place in the app that imports monaco-editor (ARCHITECTURE.md 2.5). */
export function StrategyCodeEditor({ value, onChange, readOnly = false }: StrategyCodeEditorProps) {
  return (
    <div className="overflow-hidden rounded-md border">
      <Editor
        height="520px"
        language="python"
        theme="vs-dark"
        value={value}
        onChange={(next) => onChange(next ?? '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: 'on',
          automaticLayout: true,
          scrollBeyondLastLine: false,
          tabSize: 4,
          insertSpaces: true,
          bracketPairColorization: { enabled: true },
          matchBrackets: 'always',
        }}
      />
    </div>
  )
}
