/**
 * Semantic colour helpers.
 *
 * Profit/loss colouring is a domain decision, not a styling one, so it is
 * decided here rather than with inline green/red classes at call sites.
 */

/** Tailwind text class for a signed value. Zero is neutral, not green. */
export function pnlTextClass(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value) || value === 0) {
    return 'text-muted-foreground'
  }
  return value > 0 ? 'text-profit' : 'text-loss'
}

/** CSS custom property, for chart libraries that need a raw colour string. */
export function pnlCssVar(value: number): string {
  if (value === 0) return 'var(--neutral)'
  return value > 0 ? 'var(--profit)' : 'var(--loss)'
}
