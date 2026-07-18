'use client'

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import { listBooks, deleteBook, updateBookFileMeta, getPdfDownloadUrl } from '@/lib/api'
import type { Book, BookFile } from '@/lib/types'

type EditState = {
  fileId: number
  bookId: number
  editor: string
  translator: string
}

type FilterMode = 'all' | 'withPdf' | 'missingPublisher'

type BookGroup = {
  author: string
  books: Book[]
}

const collator = new Intl.Collator('pt-BR', { sensitivity: 'base' })

function normalizeSearch(value: string | null | undefined): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

function bookAuthor(book: Book): string {
  return book.canonical_author || book.author || 'Autor desconhecido'
}

function bookTitle(book: Book): string {
  return book.canonical_title || book.title
}

function filePublisher(file: BookFile): string {
  return file.editor?.trim() || 'Editora não informada'
}

function bookSearchText(book: Book): string {
  return normalizeSearch([
    book.title,
    book.canonical_title,
    book.author,
    book.canonical_author,
    book.collection,
    book.edition_label,
    book.source_label,
    book.language,
    ...(book.files ?? []).flatMap((file) => [
      file.original_filename,
      file.editor,
      file.translator,
    ]),
  ].filter(Boolean).join(' '))
}

function hasPublisher(book: Book): boolean {
  return (book.files ?? []).some((file) => Boolean(file.editor?.trim()))
}

function sortBooks(books: Book[]): Book[] {
  return [...books].sort((a, b) => {
    const authorCompare = collator.compare(bookAuthor(a), bookAuthor(b))
    if (authorCompare !== 0) return authorCompare

    const publisherA = a.files?.[0]?.editor ?? ''
    const publisherB = b.files?.[0]?.editor ?? ''
    const publisherCompare = collator.compare(publisherA, publisherB)
    if (publisherCompare !== 0) return publisherCompare

    const volumeA = a.volume_number ?? a.files?.[0]?.volume_number ?? 0
    const volumeB = b.volume_number ?? b.files?.[0]?.volume_number ?? 0
    if (volumeA !== volumeB) return volumeA - volumeB

    return collator.compare(bookTitle(a), bookTitle(b))
  })
}

function groupBooks(books: Book[]): BookGroup[] {
  const grouped = new Map<string, Book[]>()
  for (const book of books) {
    const author = bookAuthor(book)
    grouped.set(author, [...(grouped.get(author) ?? []), book])
  }

  return Array.from(grouped.entries())
    .sort(([a], [b]) => collator.compare(a, b))
    .map(([author, groupBooks]) => ({ author, books: sortBooks(groupBooks) }))
}

function formatDate(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat('pt-BR').format(date)
}

