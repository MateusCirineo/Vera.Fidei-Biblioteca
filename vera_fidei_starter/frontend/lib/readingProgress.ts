import { authBearerHeaders } from './auth.ts'
import { getApiBase } from './api-base.ts'
import { DEFAULT_REQUEST_TIMEOUT_MS, fetchWithTimeout } from './http.ts'

const BASE = getApiBase()
const LOCAL_PROGRESS_PREFIX = 'vf:reading-progress:v2'

export type ReadingEvent = 'open' | 'progress' | 'restart'

export interface ReadingProgressPayload {
  current_page: number
  total_pages: number | null
  event: ReadingEvent
  base_revision?: number | null
}

export interface ReadingBookMetadata {
  id: number
  title: string
  author: string | null
  collection: string | null
  language: string | null
  edition_label: string | null
  canonical_title: string | null
  canonical_author: string | null
}

export interface ReadingFileMetadata {
  id: number
  original_filename: string
  volume_number: number | null
  editor: string | null
  translator: string | null
}

export interface ReadingProgress {
  id?: number
  book_id: number
  book_file_id: number
  current_page: number
  total_pages: number | null
  progress_percent: number | null
  first_opened_at: string
  last_read_at: string
  completed: boolean
  revision: number
  start_page: number
  end_page: number | null
  viewer_href: string
  book: ReadingBookMetadata
  file: ReadingFileMetadata
}

export interface ReadingHistoryResponse {
  items: ReadingProgress[]
  total: number
  limit: number
  offset: number
}

export interface LocalReadingProgress {
  version: 2
  user_id: number
  book_id: number
  book_file_id: number
  current_page: number
  total_pages: number | null
  event: ReadingEvent
  saved_at: string
  pending_sync: boolean
  revision: number | null
  mutation_id: string
  start_page?: number
  end_page?: number | null
  progress_percent?: number | null
  completed?: boolean
  viewer_href?: string
  book_title?: string
  book_author?: string | null
  original_filename?: string
}

export type ReadingProgressSnapshot = ReadingProgress | LocalReadingProgress

export interface PendingReadingFlushResult {
  attempted: number
  synced: number
  remaining: number
}

const readingSyncQueues = new Map<string, Promise<ReadingProgressSnapshot | null>>()
const readingClearEpochs = new Map<number, number>()

function positiveInteger(value: unknown): number | null {
  const parsed = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(parsed) || parsed < 1) return null
  return Math.floor(parsed)
}

function normalizePayload(payload: ReadingProgressPayload): ReadingProgressPayload {
  const totalPages = positiveInteger(payload.total_pages)
  const requestedPage = positiveInteger(payload.current_page) ?? 1
  return {
    current_page: totalPages ? Math.min(requestedPage, totalPages) : requestedPage,
    total_pages: totalPages,
    event: payload.event,
    ...(payload.base_revision !== undefined
      ? { base_revision: positiveInteger(payload.base_revision) }
      : {}),
  }
}

function mutationId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function syncQueueKey(userId: number, bookId: number, bookFileId: number): string {
  return `${userId}:${bookId}:${bookFileId}`
}

function clearEpoch(userId: number): number {
  return readingClearEpochs.get(userId) ?? 0
}

function validRevision(value: unknown): number | null {
  const parsed = positiveInteger(value)
  return parsed === null ? null : parsed
}

function endpointFor(bookFileId: number, bookId: number): string {
  const params = new URLSearchParams({ book_id: String(bookId) })
  return `${BASE}/reading/progress/${bookFileId}?${params.toString()}`
}

async function apiError(response: Response, fallback: string): Promise<Error> {
  const body = await response.json().catch(() => null) as { detail?: string } | null
  return new Error(body?.detail || fallback)
}

export function localReadingProgressKey(
  userId: number,
  bookId: number,
  bookFileId: number,
): string {
  return `${LOCAL_PROGRESS_PREFIX}:u${userId}:b${bookId}:f${bookFileId}`
}

