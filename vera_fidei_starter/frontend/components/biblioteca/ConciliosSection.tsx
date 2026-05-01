'use client'

import { useState } from 'react'
import type { Book } from '@/lib/types'
import { groupByCentury } from '@/lib/century'
import BookCard from './BookCard'

interface CouncilGroup {
  name: string
  year: number | null
  totalCount: number
  books: Book[]
}

function groupByCouncil(books: Book[]): CouncilGroup[] {
  const map: Record<string, Book[]> = {}
  for (const book of books) {
    const name = book.canonical_author ?? book.author ?? 'Desconhecido'
    if (!map[name]) map[name] = []
    map[name].push(book)
  }
  return Object.entries(map)
    .map(([name, bks]) => {
      const years = bks.map(b => b.document_year).filter(Boolean) as number[]
      return {
        name,
        year: years.length ? Math.min(...years) : null,
        totalCount: bks.length,
        books: bks,
      }
    })
    .sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999))
}

function CenturedCouncilList({
  groups,
  title,
  activeCouncil,
  onSelect,
}: {
  groups: CouncilGroup[]
  title: string
  activeCouncil: string | null
  onSelect: (name: string) => void
}) {
  if (groups.length === 0) return null

  const centuries = groupByCentury(groups, g => g.year)

  return (
    <div className="space-y-3">
      <p className="text-xs font-medium text-texto-terciario uppercase tracking-wider px-1">
        {title}
      </p>
      {centuries.map(({ label, items }) => (
        <div key={label} className="space-y-1">
          <p className="text-xs text-texto-terciario px-1 py-0.5 border-b border-fundo-borda mb-1">
            {label}
          </p>
          {items.map(group => {
            const isActive = group.name === activeCouncil
            return (
              <button
                key={group.name}
                onClick={() => onSelect(group.name)}
                className={`w-full flex items-center justify-between rounded-lg border px-4 py-3 text-left transition-colors ${
                  isActive
                    ? 'border-dourado/40 bg-dourado/10'
                    : 'border-fundo-borda bg-fundo-card hover:border-dourado/20'
                }`}
              >
                <div className="min-w-0 flex items-baseline gap-2">
                  <span className={`text-sm font-medium ${isActive ? 'text-dourado' : 'text-texto'}`}>
                    {group.name}
                  </span>
                  {group.year && (
                    <span className="text-xs text-texto-terciario">({group.year})</span>
                  )}
                </div>
                <span className={`shrink-0 ml-3 text-xs rounded-full px-2 py-0.5 ${
                  isActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
                }`}>
                  {group.totalCount}
                </span>
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}

export default function ConciliosSection({ books }: { books: Book[] }) {
  // is_ecumenical = true  → Ecumênicos
  // is_ecumenical = false → Regionais
  // is_ecumenical = null  → Locais / Sínodos
  const ecumenical = books.filter(b => b.is_ecumenical === true)
  const regional   = books.filter(b => b.is_ecumenical === false)
  const local      = books.filter(b => b.is_ecumenical === null || b.is_ecumenical === undefined)

  const ecGroups  = groupByCouncil(ecumenical)
  const regGroups = groupByCouncil(regional)
  const locGroups = groupByCouncil(local)

  const defaultCouncil =
    ecGroups[0]?.name ?? regGroups[0]?.name ?? locGroups[0]?.name ?? null
  const [activeCouncil, setActiveCouncil] = useState<string | null>(defaultCouncil)

  const allGroups = [...ecGroups, ...regGroups, ...locGroups]
  const activeGroup = allGroups.find(g => g.name === activeCouncil)

  if (books.length === 0) {
    return (
      <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
        <p className="text-sm text-texto-terciario">Nenhum concílio catalogado ainda.</p>
        <p className="text-xs text-texto-terciario mt-1">
          Use <span className="font-mono">document_type = concilio</span>,{' '}
          <span className="font-mono">canonical_author</span> = nome do concílio e{' '}
          <span className="font-mono">is_ecumenical</span>:{' '}
          <span className="font-mono">true</span> / <span className="font-mono">false</span> / <span className="font-mono">null</span>.
        </p>
      </div>
    )
  }

  return (
    <div className="space-y-5">
      <div className="space-y-5">
        <CenturedCouncilList
          groups={ecGroups}
          title="Concílios Ecumênicos"
          activeCouncil={activeCouncil}
          onSelect={setActiveCouncil}
        />
        <CenturedCouncilList
          groups={regGroups}
          title="Concílios Regionais"
          activeCouncil={activeCouncil}
          onSelect={setActiveCouncil}
        />
        <CenturedCouncilList
          groups={locGroups}
          title="Concílios Locais e Sínodos"
          activeCouncil={activeCouncil}
          onSelect={setActiveCouncil}
        />
      </div>

      {activeGroup && (
        <div>
          <h2 className="font-garamond text-lg font-medium text-texto mb-3">
            {activeGroup.name}
            {activeGroup.year && (
              <span className="ml-2 text-base font-normal text-texto-terciario">
                ({activeGroup.year})
              </span>
            )}
          </h2>
          <div className="space-y-3">
            {activeGroup.books.map(book => (
              <BookCard key={book.id} book={book} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
