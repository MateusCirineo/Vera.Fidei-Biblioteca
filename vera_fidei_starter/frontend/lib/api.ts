import { authBearerHeaders } from './auth'
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
  DailyCitationResponse,
} from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'https://verafidei.oialfred.com/api'
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

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

export async function verifyCitation(
  quote: string,
  attributed_to: string,
  language?: string
): Promise<VerifyCitationResponse> {
  const res = await fetch(`${BASE}/citations/verify-citation`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ quote, attributed_to, language: language || null }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao verificar citação')
  return res.json()
}

export async function getVerificationUsage(): Promise<VerificationUsage> {
  const res = await fetch(`${BASE}/citations/usage`, {
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar uso das verificações')
  return res.json()
}

export async function listBooks(): Promise<Book[]> {
  const res = await fetch(`${BASE}/books`, { next: { revalidate: 300 }, headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao carregar obras')
  return res.json()
}

export async function listAuthorsCatalog(): Promise<AuthorCatalogEntry[]> {
  const res = await fetch(`${BASE}/authors/catalog`, { next: { revalidate: 300 }, headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao carregar catálogo de autores')
  return res.json()
}

export async function getBook(id: number): Promise<Book> {
  const res = await fetch(`${BASE}/books/${id}`, { cache: 'no-store', headers: authHeaders() })
  if (!res.ok) throw new Error('Obra não encontrada')
  return res.json()
}

export async function listFavorites(kind?: FavoriteKind): Promise<FavoriteListResponse> {
  const query = kind ? `?kind=${encodeURIComponent(kind)}` : ''
  const res = await fetch(`${BASE}/favorites${query}`, {
    cache: 'no-store',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar favoritos')
  return res.json()
}

export async function saveFavorite(payload: FavoritePayload): Promise<FavoriteItem> {
  const res = await fetch(`${BASE}/favorites`, {
    method: 'POST',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao favoritar')
  return res.json()
}

export async function deleteFavorite(kind: FavoriteKind, itemId: string): Promise<void> {
  const res = await fetch(`${BASE}/favorites/${kind}/${encodeURIComponent(itemId)}`, {
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
  const res = await fetch(`${BASE}/books/ingest-auto`, { method: 'POST', body: form, headers: authHeaders() })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro ao ingerir PDF')
  }
  return res.json()
}

export async function getBookStatus(
  bookId: number,
): Promise<{ book_id: number; status: string; chunks_indexed: number; ingest_error?: string | null }> {
  const res = await fetch(`${BASE}/books/${bookId}/status`, { cache: 'no-store', headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao consultar status')
  return res.json()
}

export async function deleteBook(id: number): Promise<void> {
  const res = await fetch(`${BASE}/books/${id}`, { method: 'DELETE', headers: authHeaders() })
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
  const res = await fetch(`${BASE}/books/${bookId}/files/${fileId}/metadata`, {
    method: 'PATCH',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ editor, translator }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro ao atualizar metadados')
  }
}

export function getPdfUrl(file_id: number, pdf_page?: number | null): string {
  const anchor = pdf_page ? `#page=${pdf_page}` : ''
  return `/pdfs/${file_id}${anchor}`
}

export function getPdfDownloadUrl(file_id: number): string {
  const params = new URLSearchParams({ download: '1' })
  return `/pdfs/${file_id}?${params.toString()}`
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
  const res = await fetch(`${BASE}/billing/admin/coupons?${params.toString()}`, {
    cache: 'no-store',
    headers: authBearerHeaders({ 'Content-Type': 'application/json' }),
  })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar cupons')
  return res.json()
}

// ─── Busca no acervo ──────────────────────────────────────────────────────────

export async function searchAcervo(
  q: string,
  options: { limit?: number; author?: string } = {},
): Promise<AcervoSearchResponse> {
  const params = new URLSearchParams({ q, limit: String(options.limit ?? 20) })
  if (options.author) params.set('author', options.author)
  const res = await fetch(`${BASE}/search/chunks?${params}`, { headers: authHeaders() })
  if (!res.ok) throw await readApiError(res, 'Erro na busca do acervo')
  return res.json()
}

export async function searchBible(ref: string, limit = 20): Promise<AcervoSearchResponse> {
  const params = new URLSearchParams({ ref, limit: String(limit) })
  const res = await fetch(`${BASE}/search/bible?${params}`, { headers: authHeaders() })
  if (!res.ok) throw await readApiError(res, 'Erro na busca bíblica')
  return res.json()
}

export async function getDailyCitation(author: string): Promise<DailyCitationResponse> {
  const params = new URLSearchParams({ author })
  const res = await fetch(`${BASE}/search/daily-citation?${params}`, { headers: authHeaders() })
  if (!res.ok) throw await readApiError(res, 'Erro ao carregar citação do dia')
  return res.json()
}

export function getAcademicRefUrl(historyId: number, format: 'bibtex' | 'abnt' | 'ris'): string {
  return `${BASE}/citations/historico/${historyId}/export-ref?format=${format}`
}

export async function getCccCommentary(article: number, limit = 12): Promise<CccCommentaryResponse> {
  const params = new URLSearchParams({ article: String(article), limit: String(limit) })
  const res = await fetch(`${BASE}/search/ccc-commentary?${params}`, { headers: authHeaders() })
  if (!res.ok) throw await readApiError(res, 'Erro ao buscar comentário patrístico')
  return res.json()
}
