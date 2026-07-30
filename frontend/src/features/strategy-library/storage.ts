const RECENT_KEY = 'strategy-library-recent'
const FAVORITES_KEY = 'strategy-library-favorites'
const MAX_RECENT = 8

function readIds(key: string): string[] {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    return Array.isArray(parsed)
      ? parsed.filter((item): item is string => typeof item === 'string')
      : []
  } catch {
    return []
  }
}

function writeIds(key: string, ids: string[]) {
  localStorage.setItem(key, JSON.stringify(ids))
}

export function getRecentStrategyIds(): string[] {
  return readIds(RECENT_KEY)
}

export function recordRecentStrategy(strategyId: string): string[] {
  const next = [strategyId, ...getRecentStrategyIds().filter((id) => id !== strategyId)].slice(
    0,
    MAX_RECENT,
  )
  writeIds(RECENT_KEY, next)
  return next
}

export function getFavoriteStrategyIds(): string[] {
  return readIds(FAVORITES_KEY)
}

export function toggleFavoriteStrategy(strategyId: string): string[] {
  const current = getFavoriteStrategyIds()
  const next = current.includes(strategyId)
    ? current.filter((id) => id !== strategyId)
    : [...current, strategyId]
  writeIds(FAVORITES_KEY, next)
  return next
}

export function isFavoriteStrategy(strategyId: string): boolean {
  return getFavoriteStrategyIds().includes(strategyId)
}
