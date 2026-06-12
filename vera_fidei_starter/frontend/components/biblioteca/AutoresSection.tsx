'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { AuthorCatalogEntry, Book } from '@/lib/types'
import { formatLanguage } from '@/lib/language'
import { groupByCentury, getAuthorDeathYear } from '@/lib/century'

function groupByWork(books: Book[]): { title: string; books: Book[] }[] {
  const map: Record<string, Book[]> = {}
  for (const book of books) {
    const title = book.canonical_title ?? book.title
    if (!map[title]) map[title] = []
    map[title].push(book)
  }
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b, 'pt'))
    .map(([title, bks]) => ({ title, books: bks }))
}

const COLLECTION_LABEL: Record<string, string> = {
  PT: 'Paulus',
  PL: 'Migne PL',
  PG: 'Migne PG',
  PO: 'Patrologia Orientalis',
}

function editionSummary(books: Book[]): string {
  const labels = [...new Set(
    books.map(b => b.edition_label || COLLECTION_LABEL[b.collection ?? ''] || b.collection || '')
      .filter(Boolean)
  )]
  return labels.length > 0 ? labels.join(' · ') : 'Patrística'
}

interface AutoresSectionProps {
  catalog: AuthorCatalogEntry[]
}

function EditionLink({ book }: { book: Book }) {
  return (
    <Link
      href={`/biblioteca/${book.id}`}
      className="flex items-center justify-between rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 transition-colors hover:border-dourado/30 hover:bg-vinho-escuro/10"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5 text-xs text-texto-terciario">
          {book.is_primary_source && (
            <span className="rounded-full bg-dourado/15 px-2 py-0.5 font-medium text-dourado">
              Primária
            </span>
          )}
          {(book.edition_label || book.collection) && (
            <span className="rounded bg-fundo px-1.5 py-0.5 font-mono">
              {book.edition_label || COLLECTION_LABEL[book.collection ?? ''] || book.collection}
            </span>
          )}
          {book.language && <span>{formatLanguage(book.language)}</span>}
        </div>
        {book.chunk_count !== undefined && book.chunk_count > 0 && (
          <p className="mt-0.5 text-xs text-texto-terciario">
            {book.chunk_count} trechos indexados
          </p>
        )}
      </div>
      <span aria-hidden="true" className="ml-2 shrink-0 text-texto-terciario">
        ›
      </span>
    </Link>
  )
}