export function readLocalReadingProgress(
  userId: number,
  bookId: number,
  bookFileId: number,
): LocalReadingProgress | null {
  if (typeof window === 'undefined') return null

  try {
    const raw = window.localStorage.getItem(localReadingProgressKey(userId, bookId, bookFileId))
    if (!raw) return null
    const parsed = JSON.parse(raw) as Partial<LocalReadingProgress>
    const currentPage = positiveInteger(parsed.current_page)
    const totalPages = positiveInteger(parsed.total_pages)
    if (
      parsed.version !== 2
      || parsed.user_id !== userId
      || parsed.book_id !== bookId
      || parsed.book_file_id !== bookFileId
      || currentPage === null
      || (totalPages !== null && currentPage > totalPages)
      || !['open', 'progress', 'restart'].includes(parsed.event ?? '')
    ) {
      return null
    }

    return {
      version: 2,
      user_id: userId,
      book_id: bookId,
      book_file_id: bookFileId,
      current_page: currentPage,
      total_pages: totalPages,
      event: parsed.event as ReadingEvent,
      saved_at: typeof parsed.saved_at === 'string' ? parsed.saved_at : new Date(0).toISOString(),
      pending_sync: parsed.pending_sync === true,
      revision: validRevision(parsed.revision),
      mutation_id: typeof parsed.mutation_id === 'string'
        ? parsed.mutation_id
        : mutationId(),
      start_page: positiveInteger(parsed.start_page) ?? undefined,
      end_page: parsed.end_page === null
        ? null
        : positiveInteger(parsed.end_page) ?? undefined,
      progress_percent: typeof parsed.progress_percent === 'number'
        && Number.isFinite(parsed.progress_percent)
        ? Math.max(0, Math.min(100, parsed.progress_percent))
        : null,
      completed: parsed.completed === true,
      viewer_href: typeof parsed.viewer_href === 'string' ? parsed.viewer_href : undefined,
      book_title: typeof parsed.book_title === 'string' ? parsed.book_title : undefined,
      book_author: typeof parsed.book_author === 'string' || parsed.book_author === null
        ? parsed.book_author
        : undefined,
      original_filename: typeof parsed.original_filename === 'string'
        ? parsed.original_filename
        : undefined,
    }
  } catch {
    return null
  }
}

export function writeLocalReadingProgress(
  userId: number,
  bookId: number,
  bookFileId: number,
  payload: ReadingProgressPayload,
  options: {
    pendingSync?: boolean
    remote?: ReadingProgress | null
    revision?: number | null
    savedAt?: string
    mutationId?: string
  } = {},
): LocalReadingProgress {
  const normalized = normalizePayload(payload)
  const previous = readLocalReadingProgress(userId, bookId, bookFileId)
  const remote = options.remote
  const currentPage = remote ? remote.current_page : normalized.current_page
  const totalPages = remote ? remote.total_pages : normalized.total_pages
  const startPage = remote?.start_page ?? previous?.start_page
  const endPage = remote ? remote.end_page : previous?.end_page
  const progressPercent = remote ? remote.progress_percent : null
  const local: LocalReadingProgress = {
    version: 2,
    user_id: userId,
    book_id: bookId,
    book_file_id: bookFileId,
    current_page: currentPage,
    total_pages: totalPages,
    event: normalized.event,
    saved_at: options.savedAt || remote?.last_read_at || new Date().toISOString(),
    pending_sync: options.pendingSync ?? true,
    revision: remote?.revision ?? options.revision ?? previous?.revision ?? null,
    mutation_id: options.mutationId ?? mutationId(),
    start_page: startPage,
    end_page: endPage,
    progress_percent: progressPercent,
    completed: remote?.completed ?? Boolean(endPage && currentPage >= endPage),
    viewer_href: buildTrackedViewerHref(bookFileId, bookId, currentPage),
    book_title: remote?.book.canonical_title || remote?.book.title || previous?.book_title,
    book_author: remote?.book.canonical_author || remote?.book.author || previous?.book_author,
    original_filename: remote?.file.original_filename || previous?.original_filename,
  }
  storeLocalReadingProgress(local)
  return local
}

