import { authBearerHeaders } from './auth'
import { getApiBase } from './api-base'
import {
  DEFAULT_REQUEST_TIMEOUT_MS,
  LONG_REQUEST_TIMEOUT_MS,
  RequestTimeoutError,
  fetchWithTimeout,
} from './http'
import type {
  Book,
  AuthorCatalogEntry,
  FavoriteItem,
  FavoriteKind,
  FavoriteListResponse,
  FavoritePayload,
  VerificationUsage,
  VerifyCitationResponse,
  AcervoSearchResponse,
  CccCommentaryResponse,
  CatechismConcordanceResponse,
  DailyCitationResponse,
  SearchUsageInfo,
} from './types'

const BASE = getApiBase()
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''
const SEARCH_REQUEST_TIMEOUT_MS = 25_000
const USAGE_REQUEST_TIMEOUT_MS = 10_000
const PDF_UPLOAD_TIMEOUT_MS = 30 * 60_000

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return API_KEY ? { 'X-API-Key': API_KEY, ...extra } : extra
}

export class ApiError extends Error {
  status: number
  quota?: VerificationUsage

  constructor(message: string, status: number, quota?: VerificationUsage) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.quota = quota
  }
}

async function readApiError(res: Response, fallback: string): Promise<ApiError> {
  const raw = await res.text()
  if (!raw) return new ApiError(fallback, res.status)
  try {
    const parsed = JSON.parse(raw)
    const detail = parsed.detail
    if (typeof detail === 'string') {
      return new ApiError(detail, res.status)
    }
    if (detail && typeof detail === 'object') {
      return new ApiError(detail.message ?? fallback, res.status, detail.quota)
    }
    return new ApiError(parsed.message ?? fallback, res.status)
  } catch {
    return new ApiError(raw, res.status)
  }
}

async function fetchApi(
  input: RequestInfo | URL,
  init: RequestInit = {},
  options: { timeoutMs?: number; timeoutMessage?: string } = {},
): Promise<Response> {
  try {
    return await fetchWithTimeout(
      input,
      {
        ...init,
        credentials: init.credentials ?? 'include',
      },
      {
        timeoutMs: options.timeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS,
        timeoutMessage: options.timeoutMessage,
      },
    )
  } catch (error) {
    if (error instanceof RequestTimeoutError) {
      throw new ApiError(error.message, error.status)
    }
    throw error
  }
}

export async function verifyCitation(
  quote: string,
  attributed_to: string,
  language?: string
): Promise<VerifyCitationResponse> {
  const res = await fetchApi(`${BASE}/citations/verify-citation`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ quote, attributed_to, language: language || null }),
  }, {
    timeoutMs: LONG_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A verificação demorou demais. Verifique sua conexão e tente novamente.',
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao verificar citação')
  return res.json()
}

export async function getVerificationUsage(): Promise<VerificationUsage> {
  const res = await fetchApi(`${BASE}/citations/usage`, {
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  }, { timeoutMs: USAGE_REQUEST_TIMEOUT_MS })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar uso das verificações')
  return res.json()
}

