'use client'

import { useEffect, useMemo, useState } from 'react'
import Link from 'next/link'
import { deleteFavorite, listFavorites } from '@/lib/api'
import type { FavoriteItem, FavoriteKind } from '@/lib/types'

const TABS: Array<{ id: FavoriteKind | 'all'; label: string }> = [
  { id: 'all', label: 'Todos' },
  { id: 'book', label: 'Obras' },
  { id: 'prayer', label: 'Orações' },
]

function kindLabel(kind: FavoriteKind) {
  return kind === 'book' ? 'Obra' : 'Oração'
}

interface ProfileFavoritesProps {
  onTotalChange?: (total: number) => void
}

export default function ProfileFavorites({ onTotalChange }: ProfileFavoritesProps) {
  const [items, setItems] = useState<FavoriteItem[]>([])
  const [activeTab, setActiveTab] = useState<FavoriteKind | 'all'>('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load() {
    setLoading(true)
    setError('')
    try {
      const data = await listFavorites()
      setItems(data.items)
      onTotalChange?.(data.total)
    } catch {
      setError('Erro ao carregar favoritos.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    const handleChanged = () => load()
    window.addEventListener('vf:favorites-changed', handleChanged)
    return () => window.removeEventListener('vf:favorites-changed', handleChanged)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const filteredItems = useMemo(() => {
    if (activeTab === 'all') return items
    return items.filter((item) => item.kind === activeTab)
  }, [activeTab, items])

  async function handleRemove(item: FavoriteItem) {
    try {
      await deleteFavorite(item.kind, item.item_id)
      const next = items.filter((favorite) => favorite.id !== item.id)
      setItems(next)
      onTotalChange?.(next.length)
      window.dispatchEvent(new CustomEvent('vf:favorites-changed'))
    } catch {
      setError('Erro ao remover favorito.')
    }
  }

  return (
    <section id="favoritos" className="mt-6 rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
            Favoritos
          </p>
          <h2 className="mt-1 font-garamond text-xl text-texto">
            Obras e orações para acompanhar
          </h2>
          <p className="mt-1 text-xs text-texto-terciario">
            {items.length} item{items.length === 1 ? '' : 's'} favoritado{items.length === 1 ? '' : 's'}
          </p>
        </div>

        <div className="flex rounded-md border border-fundo-borda bg-fundo p-1">
          {TABS.map((tab) => {
            const active = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
                  active ? 'bg-dourado text-fundo' : 'text-texto-terciario hover:text-dourado'
                }`}
              >
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {loading && <p className="py-10 text-center text-sm text-texto-terciario">Carregando...</p>}
      {error && <p className="py-10 text-center text-sm text-vermelho">{error}</p>}

      {!loading && !error && filteredItems.length === 0 && (
        <div className="py-10 text-center">
          <p className="text-sm text-texto-terciario">
            Nenhum favorito nesta aba.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <Link
              href="/biblioteca"
              className="rounded-md border border-dourado/40 px-3 py-2 text-xs text-dourado transition-colors hover:bg-dourado hover:text-fundo"
            >
              Ver obras
            </Link>
            <Link
              href="/oracoes"
              prefetch={false}
              className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
            >
              Ver orações
            </Link>
          </div>
        </div>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {filteredItems.map((item) => (
          <article key={item.id} className="rounded-lg border border-fundo-borda bg-fundo p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div className="min-w-0">
                <span className="rounded-full border border-dourado/30 px-2 py-0.5 text-[11px] font-medium text-dourado">
                  {kindLabel(item.kind)}
                </span>
                <h3 className="mt-2 line-clamp-2 font-garamond text-lg leading-snug text-texto">
                  {item.title}
                </h3>
                {item.subtitle && (
                  <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-texto-terciario">
                    {item.subtitle}
                  </p>
                )}
              </div>
              <button
                type="button"
                onClick={() => handleRemove(item)}
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-texto-terciario transition-colors hover:bg-fundo-card hover:text-vermelho"
                aria-label="Remover favorito"
                title="Remover"
              >
                ×
              </button>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-fundo-borda pt-3">
              <span className="text-[11px] text-texto-terciario">
                {new Date(item.updated_at).toLocaleDateString('pt-BR')}
              </span>
              <Link
                href={item.href}
                prefetch={item.href.startsWith('/oracoes') ? false : undefined}
                className="rounded-md border border-dourado/35 px-3 py-1.5 text-xs font-medium text-dourado transition-colors hover:bg-dourado/10"
              >
                Abrir
              </Link>
            </div>
          </article>
        ))}
      </div>
    </section>
  )
}
