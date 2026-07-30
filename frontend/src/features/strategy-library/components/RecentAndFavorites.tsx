import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'

import { getFavoriteStrategyIds, getRecentStrategyIds } from '../storage'
import type { LibraryStrategyListItem } from '../types'

interface RecentAndFavoritesProps {
  strategies: LibraryStrategyListItem[]
}

export function RecentAndFavorites({ strategies }: RecentAndFavoritesProps) {
  const [recentIds, setRecentIds] = useState<string[]>([])
  const [favoriteIds, setFavoriteIds] = useState<string[]>([])

  useEffect(() => {
    setRecentIds(getRecentStrategyIds())
    setFavoriteIds(getFavoriteStrategyIds())
  }, [])

  const byId = useMemo(
    () => new Map(strategies.map((strategy) => [strategy.id, strategy])),
    [strategies],
  )

  const recent = recentIds.map((id) => byId.get(id)).filter(Boolean) as LibraryStrategyListItem[]
  const favorites = favoriteIds
    .map((id) => byId.get(id))
    .filter(Boolean) as LibraryStrategyListItem[]

  if (recent.length === 0 && favorites.length === 0) return null

  return (
    <div className="mb-6 space-y-4">
      {favorites.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">Favourites</h2>
          <div className="flex flex-wrap gap-2">
            {favorites.map((strategy) => (
              <Button key={strategy.id} variant="outline" size="sm" asChild>
                <Link to={`/strategy-library/${strategy.id}`}>{strategy.name}</Link>
              </Button>
            ))}
          </div>
        </section>
      )}
      {recent.length > 0 && (
        <section>
          <h2 className="mb-2 text-sm font-medium text-muted-foreground">Recent</h2>
          <div className="flex flex-wrap gap-2">
            {recent.map((strategy) => (
              <Badge key={strategy.id} variant="secondary" className="px-2 py-1">
                <Link to={`/strategy-library/${strategy.id}`} className="hover:underline">
                  {strategy.name}
                </Link>
              </Badge>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
