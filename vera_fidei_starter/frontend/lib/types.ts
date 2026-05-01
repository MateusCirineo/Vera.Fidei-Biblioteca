export interface MatchReference {
  collection: string
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

export interface VerifyCitationResponse {
  status_code: StatusCode
  label: string
  confidence: 'Alta' | 'Média' | 'Baixa' | 'Nenhuma'
  author: string | null
  work: string | null
  reference: MatchReference | null
  original_language: string | null
  source_version: string | null
  matched_excerpt: string | null
  context_before: string | null
  context_after: string | null
  explanation: string
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
export type LibrarySection = 'patristica' | 'documentos'
export type DocumentType =
  | 'concilio'
  | 'bula'
  | 'enciclica'
  | 'constituicao_apostolica'
  | 'carta_apostolica'
  | 'motu_proprio'
  | 'exortacao_apostolica'
  | 'catecismo'
  | 'direito_canonico'
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
  // Organização da biblioteca
  library_section: LibrarySection | null
  patristic_tradition: PatristicTradition | null
  document_type: DocumentType | null
  // Campos canônicos e metadados de documento
  canonical_author: string | null
  canonical_title: string | null
  pope: string | null
  document_year: number | null
  is_ecumenical: boolean | null
  document_status: string | null
}

// ─── Catálogo de autores (API /authors/catalog) ───────────────────────────────

export interface AuthorCatalogEntry {
  name: string
  tradition: 'grega' | 'latina' | 'oriental'
  collection: 'PG' | 'PL' | 'PO'
  book_count: number
  chunk_count: number
  books: Book[]
}

// ─── Estrutura organizada da biblioteca (client-side) ─────────────────────────

export interface AuthorWork {
  title: string
  books: Book[]
}

export interface AuthorEntry {
  author: string
  works: AuthorWork[]
}

export interface PopeDocumentEntry {
  pope: string
  latestYear: number | null
  totalCount: number
  types: Partial<Record<DocumentType, Book[]>>
}

export interface DocumentosLibrary {
  byPope: PopeDocumentEntry[]
  nonPapal: Partial<Record<DocumentType, Book[]>>
}

export interface LibraryStructure {
  patristica: Record<PatristicTradition, Book[]>
  obras_por_autor: AuthorEntry[]
  documentos: DocumentosLibrary
}
