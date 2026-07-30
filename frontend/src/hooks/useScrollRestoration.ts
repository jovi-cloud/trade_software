import { useEffect } from 'react'

/**
 * Put a page back where the trader left it.
 *
 * The workflow sends them from a long run form to a result and back again; the
 * router resets scroll on every navigation, which would drop them at the top of
 * a parameter list they were halfway down. Positions are per-key and per-tab.
 */
export function useScrollRestoration(key: string, enabled = true): void {
  useEffect(() => {
    if (!enabled) return
    const storageKey = `scroll:${key}`

    const saved = Number(safeGet(storageKey))
    if (Number.isFinite(saved) && saved > 0) {
      // After paint, or the page is still too short to scroll that far.
      const frame = requestAnimationFrame(() => window.scrollTo(0, saved))
      return () => {
        cancelAnimationFrame(frame)
        safeSet(storageKey, String(window.scrollY))
      }
    }
    return () => safeSet(storageKey, String(window.scrollY))
  }, [key, enabled])
}

function safeGet(key: string): string | null {
  try {
    return sessionStorage.getItem(key)
  } catch {
    return null
  }
}

function safeSet(key: string, value: string): void {
  try {
    sessionStorage.setItem(key, value)
  } catch {
    // Losing a scroll position is not worth breaking navigation over.
  }
}