function storeLocalReadingProgress(local: LocalReadingProgress): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(
      localReadingProgressKey(local.user_id, local.book_id, local.book_file_id),
      JSON.stringify(local),
    )
  } catch {
    // Storage can be unavailable in private mode. Reading must still continue.
  }
}

export function listLocalReadingProgress(userId: number): LocalReadingProgress[] {
  if (typeof window === 'undefined') return []
  const prefix = `${LOCAL_PROGRESS_PREFIX}:u${userId}:`
  const items: LocalReadingProgress[] = []

  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (!key?.startsWith(prefix)) continue
      const match = key.match(/:b(\d+):f(\d+)$/)
      if (!match) continue
      const item = readLocalReadingProgress(userId, Number(match[1]), Number(match[2]))
      if (item) items.push(item)
    }
  } catch {
    return []
  }

  return items.sort((left, right) => Date.parse(right.saved_at) - Date.parse(left.saved_at))
}

export function extractBookFileId(fileUrl: string): number | null {
  if (!fileUrl) return null
  try {
    const url = new URL(fileUrl, 'https://verafidei.local')
    const match = url.pathname.match(/\/api\/pdfs\/(\d+)\/?$/)
    return match ? positiveInteger(match[1]) : null
  } catch {
    return null
  }
}

export function buildTrackedViewerHref(
  bookFileId: number,
  bookId: number,
  page: number,
): string {
  const params = new URLSearchParams({
    file: `/api/pdfs/${bookFileId}`,
    book: String(bookId),
    page: String(positiveInteger(page) ?? 1),
    reading: '1',
  })
  return `/viewer/pdf?${params.toString()}`
}

export async function getReadingProgress(
  bookFileId: number,
  bookId: number,
): Promise<ReadingProgress | null> {
  const response = await fetchWithTimeout(endpointFor(bookFileId, bookId), {
    credentials: 'include',
    cache: 'no-store',
    headers: authBearerHeaders({ Accept: 'application/json' }),
  }, {
    timeoutMs: DEFAULT_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'O progresso de leitura demorou demais para carregar.',
  })
  if (response.status === 404) return null
  if (!response.ok) throw await apiError(response, 'Não foi possível carregar o progresso de leitura.')
  return response.json() as Promise<ReadingProgress>
}

export async function saveReadingProgress(
  bookFileId: number,
  bookId: number,
  payload: ReadingProgressPayload,
  options: { keepalive?: boolean } = {},
): Promise<ReadingProgress> {
  const normalized = normalizePayload(payload)
  const response = await fetchWithTimeout(endpointFor(bookFileId, bookId), {
    method: 'PUT',
    credentials: 'include',
    keepalive: options.keepalive,
    headers: authBearerHeaders({
      Accept: 'application/json',
      'Content-Type': 'application/json',
    }),
    body: JSON.stringify({ book_id: bookId, ...normalized }),
  }, {
    timeoutMs: DEFAULT_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'O progresso será sincronizado quando a conexão voltar.',
  })
  if (!response.ok) throw await apiError(response, 'Não foi possível sincronizar o progresso de leitura.')
  return response.json() as Promise<ReadingProgress>
}

export async function listReadingHistory(
  limit = 20,
  offset = 0,
): Promise<ReadingHistoryResponse> {
  const params = new URLSearchParams({
    limit: String(Math.max(1, Math.floor(limit))),
    offset: String(Math.max(0, Math.floor(offset))),
  })
  const response = await fetchWithTimeout(`${BASE}/reading/history?${params.toString()}`, {
    credentials: 'include',
    cache: 'no-store',
    headers: authBearerHeaders({ Accept: 'application/json' }),
  }, {
    timeoutMs: DEFAULT_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'O histórico de leitura demorou demais para carregar.',
  })
  if (!response.ok) throw await apiError(response, 'Não foi possível carregar o histórico de leitura.')
  return response.json() as Promise<ReadingHistoryResponse>
}

function cacheRemoteProgress(
  userId: number,
  remote: ReadingProgress,
  event: ReadingEvent = 'progress',
): LocalReadingProgress {
  return writeLocalReadingProgress(userId, remote.book_id, remote.book_file_id, {
    current_page: remote.current_page,
    total_pages: remote.total_pages,
    event,
    base_revision: remote.revision,
  }, { pendingSync: false, remote })
}

