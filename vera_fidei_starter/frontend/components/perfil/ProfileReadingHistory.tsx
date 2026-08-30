'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  listReadingHistory,
  restartReadingProgress,
} from '@/lib/api'
import {
  buildTrackedViewerHref,
  type ReadingProgress,
  type ReadingProgressSnapshot,
} from '@/lib/readingProgress'

const PAGE_SIZE = 6

function workTitle(item: ReadingProgress): string {
  return item.book.canonical_title || item.book.title || item.file.original_filename
}

function authorName(item: ReadingProgress): string | null {
  return item.book.canonical_author || item.book.author || null
}

function editionDetails(item: ReadingProgress): string[] {
  return [
    item.book.edition_label,
    item.file.editor ? `Editor: ${item.file.editor}` : null,
    item.file.translator ? `Tradutor: ${item.file.translator}` : null,
    item.file.volume_number ? `Vol. ${item.file.volume_number}` : null,
  ].filter((value): value is string => Boolean(value))
}

function formatLastRead(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Data não informada'

  return new Intl.DateTimeFormat('pt-BR', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function progressValue(item: ReadingProgress): number | null {
  if (item.completed) return 100
  if (item.progress_percent !== null && Number.isFinite(item.progress_percent)) {
    return Math.max(0, Math.min(100, item.progress_percent))
  }
  return null
}

function mergeRestartedProgress(
  item: ReadingProgress,
  snapshot: ReadingProgressSnapshot,
): ReadingProgress {
  if ('book' in snapshot && 'file' in snapshot) return snapshot

  return {
    ...item,
    current_page: snapshot.current_page,
    total_pages: snapshot.total_pages ?? item.total_pages,
    progress_percent: null,
    completed: false,
    start_page: snapshot.start_page ?? item.start_page,
    last_read_at: snapshot.saved_at,
    viewer_href: snapshot.viewer_href ?? item.viewer_href,
  }
}

export default function ProfileReadingHistory({
  userId,
  embedded = false,
}: {
  userId: number
  embedded?: boolean
}) {
  const [items, setItems] = useState<ReadingProgress[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [actionError, setActionError] = useState('')
  const [notice, setNotice] = useState('')
  const [restartingKey, setRestartingKey] = useState<string | null>(null)

  const load = useCallback(async (nextPage: number) => {
    setLoading(true)
    setLoadError('')
    setActionError('')
    setNotice('')

    try {
      const data = await listReadingHistory(PAGE_SIZE, (nextPage - 1) * PAGE_SIZE)
      setItems(data.items)
      setTotal(data.total)
      setPage(nextPage)
    } catch (caughtError: unknown) {
      setLoadError(caughtError instanceof Error ? caughtError.message : 'Não foi possível carregar suas leituras.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load(1)
  }, [load])

  const totalPages = useMemo(
    () => Math.max(1, Math.ceil(total / PAGE_SIZE)),
    [total],
  )

  async function handleRestart(item: ReadingProgress) {
    const title = workTitle(item)
    if (!window.confirm(`Recomeçar “${title}” desde a página ${item.start_page}?`)) return

    const itemKey = `${item.book_id}:${item.book_file_id}`
    setRestartingKey(itemKey)
    setActionError('')
    setNotice('')

    try {
      const restarted = await restartReadingProgress(
        userId,
        item.book_file_id,
        item.book_id,
        item.start_page,
        item.total_pages,
      )
      setItems((current) => current.map((entry) => (
        entry.book_id === item.book_id && entry.book_file_id === item.book_file_id
          ? mergeRestartedProgress(entry, restarted)
          : entry
      )))
      setNotice(`“${title}” foi reiniciada na página ${item.start_page}.`)
    } catch (restartError: unknown) {
      setActionError(restartError instanceof Error ? restartError.message : 'Não foi possível recomeçar esta leitura.')
    } finally {
      setRestartingKey(null)
    }
  }

  return (
    <section
      id={embedded ? 'historico-leituras' : 'leituras'}
      className={embedded
        ? 'pt-5'
        : 'mt-6 rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6'}
      aria-labelledby="reading-history-title"
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
            Leitura
          </p>
          <h2 id="reading-history-title" className="mt-1 font-garamond text-xl text-texto">
            Continue de onde parou
          </h2>
          <p className="mt-1 max-w-2xl text-xs leading-relaxed text-texto-terciario">
            Retome seus PDFs na última página lida. Este recurso está disponível em todos os planos.
          </p>
        </div>

        {!loading && !loadError && total > 0 && (
          <p className="shrink-0 text-xs text-texto-terciario">
            {total} leitura{total === 1 ? '' : 's'} recente{total === 1 ? '' : 's'}
          </p>
        )}
      </div>

      <div className="sr-only" aria-live="polite">
        {loading ? 'Carregando histórico de leitura.' : notice || actionError || loadError}
      </div>

      {loading && (
        <div className="mt-5 grid gap-3 sm:grid-cols-2" aria-hidden="true">
          {Array.from({ length: 2 }).map((_, index) => (
            <div
              key={index}
              className="h-48 animate-pulse rounded-lg border border-fundo-borda bg-fundo motion-reduce:animate-none"
            />
          ))}
        </div>
      )}

      {!loading && loadError && (
        <div className="mt-5 rounded-lg border border-vermelho/35 bg-vermelho/5 px-4 py-5 text-center">
          <p className="text-sm text-vermelho">{loadError}</p>
          <button
            type="button"
            onClick={() => void load(page)}
            className="mt-3 rounded-md border border-vermelho/40 px-3 py-2 text-xs text-vermelho transition-colors hover:bg-vermelho hover:text-white"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {!loading && !loadError && items.length === 0 && (
        <div className="mt-5 rounded-lg border border-fundo-borda bg-fundo px-4 py-8 text-center">
          <p className="text-sm text-texto-terciario">
            Nenhuma leitura iniciada ainda. Abra um PDF para salvar seu progresso automaticamente.
          </p>
          <Link
            href="/biblioteca"
            className="mt-4 inline-flex rounded-md border border-dourado/40 px-3 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado hover:text-fundo"
          >
            Explorar a Biblioteca
          </Link>
        </div>
      )}

      {!loading && !loadError && items.length > 0 && (
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {items.map((item) => {
            const title = workTitle(item)
            const author = authorName(item)
            const details = editionDetails(item)
            const progress = progressValue(item)
            const hasMeasuredProgress = progress !== null
            const restarting = restartingKey === `${item.book_id}:${item.book_file_id}`

            return (
              <article
                key={`${item.book_id}:${item.book_file_id}`}
                className="flex min-h-full flex-col rounded-lg border border-fundo-borda bg-fundo p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h3 className="line-clamp-2 font-garamond text-lg font-medium leading-snug text-texto">
                      {title}
                    </h3>
                    {author && (
                      <p className="mt-1 line-clamp-1 text-xs text-dourado">{author}</p>
                    )}
                  </div>
                  {item.completed && (
                    <span className="shrink-0 rounded-full border border-emerald-700/35 bg-emerald-950/25 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                      Concluída
                    </span>
                  )}
                </div>

                {details.length > 0 && (
                  <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-texto-terciario">
                    {details.join(' · ')}
                  </p>
                )}
                <p
                  className="mt-1 truncate text-[11px] text-texto-terciario/80"
                  title={item.file.original_filename}
                >
                  {item.file.original_filename}
                </p>

                <div className="mt-4 border-t border-fundo-borda pt-3">
                  <div className="flex items-center justify-between gap-3 text-xs">
                    <span className="font-medium text-texto-secundario">
                      Página {item.current_page}
                      {item.total_pages ? ` de ${item.total_pages}` : ''}
                    </span>
                    {hasMeasuredProgress && (
                      <span className="font-mono text-[11px] text-dourado">
                        {Math.round(progress)}%
                      </span>
                    )}
                  </div>
                  {hasMeasuredProgress && (
                    <div
                      className="mt-2 h-1.5 overflow-hidden rounded-full bg-fundo-card"
                      role="progressbar"
                      aria-label={`Progresso de leitura de ${title}`}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={Math.round(progress)}
                    >
                      <div
                        className="h-full rounded-full bg-dourado transition-[width]"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  )}
                  <p className="mt-2 text-[11px] text-texto-terciario">
                    Última leitura: {formatLastRead(item.last_read_at)}
                  </p>
                </div>

                <div className="mt-auto flex flex-wrap justify-end gap-2 pt-4">
                  <button
                    type="button"
                    onClick={() => void handleRestart(item)}
                    disabled={restarting}
                    className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado disabled:cursor-wait disabled:opacity-50"
                  >
                    {restarting ? 'Recomeçando...' : 'Recomeçar'}
                  </button>
                  <Link
                    href={buildTrackedViewerHref(item.book_file_id, item.book_id, item.current_page)}
                    prefetch={false}
                    className="rounded-md bg-dourado px-3 py-2 text-xs font-semibold text-fundo transition-colors hover:bg-dourado-claro"
                  >
                    Continuar lendo
                  </Link>
                </div>
              </article>
            )
          })}
        </div>
      )}

      {actionError && !loadError && (
        <p className="mt-4 text-xs text-vermelho" role="alert">
          {actionError}
        </p>
      )}

      {notice && !loadError && !actionError && (
        <p className="mt-4 text-xs text-dourado" role="status">
          {notice}
        </p>
      )}

      {!loading && !loadError && totalPages > 1 && (
        <nav className="mt-5 flex items-center justify-center gap-2" aria-label="Páginas do histórico de leitura">
          <button
            type="button"
            onClick={() => void load(page - 1)}
            disabled={page <= 1}
            className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado disabled:opacity-40"
          >
            Anterior
          </button>
          <span className="px-2 text-xs text-texto-terciario">
            {page} / {totalPages}
          </span>
          <button
            type="button"
            onClick={() => void load(page + 1)}
            disabled={page >= totalPages}
            className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado disabled:opacity-40"
          >
            Próxima
          </button>
        </nav>
      )}
    </section>
  )
}
