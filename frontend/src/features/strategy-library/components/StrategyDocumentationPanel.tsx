import type { StrategyDocumentation } from '../types'

interface StrategyDocumentationPanelProps {
  documentation: StrategyDocumentation
}

export function StrategyDocumentationPanel({ documentation }: StrategyDocumentationPanelProps) {
  return (
    <div className="space-y-6">
      <section>
        <h3 className="mb-2 text-sm font-semibold">Overview</h3>
        <p className="text-sm leading-relaxed text-muted-foreground">{documentation.overview}</p>
      </section>

      <DocList title="Indicators" items={documentation.indicators} />
      <DocList title="Entry rules" items={documentation.entry_rules} />
      <DocList title="Exit rules" items={documentation.exit_rules} />
      <DocList title="Risk rules" items={documentation.risk_rules} />

      {documentation.examples.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">Examples</h3>
          <div className="space-y-3">
            {documentation.examples.map((example) => (
              <div key={example.title} className="rounded-md border border-border p-3">
                <h4 className="text-sm font-medium">{example.title}</h4>
                <p className="mt-1 text-sm text-muted-foreground">{example.description}</p>
                <p className="mt-2 text-xs text-muted-foreground">
                  {example.instrument} · {example.timeframe}
                  {Object.keys(example.params).length > 0 && (
                    <>
                      {' '}
                      ·{' '}
                      {Object.entries(example.params)
                        .map(([name, value]) => `${name}=${value}`)
                        .join(', ')}
                    </>
                  )}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      <DocList title="Known limitations" items={documentation.known_limitations} />

      {documentation.changelog.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">Changelog</h3>
          <div className="space-y-3">
            {documentation.changelog.map((entry) => (
              <div key={entry.version}>
                <p className="text-sm font-medium">
                  {entry.version} · {entry.date}
                </p>
                <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-muted-foreground">
                  {entry.changes.map((change) => (
                    <li key={change}>{change}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

function DocList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold">{title}</h3>
      <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  )
}
