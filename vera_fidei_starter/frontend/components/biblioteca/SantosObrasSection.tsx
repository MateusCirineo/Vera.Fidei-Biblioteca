'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { AuthorEntry, Book } from '@/lib/types'
import { formatLanguage } from '@/lib/language'

const ALL_PUBLISHERS = 'todas'
const UNKNOWN_PUBLISHER = 'Outras editoras'

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

function normalizeText(value: string | null | undefined): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim()
}

function isRealPublisher(label: string | null | undefined, book: Book, author: string): label is string {
  const clean = label?.trim()
  if (!clean) return false

  const normalized = normalizeText(clean)
  if (!normalized || normalized.startsWith('google drive')) return false
  if (['doc', 'pt', 'pdf', 'obra catalogada', 'fonte primaria'].includes(normalized)) return false
  if (normalized === normalizeText(author)) return false
  if (normalized === normalizeText(book.title) || normalized === normalizeText(book.canonical_title)) return false
  if (/^(santo|santa|sao|beato|beata)\b/.test(normalized) && !normalized.includes('editora')) return false
  return true
}

function publisherForBook(book: Book, author: string): string {
  const fileEditor = book.files?.map(file => file.editor).find(label => isRealPublisher(label, book, author))
  if (fileEditor) return fileEditor.trim()
  if (isRealPublisher(book.edition_label, book, author)) return book.edition_label.trim()
  return UNKNOWN_PUBLISHER
}