function preserveNewerPending(
  latest: LocalReadingProgress,
  remote: ReadingProgress,
): LocalReadingProgress {
  const next: LocalReadingProgress = {
    ...latest,
    revision: remote.revision,
    start_page: remote.start_page,
    end_page: remote.end_page,
    progress_percent: null,
    completed: Boolean(remote.end_page && latest.current_page >= remote.end_page),
    viewer_href: buildTrackedViewerHref(
      latest.book_file_id,
      latest.book_id,
      latest.current_page,
    ),
    book_title: remote.book.canonical_title || remote.book.title,
    book_author: remote.book.canonical_author || remote.book.author,
    original_filename: remote.file.original_filename,
  }
  storeLocalReadingProgress(next)
  return next
}

function commitRemoteUnlessSuperseded(
  userId: number,
  bookId: number,
  bookFileId: number,
  expectedMutationId: string,
  remote: ReadingProgress,
  event: ReadingEvent,
): ReadingProgressSnapshot {
  const latest = readLocalReadingProgress(userId, bookId, bookFileId)
  if (latest?.pending_sync && latest.mutation_id !== expectedMutationId) {
    return preserveNewerPending(latest, remote)
  }
  cacheRemoteProgress(userId, remote, event)
  return remote
}

async function syncPendingLocalProgress(
  userId: number,
  bookId: number,
  bookFileId: number,
  mode: 'active' | 'reconcile',
  expectedClearEpoch: number,
  options: { keepalive?: boolean } = {},
): Promise<ReadingProgressSnapshot | null> {
  if (clearEpoch(userId) !== expectedClearEpoch) return null
  let local = readLocalReadingProgress(userId, bookId, bookFileId)
  if (!local?.pending_sync) return local

  let remote: ReadingProgress | null = null
  if (mode === 'reconcile' || local.revision === null) {
    const mutationBeforeLookup = local.mutation_id
    try {
      remote = await getReadingProgress(bookFileId, bookId)
    } catch {
      // Without the current authoritative revision, an offline pending update
      // must remain pending instead of risking a newer position from another device.
      return readLocalReadingProgress(userId, bookId, bookFileId)
    }

    if (clearEpoch(userId) !== expectedClearEpoch) return null

    const latest = readLocalReadingProgress(userId, bookId, bookFileId)
    if (!latest?.pending_sync) return latest
    local = latest
    const changedDuringLookup = latest.mutation_id !== mutationBeforeLookup

    if (
      mode === 'reconcile'
      && remote
      && (local.revision === null || remote.revision > local.revision)
    ) {
      if (!changedDuringLookup) {
        cacheRemoteProgress(userId, remote)
        return remote
      }
      local = preserveNewerPending(local, remote)
    }

    if (
      mode === 'active'
      && remote
      && local.event === 'open'
      && remote.current_page >= local.current_page
    ) {
      cacheRemoteProgress(userId, remote, 'open')
      return remote
    }

    if (remote && remote.revision !== local.revision) {
      local = preserveNewerPending(local, remote)
    }
  }

  const baseRevision = local.revision
  const expectedRevision = baseRevision === null ? 1 : baseRevision + 1
  const expectedMutationId = local.mutation_id

  try {
    const saved = await saveReadingProgress(bookFileId, bookId, {
      current_page: local.current_page,
      total_pages: local.total_pages,
      event: local.event,
      base_revision: baseRevision,
    }, options)

    if (clearEpoch(userId) !== expectedClearEpoch) return null

    // A stale base revision is deliberately returned as HTTP 200 with the
    // authoritative row. Do not retry over a newer device revision.
    return commitRemoteUnlessSuperseded(
      userId,
      bookId,
      bookFileId,
      expectedMutationId,
      saved,
      saved.revision === expectedRevision ? local.event : 'progress',
    )
  } catch {
    return readLocalReadingProgress(userId, bookId, bookFileId) ?? local
  }
}

