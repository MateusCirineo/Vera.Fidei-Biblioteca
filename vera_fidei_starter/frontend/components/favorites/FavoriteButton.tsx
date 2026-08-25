'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { ApiError, deleteFavorite, listFavorites, saveFavorite } from '@/lib/api'
import type { FavoriteKind, FavoritePayload } from '@/lib/types'

const favoriteIds = new Map<FavoriteKind, Set<string>>()
const favoriteLoads = new Map<FavoriteKind, Promise<Set<string>>>()

function emitFavoritesChanged() {
  window.dispatchEvent(new CustomEvent('vf:favorites-changed'))
}

async function loadFavoriteIds(kind: FavoriteKind): Promise<Set<string>> {
  const cached = favoriteIds.get(kind)
  if (cached) return cached

  const existingLoad = favoriteLoads.get(kind)
  if (existingLoad) return existingLoad

  const load = listFavorites(kind)
    .then((data) => {
      const ids = new Set(data.items.map((item) => item.item_id))
      favoriteIds.set(kind, ids)
      favoriteLoads.delete(kind)
      return ids
    })
    .catch((error) => {
      favoriteLoads.delete(kind)
      throw error
    })

  favoriteLoads.set(kind, load)
  return load
}

interface FavoriteButtonProps {
  payload: FavoritePayload
  compact?: boolean
}

export default function FavoriteButton({ payload, compact = false }: FavoriteButtonProps) {
  const router = useRouter()
  const [favorited, setFavorited] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    loadFavoriteIds(payload.kind)
      .then((ids) => {
        if (!cancelled) setFavorited(ids.has(payload.item_id))
      })
      .catch(() => undefined)
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [payload.kind, payload.item_id])

  async function toggle() {
    setError('')
    setBusy(true)
    try {
      const ids = await loadFavoriteIds(payload.kind)
      if (favorited) {
        await deleteFavorite(payload.kind, payload.item_id)
        ids.delete(payload.item_id)
        setFavorited(false)
      } else {
        await saveFavorite(payload)
        ids.add(payload.item_id)
        setFavorited(true)
      }
      favoriteIds.set(payload.kind, ids)
      emitFavoritesChanged()
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        router.push(`/login?redirect=${encodeURIComponent(window.location.pathname + window.location.search)}`)
      } else {
        setError(err instanceof Error ? err.message : 'Erro ao atualizar favorito.')
      }
    } finally {
      setBusy(false)
      setLoading(false)
    }
  }

  const label = favorited ? 'Favoritado' : compact ? 'Favoritar' : 'Adicionar aos favoritos'

  return (
    <div className="inline-flex flex-col items-start gap-1">
      <button
        type="button"
        onClick={toggle}
        disabled={loading || busy}
        aria-pressed={favorited}
        className={`inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-xs font-medium transition-colors disabled:opacity-60 ${
          favorited
            ? 'border-dourado bg-dourado text-fundo'
            : 'border-dourado/35 text-dourado hover:bg-dourado/10'
        }`}
      >
        <svg
          viewBox="0 0 24 24"
          fill={favorited ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="1.7"
          className="h-4 w-4"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m12 17.3-5.3 3 1.2-5.9-4.5-4 6-.7L12 4.2l2.6 5.5 6 .7-4.5 4 1.2 5.9-5.3-3Z"
          />
        </svg>
        {busy ? 'Salvando...' : label}
      </button>
      {error && <span className="text-[11px] text-vermelho">{error}</span>}
    </div>
  )
}
