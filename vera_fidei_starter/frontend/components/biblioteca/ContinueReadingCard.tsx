'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { getUser } from '@/lib/auth'
import {
  buildTrackedViewerHref,
  listLocalReadingProgress,
  listReadingHistory,
  type ReadingProgress,
  type ReadingProgressSnapshot,
} from '@/lib/readingProgress'

function lastReadAt(item: ReadingProgressSnapshot): number {
  const value = 'saved_at' in item ? item.saved_at : item.last_read_at
  const parsed = Date.parse(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function itemKey(item: ReadingProgressSnapshot): string {
  return `${item.book_id}:${item.book_file_id}`
}

function isCompleted(item: ReadingProgressSnapshot): boolean {
  if ('book' in item) return item.completed
  if (typeof item.completed === 'boolean') return item.completed
  return Boolean(item.end_page && item.current_page >= item.end_page)
}

function progressPercent(item: ReadingProgressSnapshot): number | null {
  const value = 'book' in item ? item.progress_percent : item.progress_percent ?? null
  return typeof value === 'number' && Number.isFinite(value)
    ? Math.max(0, Math.min(100, value))
    : null
}

function preferCandidate(
  current: ReadingProgressSnapshot | undefined,
  candidate: ReadingProgressSnapshot,
): ReadingProgressSnapshot {
  if (!current) return candidate

  // For the same logical work/file, an authoritative newer server revision
  // wins even if the device clock made the local saved_at look more recent.
  if ('book' in candidate && !('book' in current)) {
    if (candidate.revision > (current.revision ?? 0)) return candidate
  }
  if (!('book' in candidate) && 'book' in current) {
    if (current.revision > (candidate.revision ?? 0)) return current
  }
  return lastReadAt(candidate) > lastReadAt(current) ? candidate : current
}

function chooseContinueReadingItem(
  candidates: ReadingProgressSnapshot[],
): ReadingProgressSnapshot | null {
  const byFile = new Map<string, ReadingProgressSnapshot>()
  for (const candidate of candidates) {
    byFile.set(itemKey(candidate), preferCandidate(byFile.get(itemKey(candidate)), candidate))
  }
  const sorted = [...byFile.values()].sort((left, right) => lastReadAt(right) - lastReadAt(left))
  return sorted.find((candidate) => !isCompleted(candidate)) ?? sorted[0] ?? null
}

function titleFor(item: ReadingProgressSnapshot): string {
  if ('book' in item) return item.book.canonical_title || item.book.title
  return item.book_title || item.original_filename || 'Leitura em andamento'
}

function authorFor(item: ReadingProgressSnapshot): string | null {
  if ('book' in item) return item.book.canonical_author || item.book.author
  return item.book_author ?? null
}

export default function ContinueReadingCard() {
  const [item, setItem] = useState<ReadingProgressSnapshot | null>(null)

  useEffect(() => {
    let active = true
    void getUser().then(async (user) => {
      if (!active || !user) return

      const local = listLocalReadingProgress(user.id)
      if (active) setItem(chooseContinueReadingItem(local))
      try {
        const remote: ReadingProgress[] = []
        let offset = 0
        let total = 1
        do {
          const history = await listReadingHistory(100, offset)
          total = history.total
          for (const entry of history.items) {
            remote.push(entry)
          }
          offset += history.items.length
          if (history.items.some((entry) => !entry.completed) || history.items.length === 0) break
        } while (offset < total)

        if (active) setItem(chooseContinueReadingItem([...local, ...remote]))
      } catch {
        if (active) setItem(chooseContinueReadingItem(local))
      }
    })
    return () => {
      active = false
    }
  }, [])

  if (!item) return null

  const title = titleFor(item)
  const author = authorFor(item)
  const page = item.current_page
  const totalPages = item.total_pages
  const percent = progressPercent(item)
  const href = buildTrackedViewerHref(item.book_file_id, item.book_id, page)

  return (
    <section
      className="mb-7 overflow-hidden rounded-lg border border-dourado/25 bg-gradient-to-br from-dourado/10 via-fundo-card to-fundo-card p-4 sm:p-5"
      aria-labelledby="continue-reading-title"
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-dourado">
            Sua leitura
          </p>
          <h2 id="continue-reading-title" className="mt-1 truncate font-garamond text-xl text-texto">
            {title}
          </h2>
          {author && <p className="mt-0.5 truncate text-xs text-texto-terciario">{author}</p>}
          <p className="mt-2 text-sm font-medium text-texto-secundario">
            Página {page}{totalPages ? ` de ${totalPages}` : ''}
          </p>
          {percent !== null && (
            <div
              className="mt-2 h-1.5 max-w-sm overflow-hidden rounded-full bg-fundo"
              role="progressbar"
              aria-label={`Progresso de leitura de ${title}`}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(percent)}
            >
              <div className="h-full rounded-full bg-dourado" style={{ width: `${percent}%` }} />
            </div>
          )}
        </div>
        <Link
          href={href}
          prefetch={false}
          className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-md bg-dourado px-4 py-2 text-sm font-semibold text-fundo transition-colors hover:bg-dourado-claro focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-dourado"
        >
          {isCompleted(item) ? 'Abrir novamente' : 'Continuar lendo'}
          <span className="ml-2" aria-hidden="true">→</span>
        </Link>
      </div>
    </section>
  )
}
