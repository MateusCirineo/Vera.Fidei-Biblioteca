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
  PT: 'Paulus', PL: 'Migne PL', PG: 'Migne PG', PO: 'Patrologia Orientalis',
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

function AuthorAccordion({
  entry,
  openAuthor,
  openWork,
  onToggleAuthor,
  onToggleWork,
}: {
  entry: AuthorCatalogEntry
  openAuthor: string | null
  openWork: string | null
  onToggleAuthor: (name: string) => void
  onToggleWork: (key: string) => void
}) {
  const isAuthorOpen = openAuthor === entry.name
  const works = groupByWork(entry.books)
  const deathYear = getAuthorDeathYear(entry.name)

  return (
    <div className="rounded-lg border border-fundo-borda overflow-hidden">
      <button
        onClick={() => onToggleAuthor(entry.name)}
        className="w-full flex items-center justify-between px-4 py-3 bg-fundo-card hover:bg-fundo-card/80 transition-colors text-left"
      >
        <div>
          <p className="font-garamond text-base font-medium text-texto">
            {entry.name}
            {deathYear && (
              <span className="ml-2 text-sm font-normal text-texto-terciario">
                † {deathYear}
              </span>
            )}
          </p>
          <p className="text-xs text-texto-terciario mt-0.5">
            {editionSummary(entry.books)} · {entry.book_count}{' '}
            {entry.book_count === 1 ? 'obra' : 'obras'} — {entry.chunk_count}{' '}
            {entry.chunk_count === 1 ? 'trecho' : 'trechos'} indexados
          </p>
        </div>
        <svg
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          className={`w-4 h-4 shrink-0 ml-3 text-texto-terciario transition-transform ${
            isAuthorOpen ? 'rotate-180' : ''
          }`}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
        </svg>
      </button>

      {isAuthorOpen && (
        <div className="border-t border-fundo-borda divide-y divide-fundo-borda">
          {works.map(({ title, books }) => {
            const workKey = `${entry.name}::${title}`
            const isWorkOpen = openWork === workKey

            return (
              <div key={title}>
                <button
                  onClick={() => onToggleWork(workKey)}
                  className="w-full flex items-center justify-between px-5 py-2.5 bg-fundo hover:bg-fundo-card/40 transition-colors text-left"
                >
                  <span className="font-garamond text-sm font-medium text-texto-secundario">
                    {title}
                  </span>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <span className="text-xs text-texto-terciario bg-fundo-card rounded-full px-2 py-0.5">
                      {books.length} {books.length === 1 ? 'edição' : 'edições'}
                    </span>
                    <svg
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth={1.5}
                      className={`w-3.5 h-3.5 text-texto-terciario transition-transform ${
                        isWorkOpen ? 'rotate-180' : ''
                      }`}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                    </svg>
                  </div>
                </button>

                {isWorkOpen && (
                  <div className="px-5 pb-3 space-y-2">
                    {books.map((book) => (
                      <Link
                        key={book.id}
                        href={`/biblioteca/${book.id}`}
                        className="flex items-center justify-between rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 hover:border-dourado/30 transition-colors"
                      >
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-1.5 text-xs text-texto-terciario">
                            {book.is_primary_source && (
                              <span className="rounded-full bg-dourado/15 px-2 py-0.5 text-dourado font-medium">
                                Primária
                              </span>
                            )}
                            {(book.edition_label || book.collection) && (
                              <span className="font-mono bg-fundo px-1.5 py-0.5 rounded">
                                {book.edition_label || COLLECTION_LABEL[book.collection ?? ''] || book.collection}
                              </span>
                            )}
                            {book.language && <span>{formatLanguage(book.language)}</span>}
                          </div>
                          {book.chunk_count !== undefined && book.chunk_count > 0 && (
                            <p className="text-xs text-texto-terciario mt-0.5">
                              {book.chunk_count} trechos indexados
                            </p>
                          )}
                        </div>
                        <svg
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth={1.5}
                          className="w-4 h-4 shrink-0 ml-2 text-texto-terciario"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
                        </svg>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function AutoresSection({ catalog }: AutoresSectionProps) {
  const [openAuthor, setOpenAuthor] = useState<string | null>(null)
  const [openWork, setOpenWork] = useState<string | null>(null)

  if (catalog.length === 0) {
    return (
      <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center">
        <p className="text-sm text-texto-terciario">Catálogo indisponível.</p>
      </div>
    )
  }

  const withBooks = catalog.filter((e) => e.book_count > 0)
  const withoutBooks = catalog.filter((e) => e.book_count === 0)

  const centuries = groupByCentury(withBooks, e => getAuthorDeathYear(e.name))

  function handleToggleAuthor(name: string) {
    setOpenAuthor(prev => (prev === name ? null : name))
    setOpenWork(null)
  }

  function handleToggleWork(key: string) {
    setOpenWork(prev => (prev === key ? null : key))
  }

  return (
    <div className="space-y-6">
      {/* Contadores rápidos */}
      <div className="flex gap-3 text-xs text-texto-terciario">
        <span>
          <span className="font-medium text-dourado">{catalog.length}</span> Padres conhecidos
        </span>
        <span>·</span>
        <span>
          <span className="font-medium text-texto">{withBooks.length}</span> com obras catalogadas
        </span>
      </div>

      {/* Padres com obras — agrupados por século */}
      {withBooks.length > 0 && (
        <div className="space-y-6">
          {centuries.map(({ label, items }) => (
            <div key={label}>
              <p className="text-xs font-medium text-texto-terciario uppercase tracking-wider px-1 pb-2 border-b border-fundo-borda mb-2">
                {label}
              </p>
              <div className="space-y-2">
                {items.map((entry) => (
                  <AuthorAccordion
                    key={entry.name}
                    entry={entry}
                    openAuthor={openAuthor}
                    openWork={openWork}
                    onToggleAuthor={handleToggleAuthor}
                    onToggleWork={handleToggleWork}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Padres sem obras catalogadas ainda */}
      {withoutBooks.length > 0 && (
        <div>
          <p className="text-xs font-medium text-texto-terciario uppercase tracking-wider mb-2">
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
                  <p className="text-xs text-texto-terciario/60 mt-0.5">
                    {COLLECTION_LABEL[entry.collection] ?? entry.collection}
                  </p>
                </div>
                <span className="text-xs text-texto-terciario/50 shrink-0 ml-3">0 obras</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