function publisherGroupsForAuthor(entry: AuthorEntry): PublisherGroup[] {
  const groups: Record<string, Record<string, Book[]>> = {}

  for (const work of entry.works) {
    for (const book of work.books) {
      const publisher = publisherForBook(book, entry.author)
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
    .map(([publisher, works]) => {
      const mappedWorks = Object.entries(works)
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

function totalChunks(entry: AuthorEntry): number {
  return entry.works.reduce(
    (sum, work) => sum + work.books.reduce((workSum, book) => workSum + (book.chunk_count ?? 0), 0),
    0
  )
}

function totalBooks(entry: AuthorEntry): number {
  return entry.works.reduce((sum, work) => sum + work.books.length, 0)
}

function publisherDetailLabel(publisher: string | null): string {
  if (!publisher || publisher === UNKNOWN_PUBLISHER) return 'Editora não identificada no PDF'
  return `Editora: ${publisher}`
}

function EditionLink({ book, publisher }: { book: Book; publisher: string | null }) {
  return (
    <Link
      href={`/biblioteca/${book.id}`}
      className="block rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 transition-colors hover:border-dourado/35 hover:bg-vinho-escuro/10"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-garamond text-lg font-semibold leading-snug text-texto">
            {book.title}
          </p>
          <p className="mt-1 text-xs text-texto-terciario">
            {publisherDetailLabel(publisher)}
          </p>
        </div>
        <span className="shrink-0 rounded-full bg-dourado/15 px-2 py-0.5 text-xs font-medium text-dourado">
          Abrir
        </span>
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
        {book.collection && (
          <span className="rounded-full border border-fundo-borda bg-fundo px-2 py-0.5 font-mono text-texto-terciario">
            {book.collection}
          </span>
        )}
        {book.language && (
          <span className="rounded-full border border-fundo-borda bg-fundo px-2 py-0.5 text-texto-terciario">
            {formatLanguage(book.language)}
          </span>
        )}
        {book.chunk_count !== undefined && (
          <span className="rounded-full border border-fundo-borda bg-fundo px-2 py-0.5 text-texto-terciario">
            {book.chunk_count.toLocaleString('pt-BR')} trechos
          </span>
        )}
        {(book.files?.length ?? 0) > 0 && (
          <span className="rounded-full border border-dourado/25 bg-dourado/10 px-2 py-0.5 text-dourado">
            PDF
          </span>
        )}
      </div>
    </Link>
  )
}

interface SantosObrasSectionProps {
  entries: AuthorEntry[]
}

export default function SantosObrasSection({ entries }: SantosObrasSectionProps) {
  const [selectedAuthor, setSelectedAuthor] = useState<AuthorEntry | null>(null)
  const [selectedWorkTitle, setSelectedWorkTitle] = useState<string | null>(null)
  const [selectedPublisher, setSelectedPublisher] = useState<string | null>(null)
  const [activePublisherTab, setActivePublisherTab] = useState<string>(ALL_PUBLISHERS)

  const publisherGroups = selectedAuthor ? publisherGroupsForAuthor(selectedAuthor) : []
  const activePublisherGroups = activePublisherTab === ALL_PUBLISHERS
    ? publisherGroups
    : publisherGroups.filter(group => group.publisher === activePublisherTab)
  const selectedWork = selectedAuthor && selectedWorkTitle && selectedPublisher
    ? publisherGroups
        .find(group => group.publisher === selectedPublisher)
        ?.works.find(work => work.title === selectedWorkTitle) ?? null
    : null

  if (entries.length === 0) {
    return (
      <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center">
        <p className="text-sm text-texto-terciario">
          Nenhuma obra de santo não patrístico catalogada nesta seleção.
        </p>
      </div>
    )
  }

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
          {selectedAuthor.author}
        </button>

        <div className="border-b border-fundo-borda pb-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
            Obra do santo
          </p>
          <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
            {selectedWork.title}
          </h2>
          <p className="mt-1 text-sm text-texto-secundario">
            {selectedAuthor.author} · {selectedWork.books.length}{' '}
            {selectedWork.books.length === 1 ? 'edição' : 'edições'}
          </p>
          <p className="mt-1 text-xs text-texto-terciario">
            {publisherDetailLabel(selectedPublisher)}
          </p>
        </div>

        <div className="space-y-3">
          {selectedWork.books.map(book => (
            <EditionLink key={book.id} book={book} publisher={selectedPublisher} />
          ))}
        </div>
      </section>
    )
  }

  if (selectedAuthor) {
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
          Obras dos Santos
        </button>

        <div className="rounded-lg border border-dourado/25 bg-dourado/5 p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
                Autor santo
              </p>
              <h2 className="mt-1 font-garamond text-3xl font-semibold leading-tight text-texto">
                {selectedAuthor.author}
              </h2>
              <p className="mt-2 text-sm text-texto-secundario">
                {selectedAuthor.works.length}{' '}
                {selectedAuthor.works.length === 1 ? 'obra' : 'obras'} · {publisherGroups.length}{' '}
                {publisherGroups.length === 1 ? 'editora' : 'editoras'} · {totalChunks(selectedAuthor).toLocaleString('pt-BR')} trechos indexados
              </p>
            </div>
            <span className="shrink-0 rounded-full bg-dourado/15 px-2.5 py-1 text-xs font-medium text-dourado">
              {totalBooks(selectedAuthor)}
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
              {totalBooks(selectedAuthor)}
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
                  {group.publisher === UNKNOWN_PUBLISHER && (
                    <p className="mt-0.5 text-xs text-texto-terciario">
                      Sem editora localizada no PDF; estes itens ficam reunidos aqui sem metadado inventado.
                    </p>
                  )}
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
    <section className="space-y-4">
      <div className="border-b border-fundo-borda pb-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
          Obras dos Santos
        </p>
        <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
          Santos não patrísticos
        </h2>
        <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
          Escritos de santos medievais, modernos e doutores posteriores aos Padres da Igreja.
        </p>
      </div>

      <nav className="space-y-2">
        {entries.map((entry) => (
          <button
            key={entry.author}
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
                {entry.author}
              </span>
              <span className="mt-0.5 block text-xs text-texto-terciario">
                {entry.works.length} {entry.works.length === 1 ? 'obra' : 'obras'} · {totalChunks(entry).toLocaleString('pt-BR')} trechos
              </span>
            </span>
            <span className="ml-3 shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
              {totalBooks(entry)}
            </span>
          </button>
        ))}
      </nav>
    </section>
  )
}
