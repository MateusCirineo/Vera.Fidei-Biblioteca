import { API_BASE } from './runtime-config'
import {
  parsePlayBillingCatalog,
  parsePlayBillingStatus,
  parsePlaySyncResponse,
  type PlayBillingCatalog,
  type PlayBillingStatus,
  type PlayPurchaseInput,
  type PlaySyncResponse,
} from './play-billing'

let authToken = ''
let unauthorizedHandler: (() => void) | null = null

export function setAuthToken(token: string | null): void {
  authToken = token?.trim() ?? ''
}

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler
}

export class ApiError extends Error {
  readonly status: number
  readonly code?: string
  readonly payload?: unknown

  constructor(message: string, status = 0, code?: string, payload?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.payload = payload
  }
}

type RequestOptions = {
  signal?: AbortSignal
  timeoutMs?: number
  authenticated?: boolean
}

function apiMessage(payload: unknown, fallback: string): { message: string; code?: string } {
  if (!payload || typeof payload !== 'object') return { message: fallback }
  const root = payload as Record<string, unknown>
  const detail = root.detail
  if (typeof detail === 'string') return { message: detail }
  if (detail && typeof detail === 'object') {
    const value = detail as Record<string, unknown>
    return {
      message: typeof value.message === 'string' ? value.message : fallback,
      code: typeof value.code === 'string' ? value.code : undefined,
    }
  }
  return {
    message: typeof root.message === 'string' ? root.message : fallback,
    code: typeof root.code === 'string' ? root.code : undefined,
  }
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {},
): Promise<T> {
  const controller = new AbortController()
  const timeoutMs = options.timeoutMs ?? 20_000
  let timedOut = false
  const onExternalAbort = () => controller.abort()
  if (options.signal?.aborted) controller.abort()
  else options.signal?.addEventListener('abort', onExternalAbort, { once: true })
  const timer = setTimeout(() => {
    timedOut = true
    controller.abort()
  }, timeoutMs)

  const headers = new Headers(init.headers)
  headers.set('Accept', 'application/json')
  if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  if (options.authenticated !== false && authToken) {
    headers.set('Authorization', `Bearer ${authToken}`)
  }

  try {
    const response = await fetch(`${API_BASE}${path}`, {
      ...init,
      headers,
      signal: controller.signal,
    })
    if (response.status === 204) return undefined as T

    const raw = await response.text()
    let payload: unknown = null
    if (raw) {
      try {
        payload = JSON.parse(raw)
      } catch {
        payload = raw
      }
    }

    if (!response.ok) {
      if (response.status === 401 && options.authenticated !== false && authToken) {
        unauthorizedHandler?.()
      }
      const fallback = response.status === 401
        ? 'Sua sessão expirou ou este recurso ainda não foi liberado para o aplicativo.'
        : `Não foi possível concluir a solicitação (${response.status}).`
      const parsed = apiMessage(payload, fallback)
      throw new ApiError(parsed.message, response.status, parsed.code, payload)
    }
    return payload as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (timedOut) throw new ApiError('A conexão demorou demais. Verifique sua internet e tente novamente.', 408, 'TIMEOUT')
    if (options.signal?.aborted) throw new ApiError('Solicitação cancelada.', 499, 'ABORTED')
    throw new ApiError('Não foi possível conectar ao Vera Fidei. Verifique sua internet.', 0, 'NETWORK_ERROR')
  } finally {
    clearTimeout(timer)
    options.signal?.removeEventListener('abort', onExternalAbort)
  }
}

export interface SessionUser {
  id: number
  name: string
  email: string
  plan: string
  is_active: boolean
  email_verified: boolean
  billing_provider: string | null
  billing_status: string | null
  billing_current_period_end: string | null
  billing_cancel_at_period_end: boolean
  is_owner: boolean
}

interface TokenResponse {
  access_token: string
  token_type: string
}

