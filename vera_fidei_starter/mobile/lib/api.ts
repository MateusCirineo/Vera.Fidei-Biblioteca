import Constants from 'expo-constants'

const { apiUrl, apiKey } = Constants.expoConfig?.extra ?? {}

const BASE: string = apiUrl ?? 'http://localhost:8000'
const KEY: string = apiKey ?? ''

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const h: Record<string, string> = { ...extra }
  if (KEY) h['X-API-Key'] = KEY
  return h
}

// ── Types ──────────────────────────────────────────────────────────────────────

export interface VerifyReference {
  collection: string | null
  volume: number | null
  column_start: number | null
  column_end: number | null
  chapter_or_section: string | null
  pdf_page: number | null
  visual_anchor: string | null
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
}

export interface BookFile {
  id: number
  original_filename: string
  volume_number: number | null
  editor: string | null
  translator: string | null
  created_at: string
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

export interface AuthorCatalogEntry {
  name: string
  tradition: 'grega' | 'latina' | 'oriental'
  collection: 'PG' | 'PL' | 'PO'
  book_count: number
  chunk_count: number
  books: Book[]
}

// ── API calls ──────────────────────────────────────────────────────────────────

export async function verifyCitation(payload: {
  quote: string
  attributed_to: string
  language?: string | null
}): Promise<VerifyResponse> {
  const res = await fetch(`${BASE}/citations/verify-citation`, {
    method: 'POST',
    headers: headers({ 'Content-Type': 'application/json' }),
    body: JSON.stringify(payload),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `Erro ${res.status}`)
  }
  return res.json()
}

export async function listBooks(): Promise<Book[]> {
  const res = await fetch(`${BASE}/books`, { headers: headers() })
  if (!res.ok) throw new Error('Erro ao carregar obras')
  return res.json()
}

export async function listAuthorsCatalog(): Promise<AuthorCatalogEntry[]> {
  const res = await fetch(`${BASE}/authors/catalog`, { headers: headers() })
  if (!res.ok) throw new Error('Erro ao carregar catálogo de autores')
  return res.json()
}

export async function getBook(id: number): Promise<Book> {
  const res = await fetch(`${BASE}/books/${id}`, { headers: headers() })
  if (!res.ok) throw new Error('Obra não encontrada')
  return res.json()
}