export async function listBooks(): Promise<Book[]> {
  const res = await fetchApi(`${BASE}/books`, { next: { revalidate: 300 }, headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao carregar obras')
  return res.json()
}

export async function listAuthorsCatalog(): Promise<AuthorCatalogEntry[]> {
  const res = await fetchApi(`${BASE}/authors/catalog`, { next: { revalidate: 300 }, headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao carregar catálogo de autores')
  return res.json()
}

export async function getBook(id: number): Promise<Book> {
  const res = await fetchApi(`${BASE}/books/${id}`, { cache: 'no-store', headers: authHeaders() })
  if (!res.ok) throw new Error('Obra não encontrada')
  return res.json()
}

export async function listFavorites(kind?: FavoriteKind): Promise<FavoriteListResponse> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : ''
  const res = await fetchApi(`${BASE}/favorites${query}`, {
    cache: 'no-store',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar favoritos')
  return res.json()
}

export async function saveFavorite(payload: FavoritePayload): Promise<FavoriteItem> {
  const res = await fetchApi(`${BASE}/favorites`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao favoritar')
  return res.json()
}

export async function deleteFavorite(kind: FavoriteKind, itemId: string): Promise<void> {
  const res = await fetchApi(`${BASE}/favorites/${kind}/${encodeURIComponent(itemId)}`, {
    method: 'DELETE',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao remover favorito')
}

export interface AutoIngestResult {
  id: number
  file_id: number
  title: string
  author: string
  collection: string | null
  language: string
  canonical_author: string | null
  canonical_title: string | null
  library_section: string | null
  patristic_tradition: string | null
  chunks_indexed: number
  ingest_error?: string | null
}

export async function ingestAuto(
  file: File,
  titleOverride?: string,
  editor?: string,
  translator?: string,
): Promise<AutoIngestResult> {
  const form = new FormData()
  form.append('file', file)
  if (titleOverride?.trim()) form.append('title_override', titleOverride.trim())
  if (editor?.trim()) form.append('editor', editor.trim())
  if (translator?.trim()) form.append('translator', translator.trim())
  const res = await fetchApi(`${BASE}/books/ingest-auto`, {
    method: 'POST',
    body: form,
    headers: authBearerHeaders(),
  }, {
    timeoutMs: PDF_UPLOAD_TIMEOUT_MS,
    timeoutMessage: 'O envio do PDF excedeu 30 minutos. Verifique a conexão antes de tentar novamente.',
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro ao ingerir PDF')
  }
  return res.json()
}

export async function getBookStatus(
  bookId: number,
): Promise<{ book_id: number; status: string; chunks_indexed: number; ingest_error?: string | null }> {
  const res = await fetchApi(`${BASE}/books/${bookId}/status`, { cache: 'no-store', headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao consultar status')
  return res.json()
}

export async function deleteBook(id: number): Promise<void> {
  const res = await fetchApi(`${BASE}/books/${id}`, { method: 'DELETE', headers: authBearerHeaders() })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro ao excluir livro')
  }
}

export async function updateBookFileMeta(
  bookId: number,
  fileId: number,
  editor: string | null,
  translator: string | null,
): Promise<void> {
  const res = await fetchApi(`${BASE}/books/${bookId}/files/${fileId}/metadata`, {
    method: 'PATCH',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ editor, translator }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro ao atualizar metadados')
  }
}

export function getPdfUrl(file_id: number): string {
  return `/api/pdfs/${file_id}`
}

export function getPdfDownloadUrl(file_id: number): string {
  const params = new URLSearchParams({ download: '1' })
  return `/api/pdfs/${file_id}?${params.toString()}`
}

export interface AdminCoupon {
  id: string
  code: string
  active: boolean
  status: 'available' | 'used' | 'inactive'
  status_label: string
  percent_off?: number | null
  amount_off?: number | null
  currency?: string | null
  duration?: string | null
  times_redeemed: number
  max_redemptions?: number | null
  created_at?: string | null
}

export interface AdminCouponsResponse {
  mode: string
  prefix: string
  total: number
  available_count: number
  used_count: number
  inactive_count: number
  available: AdminCoupon[]
  used: AdminCoupon[]
  inactive: AdminCoupon[]
}

export async function getAdminCoupons(prefix = 'COLEGIO'): Promise<AdminCouponsResponse> {
  const params = new URLSearchParams({ prefix, limit: '500' })
  const res = await fetchApi(`${BASE}/billing/admin/coupons?${params.toString()}`, {
    cache: 'no-store',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar cupons')
  return res.json()
}

export interface CreateAdminCouponInput {
  code: string
  percent_off: number
  duration: 'once' | 'forever'
  max_redemptions?: number | null
  name?: string | null
}

export async function createAdminCoupon(payload: CreateAdminCouponInput): Promise<AdminCoupon> {
  const res = await fetchApi(`${BASE}/billing/admin/coupons`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao criar cupom')
  return res.json()
}

export interface AdminMetricPeriod {
  today: number
  last_7_days: number
  last_30_days: number
}

export interface AdminMetricCount {
  key: string
  label: string
  count: number
}

export interface AdminDailyActivity {
  date: string
  visitors: number
  page_views: number
  registrations: number
}

export interface AdminRecentAccount {
  id: number
  name: string
  email: string
  plan: string
  plan_label: string
  billing_status?: string | null
  email_verified: boolean
  is_active: boolean
  created_at: string
}

export interface AdminMetricsResponse {
  generated_at: string
  refresh_after_seconds: number
  tracking_started_at?: string | null
  accounts_total: number
  accounts_active: number
  accounts_disabled: number
  accounts_free: number
  subscribers_active: number
  subscribers_canceling: number
  subscriptions_pending: number
  conversion_rate: number
  registrations: AdminMetricPeriod
  visitors_unique_total: number
  visitors_online_now: number
  visitors: AdminMetricPeriod
  page_views: AdminMetricPeriod
  searches_today: number
  verifications_today: number
  plans: AdminMetricCount[]
  subscription_statuses: AdminMetricCount[]
  top_pages_7_days: AdminMetricCount[]
  daily_activity: AdminDailyActivity[]
  recent_accounts: AdminRecentAccount[]
}

export async function getAdminMetrics(): Promise<AdminMetricsResponse> {
  const res = await fetchApi(`${BASE}/analytics/admin/metrics`, {
    cache: 'no-store',
    credentials: 'include',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar métricas')
  return res.json()
}

// ─── Busca no acervo ──────────────────────────────────────────────────────────

export async function searchAcervo(
  q: string,
  options: {
    limit?: number
    author?: string
    collection?: string
    includePatristic?: boolean
    patristicLimit?: number
    quotesOnly?: boolean
    cursor?: string
    signal?: AbortSignal
  } = {},
): Promise<AcervoSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(options.limit ?? 50) })
  if (options.author) params.set('author', options.author)
  if (options.collection) params.set('collection', options.collection)
  if (options.includePatristic) params.set('include_patristic', 'true')
  if (options.patristicLimit) params.set('patristic_limit', String(options.patristicLimit))
  if (options.quotesOnly) params.set('quotes_only', 'true')
  if (options.cursor) params.set('cursor', options.cursor)
  const res = await fetchApi(`${BASE}/search/chunks?${params}`, {
    headers: authBearerHeaders(),
    signal: options.signal,
  }, {
    timeoutMs: SEARCH_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A busca demorou demais. Tente novamente.',
  })
  if (!res.ok) throw await readApiError(res, 'Erro na busca do acervo')
  return res.json()
}

export async function searchBible(
  ref: string,
  limit = 20,
  signal?: AbortSignal,
): Promise<AcervoSearchResponse> {
  const params = new URLSearchParams({ ref, limit: String(limit) })
  const res = await fetchApi(`${BASE}/search/bible?${params}`, {
    headers: authBearerHeaders(),
    signal,
  }, {
    timeoutMs: SEARCH_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A busca demorou demais. Tente novamente.',
  })
  if (!res.ok) throw await readApiError(res, 'Erro na busca bíblica')
  return res.json()
}

export async function getSearchUsage(): Promise<SearchUsageInfo> {
  const res = await fetchApi(`${BASE}/search/usage`, {
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  }, { timeoutMs: USAGE_REQUEST_TIMEOUT_MS })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar uso de busca')
  return res.json()
}

export async function getDailyCitation(author: string): Promise<DailyCitationResponse> {
  const params = new URLSearchParams({ author })
  const res = await fetchApi(`${BASE}/search/daily-citation?${params}`, {
    headers: authHeaders(),
  }, {
    timeoutMessage: 'A citação do dia demorou demais para carregar. Tente novamente.',
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar citação do dia')
  return res.json()
}

export function getAcademicRefUrl(historyId: number, format: 'bibtex' | 'abnt' | 'ris'): string {
  return `${BASE}/citations/historico/${historyId}/export-ref?format=${format}`
}

export async function getCccCommentary(article: number, limit = 12): Promise<CccCommentaryResponse> {
  const params = new URLSearchParams({ article: String(article), limit: String(limit) })
  const res = await fetchApi(`${BASE}/search/ccc-commentary?${params}`, {
    headers: authBearerHeaders(),
  }, {
    timeoutMs: SEARCH_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A busca demorou demais. Tente novamente.',
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao buscar comentário patrístico')
  return res.json()
}

export async function getCatechismConcordance(
  article: number,
  options: { patristicLimit?: number; signal?: AbortSignal } = {},
): Promise<CatechismConcordanceResponse> {
  const params = new URLSearchParams({
    article: String(article),
    patristic_limit: String(options.patristicLimit ?? 8),
  })
  const res = await fetchApi(`${BASE}/search/catechism-concordance?${params}`, {
    headers: authBearerHeaders(),
    signal: options.signal,
  }, {
    timeoutMs: SEARCH_REQUEST_TIMEOUT_MS,
    timeoutMessage: 'A busca demorou demais. Tente novamente.',
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao consultar a concordância dos catecismos')
  return res.json()
}
