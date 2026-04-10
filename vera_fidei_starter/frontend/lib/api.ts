import type { Book, VerifyCitationResponse } from './types'

const BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'

export async function verifyCitation(
  quote: string,
  attributed_to: string,
  language?: string
): Promise<VerifyCitationResponse> {
  const res = await fetch(`${BASE}/citations/verify-citation`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ quote, attributed_to, language: language || null }),
  })
  if (!res.ok) {
    const err = await res.text()
    throw new Error(err || 'Erro ao verificar citação')
  }
  return res.json()
}

export async function listBooks(): Promise<Book[]> {
  const res = await fetch(`${BASE}/books`, { cache: 'no-store' })
  if (!res.ok) throw new Error('Erro ao carregar obras')
  return res.json()
}

export async function getBook(id: number): Promise<Book> {
  const res = await fetch(`${BASE}/books/${id}`, { cache: 'no-store' })
  if (!res.ok) throw new Error('Obra não encontrada')
  return res.json()
}

export function getPdfUrl(file_id: number, pdf_page?: number | null): string {
  const anchor = pdf_page ? `#page=${pdf_page}` : ''
  return `${BASE}/pdfs/${file_id}${anchor}`
}
