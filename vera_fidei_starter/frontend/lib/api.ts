import type { Book, AuthorCatalogEntry, VerifyCitationResponse } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return API_KEY ? { 'X-API-Key': API_KEY, ...extra } : extra
}

export async function verifyCitation(
  quote: string,
  attributed_to: string,
  language?: string
): Promise<VerifyCitationResponse> {
  const res = await fetch(`${BASE}/citations/verify-citation`, {
    method: 'POST',
    headers: authHeaders({ 'Content-Type': 'application/json' }),
    body: JSON.stringify({ quote, attributed_to, language: language || null }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro ao verificar citação')
  }
  return res.json()
}

export async function listBooks(): Promise<Book[]> {
  const res = await fetch(`${BASE}/books`, { cache: 'no-store', headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao carregar obras')
  return res.json()
}

export async function listAuthorsCatalog(): Promise<AuthorCatalogEntry[]> {
  const res = await fetch(`${BASE}/authors/catalog`, { next: { revalidate: 30 }, headers: authHeaders() })
  if (!res.ok) throw new Error('Erro ao carregar catálogo de autores')
  return res.json()
}

export async function getBook(id: number): Promise<Book> {
  const res = await fetch(`${BASE}/books/${id}`, { cache: 'no-store', headers: authHeaders() })
  if (!res.ok) throw new Error('Obra não encontrada')
  return res.json()
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
  const keyParam = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : ''
  const anchor = pdf_page ? `#page=${pdf_page}` : ''
  return `${BASE}/pdfs/${file_id}${keyParam}${anchor}`
}