export async function loginUser(email: string, password: string, signal?: AbortSignal): Promise<string> {
  const response = await requestJson<TokenResponse>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ email, password }) },
    { signal, authenticated: false },
  )
  return response.access_token
}

export async function registerUser(
  name: string,
  email: string,
  password: string,
  signal?: AbortSignal,
): Promise<string> {
  const response = await requestJson<TokenResponse>(
    '/auth/register',
    { method: 'POST', body: JSON.stringify({ name, email, password }) },
    { signal, authenticated: false },
  )
  return response.access_token
}

export function getCurrentUser(signal?: AbortSignal): Promise<SessionUser> {
  return requestJson('/auth/me', {}, { signal })
}

export interface BillingSyncResponse {
  synced: boolean
  plan: string
  billing_status: string | null
}

export function syncBillingSubscription(signal?: AbortSignal): Promise<BillingSyncResponse> {
  return requestJson(
    '/billing/sync',
    { method: 'POST' },
    { signal, timeoutMs: 20_000 },
  )
}

export async function getGooglePlayBillingCatalog(signal?: AbortSignal): Promise<PlayBillingCatalog> {
  const response = await requestJson<unknown>('/billing/google-play/catalog', {}, { signal })
  return parsePlayBillingCatalog(response)
}

export async function syncGooglePlaySubscriptions(
  purchases: PlayPurchaseInput[],
  operation: 'sync' | 'restore',
  signal?: AbortSignal,
): Promise<PlaySyncResponse> {
  const response = await requestJson<unknown>(
    `/billing/google-play/subscriptions/${operation}`,
    { method: 'POST', body: JSON.stringify({ purchases }) },
    { signal, timeoutMs: 35_000 },
  )
  return parsePlaySyncResponse(response, operation)
}

export async function getGooglePlayBillingStatus(signal?: AbortSignal): Promise<PlayBillingStatus> {
  const response = await requestJson<unknown>('/billing/status', {}, { signal })
  return parsePlayBillingStatus(response)
}

export async function requestPasswordReset(email: string, signal?: AbortSignal): Promise<string> {
  const response = await requestJson<{ message: string }>(
    '/auth/forgot-password',
    { method: 'POST', body: JSON.stringify({ email }) },
    { signal, authenticated: false },
  )
  return response.message
}

export async function resendEmailVerification(signal?: AbortSignal): Promise<string> {
  const response = await requestJson<{ message: string }>(
    '/auth/resend-verification',
    { method: 'POST' },
    { signal },
  )
  return response.message
}

export function exportPersonalData(signal?: AbortSignal): Promise<unknown> {
  return requestJson('/auth/data-export', {}, { signal, timeoutMs: 35_000 })
}

export async function deletePersonalAccount(
  password: string,
  confirmation: string,
  signal?: AbortSignal,
): Promise<string> {
  const response = await requestJson<{ message: string }>(
    '/auth/account',
    {
      method: 'DELETE',
      body: JSON.stringify({ password, confirmation }),
    },
    { signal, timeoutMs: 35_000 },
  )
  return response.message
}

export async function notifyLogout(): Promise<void> {
  try {
    await requestJson('/auth/logout', { method: 'POST' }, { timeoutMs: 5_000 })
  } catch {
    // O JWT é removido localmente mesmo se o aparelho estiver offline.
  }
}

export interface VerifyReference {
  collection: string | null
  volume: number | null
  column_start: number | null
  column_end: number | null
  chapter_or_section: string | null
  visual_anchor: string | null
  pdf_page: number | null
  edition_label: string | null
  source_label: string | null
  language: string | null
  editor: string | null
  translator: string | null
  is_primary_source: boolean
  pdf_file_id: number | null
}

export type StatusCode =
  | 'CONFIRMADA_EXATA'
  | 'ATRIBUICAO_DUVIDOSA'
  | 'CORRESPONDENCIA_FORTE'
  | 'TRADUCAO_FIEL'
  | 'TRADUCAO_IMPRECISA'
  | 'PARAFRASE_PLAUSIVEL'
  | 'NAO_ENCONTRADA'

