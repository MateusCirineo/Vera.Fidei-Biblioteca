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
  | 'CONFIRMADA_TRADUCAO'
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
}

export interface BookFile {
  id: number
  original_filename: string
  volume_number: number | null
  editor: string | null
  translator: string | null
  created_at: string
}

export interface Book {
  id: number
  collection: string
  title: string
  author: string | null
  language: string | null
  edition_label: string | null
  source_label: string | null
  is_primary_source: boolean
  chunk_count?: number
  files?: BookFile[]
}
