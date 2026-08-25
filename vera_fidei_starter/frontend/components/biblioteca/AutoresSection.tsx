'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { AuthorCatalogEntry, Book } from '@/lib/types'
import { formatLanguage } from '@/lib/language'
import { groupByCentury, getAuthorDeathYear } from '@/lib/century'
import { ALL_PUBLISHERS, UNKNOWN_PUBLISHER, publisherForBook } from '@/lib/publisher'

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

type PublisherWork = {
  title: string
  books: Book[]
}

type PublisherGroup = {
  publisher: string
  works: PublisherWork[]
  bookCount: number
  chunkCount: number
}

function publisherGroupsForWorks(works: PublisherWork[], author: string): PublisherGroup[] {
  const groups: Record<string, Record<string, Book[]>> = {}

  for (const work of works) {
    for (const book of work.books) {
      const publisher = publisherForBook(book, author)
      if (!groups[publisher]) groups[publisher] = {}
      if (!groups[publisher][work.title]) groups[publisher][work.title] = []
      groups[publisher][work.title].push(book)
    }
  }

  return Object.entries(groups)
    .sort(([a], [b]) => {
      if (a === UNKNOWN_PUBLISHER) return 1
      if (b === UNKNOWN_PUBLISHER) return -1
      return a.localeCompare(b, 'pt')
    })
    .map(([publisher, groupedWorks]) => {
      const mappedWorks = Object.entries(groupedWorks)
        .sort(([a], [b]) => a.localeCompare(b, 'pt'))
        .map(([title, books]) => ({ title, books }))
      return {
        publisher,
        works: mappedWorks,
        bookCount: mappedWorks.reduce((sum, work) => sum + work.books.length, 0),
        chunkCount: mappedWorks.reduce(
          (sum, work) => sum + work.books.reduce((bookSum, book) => bookSum + (book.chunk_count ?? 0), 0),
          0
        ),
      }
    })
}

function workSummary(books: Book[]): string {
  const languages = [...new Set(books.map(book => book.language).filter(Boolean))]
  const chunks = books.reduce((sum, book) => sum + (book.chunk_count ?? 0), 0)
  const parts = [
    languages.length > 0 ? languages.map(language => formatLanguage(language!)).join(' · ') : null,
    chunks > 0 ? `${chunks.toLocaleString('pt-BR')} trechos` : null,
  ].filter(Boolean)
  return parts.length > 0 ? parts.join(' · ') : 'Obra catalogada'
}

function publisherDetailLabel(publisher: string | null): string {
  if (!publisher || publisher === UNKNOWN_PUBLISHER) return 'Editora não identificada no PDF'
  return `Editora: ${publisher}`
}

interface AutoresSectionProps {
  catalog: AuthorCatalogEntry[]
}

function EditionLink({ book }: { book: Book }) {
  const publisher = publisherForBook(book, book.canonical_author ?? book.author)
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
              {publisher}
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
  const [selectedPublisher, setSelectedPublisher] = useState<string | null>(null)
  const [activePublisherTab, setActivePublisherTab] = useState<string>(ALL_PUBLISHERS)

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
  const publisherGroups = selectedAuthor ? publisherGroupsForWorks(selectedWorks, selectedAuthor.name) : []
  const activePublisherGroups = activePublisherTab === ALL_PUBLISHERS
    ? publisherGroups
    : publisherGroups.filter(group => group.publisher === activePublisherTab)
  const selectedWork = selectedAuthor && selectedWorkTitle && selectedPublisher
    ? publisherGroups
        .find(group => group.publisher === selectedPublisher)
        ?.works.find(work => work.title === selectedWorkTitle) ?? null
    : null

  if (selectedAuthor && selectedWork) {
    return (
      <section className="space-y-4">
        <button
          type="button"
          onClick={() => {
            setSelectedWorkTitle(null)
            setSelectedPublisher(null)
          }}
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
          <p className="mt-1 text-xs text-texto-terciario">
            {publisherDetailLabel(selectedPublisher)}
          </p>
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
            setSelectedPublisher(null)
            setActivePublisherTab(ALL_PUBLISHERS)
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

        <div className="flex flex-wrap gap-2 border-b border-fundo-borda pb-3">
          <button
            type="button"
            onClick={() => setActivePublisherTab(ALL_PUBLISHERS)}
            className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
              activePublisherTab === ALL_PUBLISHERS
                ? 'border-dourado/40 bg-dourado/10 text-dourado'
                : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
            }`}
          >
            Todas
            <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
              activePublisherTab === ALL_PUBLISHERS ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
            }`}>
              {selectedAuthor.book_count}
            </span>
          </button>

          {publisherGroups.map(group => {
            const isActive = activePublisherTab === group.publisher
            return (
              <button
                key={group.publisher}
                type="button"
                onClick={() => setActivePublisherTab(group.publisher)}
                className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border-dourado/40 bg-dourado/10 text-dourado'
                    : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
                }`}
              >
                {group.publisher}
                <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
                  isActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
                }`}>
                  {group.bookCount}
                </span>
              </button>
            )
          })}
        </div>

        <div className="space-y-5">
          {activePublisherGroups.map(group => (
            <section key={group.publisher} className="space-y-2">
              <div className="flex items-end justify-between gap-3 border-b border-fundo-borda pb-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
                    Editora
                  </p>
                  <h3 className="font-garamond text-xl font-medium text-texto">
                    {group.publisher}
                  </h3>
                </div>
                <span className="shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
                  {group.bookCount}
                </span>
              </div>

              <div className="space-y-2">
                {group.works.map(({ title, books }) => (
                  <button
                    key={`${group.publisher}-${title}`}
                    type="button"
                    onClick={() => {
                      setSelectedPublisher(group.publisher)
                      setSelectedWorkTitle(title)
                    }}
                    className="flex w-full items-center justify-between gap-3 rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left transition-colors hover:border-dourado/30 hover:bg-vinho-escuro/10"
                  >
                    <span className="min-w-0">
                      <span className="block font-garamond text-base font-medium leading-snug text-texto">
                        {title}
                      </span>
                      <span className="mt-0.5 block text-xs text-texto-terciario">
                        {workSummary(books)}
                      </span>
                    </span>
                    <span className="ml-3 shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
                      {books.length}
                    </span>
                  </button>
                ))}
              </div>
            </section>
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
                        setSelectedPublisher(null)
                        setActivePublisherTab(ALL_PUBLISHERS)
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
