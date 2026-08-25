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

export interface VerificationUsage {
  plan: string
  limit: number | null
  used: number
  remaining: number | null
  period_start: string
  resets_at: string
  reset_seconds: number
  percent_used: number
  threshold: 'half' | 'almost' | 'full' | null
  message: string | null
  blocked: boolean
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
  variant_analysis: string | null
  history_id?: number | null
  quota?: VerificationUsage | null
}

export interface BookFile {
  id: number
  original_filename: string
  volume_number: number | null
  editor: string | null
  translator: string | null
  created_at: string
  start_page?: number
  is_source_alias?: boolean
}

export type PatristicTradition = 'grega' | 'oriental' | 'latina' | 'portuguesa'
export type PatristicShelf = PatristicTradition | 'inglesa'
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
  volume_number: number | null
  ingest_status?: string | null
  ingest_error?: string | null
}

export type FavoriteKind = 'book' | 'prayer'

export interface FavoriteItem {
  id: number
  kind: FavoriteKind
  item_id: string
  title: string
  subtitle: string | null
  href: string
  source: string | null
  metadata: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface FavoriteListResponse {
  items: FavoriteItem[]
  total: number
}

export interface FavoritePayload {
  kind: FavoriteKind
  item_id: string
  title: string
  subtitle?: string | null
  href: string
  source?: string | null
  metadata?: Record<string, unknown> | null
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
  patristica: Record<PatristicShelf, Book[]>
  obras_por_autor: AuthorEntry[]
  obras_santos: AuthorEntry[]
  documentos: DocumentosLibrary
}

// ─── Busca no acervo ──────────────────────────────────────────────────────────

export interface AcervoSearchResult {
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
  library_section: string | null
  patristic_tradition: string | null
  source_fidelity: 'verified_transcription' | 'source_text' | 'unverified_ocr'
  source_fidelity_label: string
  source_warning: string | null
  matched_query: string | null
  match_type?: 'literal' | 'semantic'
  content_role: string | null
}

export interface AcervoSearchResponse {
  results: AcervoSearchResult[]
  total: number
  query: string
  patristic_results?: AcervoSearchResult[]
  returned?: number
  readable_total?: number
  matching_works?: number
  has_more?: boolean
  next_cursor?: string | null
  total_matching_pages?: number
  total_matching_works?: number
  expanded_terms?: string[]
}

// ─── Comentário patrístico por artigo do CCC ─────────────────────────────────

export interface CccCommentaryResponse {
  article: number
  section_title: string
  themes: string[]
  results: AcervoSearchResult[]
  total: number
  article_text: string | null
  source_pages: number[]
  mode: 'exact_article' | 'source_unavailable'
  warning: string | null
}

// ─── Concordância dos Catecismos ─────────────────────────────────────────────

export type CatechismId = 'ccc' | 'compendium' | 'pio_x' | 'youcat' | 'roman'

export interface CatechismSourceRef {
  book_id: number
  book_file_id: number | null
  chunk_ids: number[]
  pages: number[]
  edition_label: string | null
  language: string | null
}

export interface CatechismPassage {
  catechism: CatechismId
  source_title: string
  source_author: string | null
  locator: string
  section_title: string | null
  text: string
  source: CatechismSourceRef
  verification: 'indexed_edition'
  text_fingerprint: string
}

export interface CatechismComparisonMatch {
  kind: 'explicit_cross_reference' | 'thematic'
  confidence: 'high'
  evidence_terms: string[]
}

export interface CatechismComparison {
  status: 'matched' | 'no_reliable_match' | 'source_unavailable'
  source: Exclude<CatechismId, 'ccc'>
  source_title: string
  message: string | null
  passage: CatechismPassage | null
  match: CatechismComparisonMatch | null
}

export interface CatechismConcordanceNotice {
  scope: 'anchor' | 'comparisons' | 'patristic'
  code: string
  message: string
}

export interface CatechismConcordanceResponse {
  query: {
    kind: 'ccc_paragraph'
    article: number
  }
  anchor: CatechismPassage
  themes: string[]
  comparisons: CatechismComparison[]
  patristic_roots: {
    results: AcervoSearchResult[]
    total: number
  }
  notices: CatechismConcordanceNotice[]
}

// ─── Uso diário de busca ──────────────────────────────────────────────────────

export interface SearchUsageInfo {
  plan: string
  limit: number | null
  used: number
  remaining: number | null
}

// ─── Citação do dia ───────────────────────────────────────────────────────────

export interface DailyCitationResponse {
  chunk_id: number | null
  text: string | null
  author: string | null
  work_title: string | null
  pdf_page: number | null
  chapter_or_section: string | null
  edition_label: string | null
  language: string | null
  translation_text: string | null
  book_id: number | null
  book_file_id: number | null
  day_of_year: number
  source_fidelity: 'verified_transcription' | 'source_text' | null
  source_fidelity_label: string | null
}
