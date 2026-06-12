'use client'

import { useState } from 'react'
import type { Book, PatristicTradition, LibraryStructure } from '@/lib/types'
import BookCard from './BookCard'

type TraditionTab = {
  id: PatristicTradition
  label: string
  description: string
}

type PublisherTab = {
  id: string
  label: string
  count: number
}

const TRADITIONS: TraditionTab[] = [
  {
    id: 'grega',
    label: 'Patrística Grega',
    description: 'Fontes primárias em grego',
  },
  {
    id: 'oriental',
    label: 'Patrística Oriental',
    description: 'Siríaco, copta, árabe e outras línguas orientais',
  },
  {
    id: 'latina',
    label: 'Patrística Latina',
    description: 'Fontes primárias latinas, PL e coleções equivalentes',
  },
  {
    id: 'portuguesa',
    label: 'em Português',
    description: 'Traduções, edições vernáculas e materiais de apoio',
  },
]

function normalizeKey(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function publisherLabelFor(book: Book): string {
  const label = (book.edition_label || book.source_label || '').trim()
  const normalized = label
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()

  if (normalized.includes('paulus')) return 'Paulus'
  if (normalized.includes('familia')) return 'Editora Família'
  if (label) return label
  return 'Outras editoras'
}

function buildPublisherTabs(books: Book[]): PublisherTab[] {
  const counts = new Map<string, PublisherTab>()
  for (const book of books) {
    const label = publisherLabelFor(book)
    const id = normalizeKey(label)
    const current = counts.get(id)
    if (current) {
      current.count += 1
    } else {
      counts.set(id, { id, label, count: 1 })
    }
  }

  return [...counts.values()].sort((a, b) => {
    if (a.label === 'Paulus') return -1
    if (b.label === 'Paulus') return 1
    if (a.label === 'Outras editoras') return 1
    if (b.label === 'Outras editoras') return -1
    return a.label.localeCompare(b.label, 'pt')
  })
}

interface PatristicaSectionProps {
  patristica: LibraryStructure['patristica']
}

export default function PatristicaSection({ patristica }: PatristicaSectionProps) {
  const [active, setActive] = useState<PatristicTradition | null>(null)
  const [activePublisherTabs, setActivePublisherTabs] = useState<Partial<Record<PatristicTradition, string>>>({})

  const allBooks = active ? patristica[active] : []
  const activeMeta = active ? TRADITIONS.find((t) => t.id === active) : null
  const publisherTabs = active === 'portuguesa' ? buildPublisherTabs(allBooks) : []
  const requestedPublisherTab = active ? activePublisherTabs[active] ?? 'todos' : 'todos'
  const resolvedPublisherTab =
    requestedPublisherTab === 'todos' || publisherTabs.some(tab => tab.id === requestedPublisherTab)
      ? requestedPublisherTab
      : 'todos'
  const books = active === 'portuguesa' && resolvedPublisherTab !== 'todos'
    ? allBooks.filter(book => normalizeKey(publisherLabelFor(book)) === resolvedPublisherTab)
    : allBooks

  if (!active) {
    return (
      <section className="space-y-4">
        <div className="border-b border-fundo-borda pb-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
            Biblioteca Patrística
          </p>
          <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
            Tradições e edições
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
            Escolha uma tradição para abrir uma tela própria de obras.
          </p>
        </div>

        <nav className="space-y-2">
          {TRADITIONS.map((tradition) => {
            const count = patristica[tradition.id].length
            return (
              <button
                key={tradition.id}
                onClick={() => setActive(tradition.id)}
                className="flex w-full items-center justify-between rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left transition-colors hover:border-dourado/30 hover:bg-vinho-escuro/10"
              >
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-texto">
                    {tradition.label}
                  </span>
                  <span className="mt-0.5 block text-xs leading-snug text-texto-terciario">
                    {tradition.description}
                  </span>
                </span>
                <span className="ml-3 shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
                  {count}
                </span>
              </button>
            )
          })}
        </nav>
      </section>
    )
  }

  return (
    <section className="min-w-0 space-y-4">
      <div className="border-b border-fundo-borda pb-3">
        <button
          type="button"
          onClick={() => setActive(null)}
          className="mb-2 inline-flex items-center gap-1 text-xs text-texto-terciario transition-colors hover:text-dourado"
        >
          <span aria-hidden="true">‹</span>
          Biblioteca Patrística
        </button>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
              Biblioteca Patrística
            </p>
            <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
              {activeMeta?.label}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
              {activeMeta?.description}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-dourado/15 px-2.5 py-1 text-xs font-medium text-dourado">
            {allBooks.length}
          </span>
        </div>
      </div>

      {publisherTabs.length > 1 && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setActivePublisherTabs(prev => ({ ...prev, [active]: 'todos' }))}
            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
              resolvedPublisherTab === 'todos'
                ? 'border-dourado/40 bg-dourado/10 text-dourado'
                : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
            }`}
          >
            Todas
            <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
              resolvedPublisherTab === 'todos' ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
            }`}>
              {allBooks.length}
            </span>
          </button>
          {publisherTabs.map(tab => {
            const isActive = resolvedPublisherTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActivePublisherTabs(prev => ({ ...prev, [active]: tab.id }))}
                className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border-dourado/40 bg-dourado/10 text-dourado'
                    : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
                }`}
              >
                {tab.label}
                <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
                  isActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
                }`}>
                  {tab.count}
                </span>
              </button>
            )
          })}
        </div>
      )}

      {books.length === 0 ? (
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center">
          <p className="text-sm text-texto-terciario">
            Nenhuma obra catalogada nesta categoria ainda.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {books.map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      )}
    </section>
  )
}