function enqueueReadingSync(
  userId: number,
  bookId: number,
  bookFileId: number,
  mode: 'active' | 'reconcile',
  options: { keepalive?: boolean } = {},
): Promise<ReadingProgressSnapshot | null> {
  const key = syncQueueKey(userId, bookId, bookFileId)
  const expectedClearEpoch = clearEpoch(userId)
  const previous = readingSyncQueues.get(key) ?? Promise.resolve(null)
  const task = previous
    .catch(() => null)
    .then(() => syncPendingLocalProgress(
      userId,
      bookId,
      bookFileId,
      mode,
      expectedClearEpoch,
      options,
    ))
  const tracked = task.finally(() => {
    if (readingSyncQueues.get(key) === tracked) readingSyncQueues.delete(key)
  })
  readingSyncQueues.set(key, tracked)
  return tracked
}

export async function syncReadingProgressWithFallback(
  userId: number,
  bookId: number,
  bookFileId: number,
  payload: ReadingProgressPayload,
  options: { keepalive?: boolean } = {},
): Promise<ReadingProgressSnapshot> {
  const previous = readLocalReadingProgress(userId, bookId, bookFileId)
  if (payload.event === 'open' && previous?.pending_sync) {
    // Reopening a book must not turn a real offline page update into a weaker
    // "open" event. Reconcile the pending bookmark first; if the network is
    // still unavailable, keep the exact local position untouched.
    return await enqueueReadingSync(
      userId,
      bookId,
      bookFileId,
      'reconcile',
      options,
    ) ?? previous
  }

  const local = writeLocalReadingProgress(userId, bookId, bookFileId, payload, {
    pendingSync: true,
    revision: payload.base_revision,
  })
  return await enqueueReadingSync(userId, bookId, bookFileId, 'active', options) ?? local
}

export async function loadReadingProgressWithFallback(
  userId: number,
  bookId: number,
  bookFileId: number,
): Promise<ReadingProgressSnapshot | null> {
  const local = readLocalReadingProgress(userId, bookId, bookFileId)

  if (local?.pending_sync) {
    return await enqueueReadingSync(userId, bookId, bookFileId, 'reconcile') ?? local
  }

  try {
    const expectedClearEpoch = clearEpoch(userId)
    const remote = await getReadingProgress(bookFileId, bookId)
    if (clearEpoch(userId) !== expectedClearEpoch) return null
    if (!remote) return local
    const latest = readLocalReadingProgress(userId, bookId, bookFileId)
    if (latest?.pending_sync) {
      return await enqueueReadingSync(userId, bookId, bookFileId, 'reconcile') ?? latest
    }
    cacheRemoteProgress(userId, remote)
    return remote
  } catch {
    return local
  }
}

export async function restartReadingProgress(
  userId: number,
  bookFileId: number,
  bookId: number,
  startPage = 1,
  totalPages: number | null = null,
): Promise<ReadingProgressSnapshot> {
  return syncReadingProgressWithFallback(userId, bookId, bookFileId, {
    current_page: startPage,
    total_pages: totalPages,
    event: 'restart',
  })
}

export function clearLocalReadingProgress(userId: number): number {
  if (typeof window === 'undefined') return 0
  readingClearEpochs.set(userId, clearEpoch(userId) + 1)
  const prefix = `${LOCAL_PROGRESS_PREFIX}:u${userId}:`
  const keys: string[] = []
  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index)
      if (key?.startsWith(prefix)) keys.push(key)
    }
    for (const key of keys) window.localStorage.removeItem(key)
    return keys.length
  } catch {
    return 0
  }
}

export async function flushPendingReadingProgress(
  userId: number,
): Promise<PendingReadingFlushResult> {
  const pending = listLocalReadingProgress(userId).filter((item) => item.pending_sync)
  await Promise.all(pending.map((item) => enqueueReadingSync(
    userId,
    item.book_id,
    item.book_file_id,
    'reconcile',
  )))
  const remaining = listLocalReadingProgress(userId).filter((item) => item.pending_sync).length
  return {
    attempted: pending.length,
    synced: pending.filter((item) => (
      readLocalReadingProgress(userId, item.book_id, item.book_file_id)?.pending_sync !== true
    )).length,
    remaining,
  }
}