export default function BookList() {
  const [books, setBooks] = useState<Book[]>([])
  const [loading, setLoading] = useState(true)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<FilterMode>('all')

  const [editing, setEditing] = useState<EditState | null>(null)
  const [saving, setSaving] = useState(false)
  const [savedFileId, setSavedFileId] = useState<number | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listBooks()
      setBooks(data)
    } catch {
      setError('Erro ao carregar obras.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const summary = useMemo(() => {
    const pdfs = books.reduce((sum, book) => sum + (book.files?.length ?? 0), 0)
    const chunks = books.reduce((sum, book) => sum + (book.chunk_count ?? 0), 0)
    const publishers = new Set<string>()
    for (const book of books) {
      for (const file of book.files ?? []) {
        if (file.editor?.trim()) publishers.add(file.editor.trim())
      }
    }
    return { pdfs, chunks, publishers: publishers.size }
  }, [books])

  const visibleBooks = useMemo(() => {
    const cleanQuery = normalizeSearch(query.trim())
    return sortBooks(books).filter((book) => {
      if (filter === 'withPdf' && (book.files?.length ?? 0) === 0) return false
      if (filter === 'missingPublisher' && hasPublisher(book)) return false
      if (cleanQuery && !bookSearchText(book).includes(cleanQuery)) return false
      return true
    })
  }, [books, filter, query])

  const groupedBooks = useMemo(() => groupBooks(visibleBooks), [visibleBooks])

  async function handleDelete(book: Book) {
    if (!window.confirm(`Excluir "${book.title}" e todos os seus trechos?\nEsta ação não pode ser desfeita.`)) {
      return
    }
    setDeletingId(book.id)
    setError(null)
    try {
      await deleteBook(book.id)
      setBooks((prev) => prev.filter((b) => b.id !== book.id))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao excluir obra.')
    } finally {
      setDeletingId(null)
    }
  }

  function openEdit(book: Book, file: BookFile) {
    setEditing({
      fileId: file.id,
      bookId: book.id,
      editor: file.editor ?? '',
      translator: file.translator ?? '',
    })
    setSavedFileId(null)
  }

  function cancelEdit() {
    setEditing(null)
  }

  async function handleSave() {
    if (!editing) return
    setSaving(true)
    try {
      await updateBookFileMeta(
        editing.bookId,
        editing.fileId,
        editing.editor.trim() || null,
        editing.translator.trim() || null,
      )
      setBooks((prev) =>
        prev.map((book) => {
          if (book.id !== editing.bookId) return book
          return {
            ...book,
            files: book.files?.map((file) =>
              file.id === editing.fileId
                ? {
                    ...file,
                    editor: editing.editor.trim() || null,
                    translator: editing.translator.trim() || null,
                  }
                : file,
            ),
          }
        }),
      )
      setSavedFileId(editing.fileId)
      setEditing(null)
      setTimeout(() => setSavedFileId(null), 2500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="space-y-5">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-dourado/70">
            Acervo indexado
          </p>
          <h2 className="mt-1 font-eb-garamond text-2xl text-texto">
            Obras anexadas
          </h2>
          <p className="mt-1 max-w-2xl text-sm text-texto-terciario">
            Organize os PDFs usados pela biblioteca e pelo verificador de citações.
          </p>
        </div>
        <button
          onClick={load}
          className="self-start rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado/60 hover:text-dourado lg:self-auto"
        >
          Atualizar
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <SummaryTile label="Obras" value={books.length.toLocaleString('pt-BR')} />
        <SummaryTile label="PDFs anexados" value={summary.pdfs.toLocaleString('pt-BR')} />
        <SummaryTile label="Editoras" value={summary.publishers.toLocaleString('pt-BR')} />
        <SummaryTile label="Trechos" value={summary.chunks.toLocaleString('pt-BR')} />
      </div>

      <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
          <label className="block">
            <span className="sr-only">Pesquisar obra</span>
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Pesquisar obra, autor, editora, tradutor ou arquivo"
              className="h-11 w-full rounded-md border border-fundo-borda bg-fundo px-3 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/70"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <FilterButton active={filter === 'all'} onClick={() => setFilter('all')}>
              Todas
            </FilterButton>
            <FilterButton active={filter === 'withPdf'} onClick={() => setFilter('withPdf')}>
              Com PDF
            </FilterButton>
            <FilterButton active={filter === 'missingPublisher'} onClick={() => setFilter('missingPublisher')}>
              Sem editora
            </FilterButton>
          </div>
        </div>
        <p className="mt-3 text-xs text-texto-terciario">
          {visibleBooks.length.toLocaleString('pt-BR')} de {books.length.toLocaleString('pt-BR')} obras exibidas.
        </p>
      </div>

      {error && (
        <p className="rounded-md border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-300">
          {error}
        </p>
      )}

      {loading ? (
        <p className="rounded-lg border border-fundo-borda bg-fundo-card px-4 py-8 text-center text-sm text-texto-terciario">
          Carregando obras...
        </p>
      ) : books.length === 0 ? (
        <p className="rounded-lg border border-fundo-borda bg-fundo-card px-4 py-8 text-center text-sm text-texto-terciario">
          Nenhuma obra indexada.
        </p>
      ) : groupedBooks.length === 0 ? (
        <p className="rounded-lg border border-fundo-borda bg-fundo-card px-4 py-8 text-center text-sm text-texto-terciario">
          Nenhuma obra encontrada com estes filtros.
        </p>
      ) : (
        <div className="space-y-5">
          {groupedBooks.map((group) => (
            <section key={group.author} className="overflow-hidden rounded-lg border border-fundo-borda bg-fundo-card">
              <div className="flex flex-col gap-1 border-b border-fundo-borda bg-fundo/60 px-4 py-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <h3 className="font-eb-garamond text-lg text-texto">{group.author}</h3>
                  <p className="text-xs text-texto-terciario">
                    {group.books.length} {group.books.length === 1 ? 'obra' : 'obras'} ·{' '}
                    {group.books.reduce((sum, book) => sum + (book.files?.length ?? 0), 0)} PDFs
                  </p>
                </div>
                <p className="text-xs text-texto-terciario">
                  {group.books.reduce((sum, book) => sum + (book.chunk_count ?? 0), 0).toLocaleString('pt-BR')} trechos
                </p>
              </div>

              <div className="divide-y divide-fundo-borda">
                {group.books.map((book) => (
                  <article key={book.id} className="px-4 py-4">
                    <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto]">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <h4 className="break-words text-sm font-semibold text-texto">
                            {bookTitle(book)}
                          </h4>
                          {book.is_primary_source && (
                            <span className="rounded-full border border-dourado/30 px-2 py-0.5 text-[11px] text-dourado">
                              Fonte primária
                            </span>
                          )}
                        </div>
                        <p className="mt-1 text-xs text-texto-terciario">
                          {book.collection || 'Coleção não informada'}
                          {book.language && <span> · {book.language.toUpperCase()}</span>}
                          <span> · {(book.chunk_count ?? 0).toLocaleString('pt-BR')} trechos</span>
                        </p>
                      </div>

                      <button
                        onClick={() => handleDelete(book)}
                        disabled={deletingId === book.id}
                        className="h-9 rounded-md border border-red-500/30 px-3 text-xs text-red-300 transition-colors hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        {deletingId === book.id ? 'Excluindo...' : 'Excluir obra'}
                      </button>
                    </div>

                    {book.files && book.files.length > 0 ? (
                      <div className="mt-4 space-y-2">
                        {book.files.map((file) => (
                          <div key={file.id} className="rounded-md border border-fundo-borda/80 bg-fundo/40 p-3">
                            <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
                              <div className="min-w-0 space-y-2">
                                <p className="break-words text-xs font-medium text-texto-secundario">
                                  {file.original_filename}
                                </p>
                                <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-texto-terciario">
                                  <span>
                                    Editora:{' '}
                                    <span className="text-texto-secundario">
                                      {savedFileId === file.id ? (
                                        <span className="text-green-400">Salvo</span>
                                      ) : (
                                        filePublisher(file)
                                      )}
                                    </span>
                                  </span>
                                  <span>
                                    Tradutor:{' '}
                                    <span className="text-texto-secundario">
                                      {file.translator?.trim() || 'Não informado'}
                                    </span>
                                  </span>
                                  {file.volume_number !== null && (
                                    <span>Volume {file.volume_number}</span>
                                  )}
                                  <span>Anexado em {formatDate(file.created_at)}</span>
                                </div>
                              </div>

                              <div className="flex flex-wrap gap-2 lg:justify-end">
                                <a
                                  href={getPdfDownloadUrl(file.id)}
                                  download={file.original_filename}
                                  className="inline-flex h-9 items-center rounded-md bg-dourado px-3 text-xs font-semibold text-fundo transition-colors hover:bg-dourado/90"
                                >
                                  Baixar PDF
                                </a>
                                <button
                                  onClick={() =>
                                    editing?.fileId === file.id ? cancelEdit() : openEdit(book, file)
                                  }
                                  className="h-9 rounded-md border border-fundo-borda px-3 text-xs text-texto-secundario transition-colors hover:border-dourado/60 hover:text-dourado"
                                >
                                  {editing?.fileId === file.id ? 'Cancelar' : 'Editar dados'}
                                </button>
                              </div>
                            </div>

                            {editing?.fileId === file.id && (
                              <div className="mt-3 rounded-md border border-dourado/20 bg-dourado/5 p-3">
                                <div className="grid gap-3 sm:grid-cols-2">
                                  <label className="block">
                                    <span className="mb-1 block text-xs text-texto-terciario">Editora</span>
                                    <input
                                      type="text"
                                      value={editing.editor}
                                      onChange={(event) => setEditing({ ...editing, editor: event.target.value })}
                                      placeholder="Ex: Paulus"
                                      className="h-10 w-full rounded-md border border-fundo-borda bg-fundo-card px-3 text-sm text-texto outline-none placeholder:text-texto-terciario focus:border-dourado/60"
                                    />
                                  </label>
                                  <label className="block">
                                    <span className="mb-1 block text-xs text-texto-terciario">Tradutor</span>
                                    <input
                                      type="text"
                                      value={editing.translator}
                                      onChange={(event) => setEditing({ ...editing, translator: event.target.value })}
                                      placeholder="Ex: Lourenço Costa"
                                      className="h-10 w-full rounded-md border border-fundo-borda bg-fundo-card px-3 text-sm text-texto outline-none placeholder:text-texto-terciario focus:border-dourado/60"
                                    />
                                  </label>
                                </div>
                                <button
                                  onClick={handleSave}
                                  disabled={saving}
                                  className="mt-3 h-9 rounded-md bg-dourado px-4 text-xs font-semibold text-fundo transition-colors hover:bg-dourado/90 disabled:cursor-not-allowed disabled:opacity-40"
                                >
                                  {saving ? 'Salvando...' : 'Salvar metadados'}
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-3 rounded-md border border-fundo-borda/80 bg-fundo/40 px-3 py-2 text-xs text-texto-terciario">
                        Esta obra ainda não tem PDF anexado.
                      </p>
                    )}
                  </article>
                ))}
              </div>
            </section>
          ))}
        </div>
      )}
    </section>
  )
}

function SummaryTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
      <p className="text-xs uppercase tracking-[0.18em] text-texto-terciario">{label}</p>
      <p className="mt-2 font-eb-garamond text-2xl text-dourado">{value}</p>
    </div>
  )
}

function FilterButton({
  active,
  onClick,
  children,
}: {
  active: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'h-10 rounded-md border px-3 text-xs transition-colors',
        active
          ? 'border-dourado bg-dourado text-fundo'
          : 'border-fundo-borda text-texto-secundario hover:border-dourado/60 hover:text-dourado',
      ].join(' ')}
    >
      {children}
    </button>
  )
}