export default function AutoresSection({ catalog }: AutoresSectionProps) {
  const [selectedAuthor, setSelectedAuthor] = useState<AuthorCatalogEntry | null>(null)
  const [selectedWorkTitle, setSelectedWorkTitle] = useState<string | null>(null)

  if (catalog.length === 0) {
    return (
      <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center">
        <p className="text-sm text-texto-terciario">Catálogo indisponível.</p>
      </div>
    )
  }

  const withBooks = catalog.filter((entry) => entry.book_count > 0)
  const withoutBooks = catalog.filter((entry) => entry.book_count === 0)
  const centuries = groupByCentury(withBooks, entry => getAuthorDeathYear(entry.name))
  const selectedWorks = selectedAuthor ? groupByWork(selectedAuthor.books) : []
  const selectedWork = selectedWorkTitle
    ? selectedWorks.find(work => work.title === selectedWorkTitle) ?? null
    : null

  if (selectedAuthor && selectedWork) {
    return (
      <section className="space-y-4">
        <button
          type="button"
          onClick={() => setSelectedWorkTitle(null)}
          className="inline-flex items-center gap-1 text-xs text-texto-terciario transition-colors hover:text-dourado"
        >
          <span aria-hidden="true">‹</span>
          {selectedAuthor.name}
        </button>

        <div className="border-b border-fundo-borda pb-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
            Obra
          </p>
          <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
            {selectedWork.title}
          </h2>
          <p className="mt-1 text-sm text-texto-secundario">
            {selectedAuthor.name} · {selectedWork.books.length}{' '}
            {selectedWork.books.length === 1 ? 'edição' : 'edições'}
          </p>
        </div>

        <div className="space-y-2">
          {selectedWork.books.map(book => (
            <EditionLink key={book.id} book={book} />
          ))}
        </div>
      </section>
    )
  }

  if (selectedAuthor) {
    const deathYear = getAuthorDeathYear(selectedAuthor.name)

    return (
      <section className="space-y-4">
        <button
          type="button"
          onClick={() => {
            setSelectedAuthor(null)
            setSelectedWorkTitle(null)
          }}
          className="inline-flex items-center gap-1 text-xs text-texto-terciario transition-colors hover:text-dourado"
        >
          <span aria-hidden="true">‹</span>
          Obras dos Padres
        </button>

        <div className="rounded-lg border border-dourado/25 bg-dourado/5 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
                Autor patrístico
              </p>
              <h2 className="mt-1 font-garamond text-3xl font-semibold leading-tight text-texto">
                {selectedAuthor.name}
                {deathYear && (
                  <span className="ml-2 font-sans text-base font-normal text-texto-terciario">
                    † {deathYear}
                  </span>
                )}
              </h2>
              <p className="mt-2 text-sm text-texto-secundario">
                {editionSummary(selectedAuthor.books)} · {selectedAuthor.chunk_count} trechos indexados
              </p>
            </div>
            <span className="shrink-0 rounded-full bg-dourado/15 px-2.5 py-1 text-xs font-medium text-dourado">
              {selectedWorks.length}
            </span>
          </div>
        </div>

        <div className="space-y-2">
          {selectedWorks.map(({ title, books }) => (
            <button
              key={title}
              type="button"
              onClick={() => setSelectedWorkTitle(title)}
              className="flex w-full items-center justify-between gap-3 rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left transition-colors hover:border-dourado/30 hover:bg-vinho-escuro/10"
            >
              <span className="min-w-0">
                <span className="block font-garamond text-base font-medium leading-snug text-texto">
                  {title}
                </span>
                <span className="mt-0.5 block text-xs text-texto-terciario">
                  {editionSummary(books)}
                </span>
              </span>
              <span className="ml-3 shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
                {books.length}
              </span>
            </button>
          ))}
        </div>
      </section>
    )
  }

  return (
    <section className="space-y-6">
      <div className="flex gap-3 text-xs text-texto-terciario">
        <span>
          <span className="font-medium text-dourado">{catalog.length}</span> Padres conhecidos
        </span>
        <span>·</span>
        <span>
          <span className="font-medium text-texto">{withBooks.length}</span> com obras catalogadas
        </span>
      </div>

      {withBooks.length > 0 && (
        <div className="space-y-6">
          {centuries.map(({ label, items }) => (
            <div key={label}>
              <p className="mb-2 border-b border-fundo-borda px-1 pb-2 text-xs font-medium uppercase tracking-wider text-texto-terciario">
                {label}
              </p>
              <div className="space-y-2">
                {items.map((entry) => {
                  const deathYear = getAuthorDeathYear(entry.name)
                  return (
                    <button
                      key={entry.name}
                      type="button"
                      onClick={() => {
                        setSelectedAuthor(entry)
                        setSelectedWorkTitle(null)
                      }}
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left transition-colors hover:border-dourado/30 hover:bg-vinho-escuro/10"
                    >
                      <span className="min-w-0">
                        <span className="block font-garamond text-base font-medium text-texto">
                          {entry.name}
                          {deathYear && (
                            <span className="ml-2 font-sans text-sm font-normal text-texto-terciario">
                              † {deathYear}
                            </span>
                          )}
                        </span>
                        <span className="mt-0.5 block text-xs text-texto-terciario">
                          {editionSummary(entry.books)} · {entry.book_count}{' '}
                          {entry.book_count === 1 ? 'obra' : 'obras'}
                        </span>
                      </span>
                      <span className="ml-3 shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
                        {entry.chunk_count}
                      </span>
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      )}

      {withoutBooks.length > 0 && (
        <div>
          <p className="mb-2 text-xs font-medium uppercase tracking-wider text-texto-terciario">
            Sem obras catalogadas ({withoutBooks.length})
          </p>
          <div className="space-y-1">
            {withoutBooks.map((entry) => (
              <div
                key={entry.name}
                className="flex items-center justify-between rounded-lg border border-fundo-borda/50 bg-fundo-card/40 px-4 py-2.5"
              >
                <div>
                  <p className="text-sm text-texto-terciario">{entry.name}</p>
                  <p className="mt-0.5 text-xs text-texto-terciario/60">
                    {COLLECTION_LABEL[entry.collection] ?? entry.collection}
                  </p>
                </div>
                <span className="ml-3 shrink-0 text-xs text-texto-terciario/50">0 obras</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  )
}