export interface VerificationUsage {
  plan: string
  limit: number | null
  used: number
  remaining: number | null
  blocked: boolean
  message: string | null
  percent_used: number
}

export interface VerifyResponse {
  status_code: StatusCode
  label: string
  confidence: 'Alta' | 'Média' | 'Baixa' | 'Nenhuma'
  author: string | null
  work: string | null
  reference: VerifyReference | null
  original_language: string | null
  source_version: string | null
  matched_excerpt: string | null
  context_before: string | null
  context_after: string | null
  explanation: string | null
  matched_translation: string | null
  translation_language: string | null
  translation_fidelity: 'fiel' | 'imprecisa' | 'nao_encontrada' | null
  translator: string | null
  translation_edition: string | null
  quota?: VerificationUsage | null
}

export function verifyCitation(
  payload: { quote: string; attributed_to: string; language?: string | null },
  signal?: AbortSignal,
): Promise<VerifyResponse> {
  return requestJson(
    '/citations/verify-citation',
    { method: 'POST', body: JSON.stringify(payload) },
    { signal, timeoutMs: 45_000 },
  )
}

export interface BookFile {
  id: number
  original_filename: string
  volume_number: number | null
  editor: string | null
  translator: string | null
  created_at: string
  start_page?: number
}

export type PatristicTradition = 'grega' | 'oriental' | 'latina' | 'portuguesa'
export type DocumentType =
  | 'concilio'
  | 'bula'
  | 'enciclica'
  | 'constituicao_apostolica'
  | 'carta_apostolica'
  | 'motu_proprio'
  | 'exortacao_apostolica'
  | 'catecismo'
  | 'catequese'
  | 'liturgia'
  | 'doutrina_social'
  | 'direito_canonico'
  | 'teologia'
  | 'linguas_biblicas'
  | 'literatura_crista'
  | 'outro'

export interface Book {
  id: number
  collection: string | null
  title: string
  author: string | null
  language: string | null
  edition_label: string | null
  source_label: string | null
  is_primary_source: boolean
  chunk_count?: number
  files?: BookFile[]
  library_section: 'patristica' | 'documentos' | null
  patristic_tradition: PatristicTradition | null
  document_type: DocumentType | null
  canonical_author: string | null
  canonical_title: string | null
  pope: string | null
  document_year: number | null
  is_ecumenical: boolean | null
  document_status: string | null
  volume_number?: number | null
  ingest_status?: string | null
}

export function listBooks(signal?: AbortSignal): Promise<Book[]> {
  return requestJson('/books', {}, { signal, timeoutMs: 35_000 })
}

export function getBook(id: number, signal?: AbortSignal): Promise<Book> {
  return requestJson(`/books/${id}`, {}, { signal, timeoutMs: 25_000 })
}

export interface SearchResult {
  chunk_id: number
  text: string
  author: string | null
  chunk_author: string | null
  translator: string | null
  editor: string | null
  work_title: string | null
  pdf_page: number | null
  chapter_or_section: string | null
  collection: string | null
  volume: number | null
  edition_label: string | null
  language: string | null
  translation_text: string | null
  relevance_score: number
  book_id: number | null
  book_file_id: number | null
  source_fidelity: string
  source_fidelity_label: string
  source_warning: string | null
}

export interface SearchResponse {
  results: SearchResult[]
  total: number
  query: string
  returned: number
  readable_total: number
  matching_works: number
  has_more: boolean
  next_cursor: string | null
  total_matching_pages: number
  total_matching_works: number
}

export function searchCorpus(
  query: string,
  cursor = '',
  signal?: AbortSignal,
): Promise<SearchResponse> {
  const params = new URLSearchParams({
    q: query,
    limit: '24',
    collection: 'all',
    quotes_only: 'true',
  })
  if (cursor) params.set('cursor', cursor)
  return requestJson(`/search/chunks?${params.toString()}`, {}, { signal, timeoutMs: 35_000 })
}
