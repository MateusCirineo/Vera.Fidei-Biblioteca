'use client'

import { useState, useCallback, useEffect, useRef } from 'react'
import Link from 'next/link'
import type {
  Book,
  LibraryStructure,
  PatristicShelf,
  DocumentType,
  PopeDocumentEntry,
  DocumentosLibrary,
  AuthorEntry,
  AuthorCatalogEntry,
} from '@/lib/types'

import PatristicaSection from './PatristicaSection'
import AutoresSection from './AutoresSection'
import DocumentosSection from './DocumentosSection'
import SantosObrasSection from './SantosObrasSection'
import BookCard from './BookCard'
import { searchAcervo, searchBible, getCatechismConcordance, getPdfUrl, ApiError, getSearchUsage } from '@/lib/api'
import { getToken } from '@/lib/auth'
import type {
  AcervoSearchResult,
  CatechismConcordanceResponse,
  CatechismPassage,
  SearchUsageInfo,
} from '@/lib/types'

const CONTENT_SEARCH_PAGE_SIZE = 36

function searchResultIdentity(hit: AcervoSearchResult): string {
  const owner = hit.book_file_id != null
    ? `file:${hit.book_file_id}`
    : hit.book_id != null
      ? `book:${hit.book_id}`
      : `chunk:${hit.chunk_id}`
  return hit.pdf_page != null ? `${owner}:page:${hit.pdf_page}` : `chunk:${hit.chunk_id}`
}

function SearchResultCard({ hit, query }: { hit: AcervoSearchResult; query: string }) {
  // Keep source punctuation and wording untouched. Browser layout may wrap
  // whitespace, but this component must never "clean up" a verified edition.
  const translatedPassage = hit.translation_text?.trim() ?? ''
  const originalPassage = hit.text?.trim() ?? ''
  const text = originalPassage || translatedPassage
  const isPdfLocator = hit.source_fidelity === 'unverified_ocr'
  const pdfHref = hit.book_file_id == null
    ? null
    : (() => {
        const params = new URLSearchParams({ file: getPdfUrl(hit.book_file_id!) })
        if (hit.pdf_page != null) params.set('page', String(hit.pdf_page))
        const sourceExcerpt = originalPassage.replace(/\s+/g, ' ').slice(0, 700)
        if (sourceExcerpt) params.set('quote', sourceExcerpt)
        return `/viewer/pdf?${params.toString()}`
      })()

  function highlight(str: string) {
    const q = query.trim()
    if (!q) return str
    try {
      const matched = hit.matched_query?.trim() ?? ''
      const candidates = [matched, q, ...q.split(/\s+/).filter(term => term.length >= 3)].filter(Boolean)
      const unique = Array.from(new Set(candidates.map(term => term.toLocaleLowerCase('pt-BR'))))
      const pattern = unique
        .sort((a, b) => b.length - a.length)
        .map(term => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
        .join('|')
      if (!pattern) return str
      const highlighted = new Set(unique)
      const parts = str.split(new RegExp(`(${pattern})`, 'gi'))
      return (
        <>
          {parts.map((p, i) =>
            highlighted.has(p.toLocaleLowerCase('pt-BR'))
              ? <mark key={i} className="rounded-sm bg-dourado/25 px-0.5 not-italic font-semibold text-dourado">{p}</mark>
              : p
          )}
        </>
      )
    } catch {
      return str
    }
  }

  const displayAuthor = hit.chunk_author || hit.author

  return (
    <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4 space-y-2">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          {displayAuthor && (
            <p className="text-xs font-semibold text-dourado">{displayAuthor}</p>
          )}
          {hit.work_title && (
            <p className="text-xs italic text-texto-secundario">{hit.work_title}</p>
          )}
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] text-texto-terciario">
            <span className="rounded border border-dourado/20 bg-dourado/8 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-dourado/80">
              {isPdfLocator ? 'Página no PDF' : 'Trecho da obra'}
            </span>
            {!isPdfLocator && hit.match_type === 'semantic' && (
              <span className="rounded border border-emerald-800/40 bg-emerald-950/20 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-300">
                Correspondência temática multilíngue
              </span>
            )}
            {isPdfLocator && (
              <span className="rounded border border-amber-800/35 bg-amber-950/20 px-1.5 py-0.5 text-[9px] font-semibold text-amber-300">
                {hit.source_fidelity_label}
              </span>
            )}
            {hit.collection && (
              <span className="rounded border border-dourado/20 bg-dourado/8 px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide text-dourado/80">
                {hit.collection}
              </span>
            )}
            {hit.edition_label && <span>{hit.edition_label}</span>}
            {hit.volume != null && <span>vol. {hit.volume}</span>}
            {hit.chapter_or_section && <span className="max-w-[160px] truncate" title={hit.chapter_or_section}>{hit.chapter_or_section}</span>}
            {hit.pdf_page != null && <span className="font-medium text-texto-secundario">p. {hit.pdf_page}</span>}
            {hit.language && <span className="italic">{hit.language}</span>}
          </div>
        </div>
        <div className="flex shrink-0 gap-2">
          {pdfHref && (
            <Link
              href={pdfHref}
              className="rounded border border-dourado/30 px-2 py-1 text-[10px] font-medium text-dourado transition-colors hover:bg-dourado/10"
            >
              {isPdfLocator ? 'Conferir no PDF' : 'Abrir PDF'}
            </Link>
          )}
          {hit.book_id != null && (
            <Link
              href={`/biblioteca/${hit.book_id}`}
              className="rounded border border-fundo-borda px-2 py-1 text-[10px] text-texto-terciario transition-colors hover:border-dourado/30 hover:text-texto"
            >
              Ver obra
            </Link>
          )}
        </div>
      </div>
      {text && (
        <blockquote className="border-l-2 border-dourado/30 pl-3 text-sm leading-relaxed text-texto">
          {highlight(text)}
        </blockquote>
      )}
      {hit.source_warning && (
        <p className="rounded border border-amber-800/35 bg-amber-950/20 px-2 py-1.5 text-[10px] text-amber-300">
          {hit.source_warning}
        </p>
      )}
      {translatedPassage && translatedPassage !== originalPassage && (
        <details className="text-xs text-texto-terciario">
          <summary className="cursor-pointer select-none transition-colors hover:text-dourado">
            Ver texto traduzido (indexado)
          </summary>
          <p className="mt-2 border-l-2 border-fundo-borda pl-3 leading-relaxed italic text-texto-secundario">
            {highlight(translatedPassage)}
          </p>
        </details>
      )}
    </div>
  )
}

function CatechismPassageCard({
  passage,
  comparisonLabel,
  evidenceTerms = [],
}: {
  passage: CatechismPassage
  comparisonLabel?: string
  evidenceTerms?: string[]
}) {
  const firstPage = passage.source.pages.find(page => Number.isInteger(page) && page > 0) ?? null
  const pdfHref = passage.source.book_file_id == null
    ? null
    : (() => {
        const params = new URLSearchParams({
          file: getPdfUrl(passage.source.book_file_id!),
        })
        if (firstPage != null) params.set('page', String(firstPage))

        // The page coordinate comes from the same indexed edition as the
        // passage. Sending a short excerpt also lets the viewer mark the exact
        // paragraph instead of merely opening the PDF near it.
        const sourceExcerpt = passage.text.replace(/\s+/g, ' ').trim().slice(0, 700)
        if (sourceExcerpt) params.set('quote', sourceExcerpt)
        return `/viewer/pdf?${params.toString()}`
      })()
  return (
    <article className="space-y-3 rounded-lg border border-fundo-borda bg-fundo-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          {comparisonLabel && (
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-dourado">
              {comparisonLabel}
            </p>
          )}
          <h3 className="font-garamond text-lg font-medium text-texto">{passage.source_title}</h3>
          <p className="mt-0.5 text-xs font-semibold text-dourado">{passage.locator}</p>
          {passage.section_title && (
            <p className="mt-0.5 text-xs text-texto-terciario">{passage.section_title}</p>
          )}
        </div>
        <div className="flex shrink-0 gap-2">
          {pdfHref && (
            <Link
              href={pdfHref}
              className="rounded border border-dourado/30 px-2 py-1 text-[10px] font-medium text-dourado transition-colors hover:bg-dourado/10"
            >
              Conferir no PDF
            </Link>
          )}
          <Link
            href={`/biblioteca/${passage.source.book_id}`}
            className="rounded border border-fundo-borda px-2 py-1 text-[10px] text-texto-terciario transition-colors hover:border-dourado/30 hover:text-texto"
          >
            Ver obra
          </Link>
        </div>
      </div>
      <blockquote className="border-l-2 border-dourado/30 pl-3 text-sm leading-relaxed text-texto">
        {passage.text}
      </blockquote>
      <div className="flex flex-wrap items-center gap-1.5 text-[10px] text-texto-terciario">
        <span className="rounded border border-dourado/20 bg-dourado/8 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-dourado/80">
          Texto extraído da edição indexada
        </span>
        {passage.source.edition_label && <span>{passage.source.edition_label}</span>}
        {passage.source.pages.length > 0 && <span>p. {passage.source.pages.join(', ')}</span>}
        {passage.source.language && <span className="italic">{passage.source.language}</span>}
      </div>
      {evidenceTerms.length > 0 && (
        <p className="text-[10px] text-texto-terciario">
          Correspondência apoiada por: {evidenceTerms.slice(0, 6).join(', ')}.
        </p>
      )}
    </article>
  )
}

function languageParts(language: string | null): string[] {
  return (language ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+e\s+/g, '+')
    .split(/[+/;,|]/)
    .map(part => part.trim())
    .filter(Boolean)
}

function isPatrologiaOrientalis(book: Book): boolean {
  if ((book.collection ?? '').trim().toUpperCase() === 'PO') return true

  const identity = [book.collection, book.title, book.canonical_title]
    .filter(Boolean)
    .join(' ')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()

  return identity.includes('patrologia orientalis') || identity.includes('patristica orientalis')
}

function patristicShelvesFor(book: Book): PatristicShelf[] {
  const parts = languageParts(book.language)
  const isBilingualGreekPortuguese = parts.includes('grc') && parts.includes('pt')
  const isEnglishEdition = parts.some(part => ['en', 'eng', 'english', 'ingles'].includes(part))
  const isDidaque = [book.collection, book.title, book.canonical_title]
    .filter(Boolean)
    .join(' ')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .includes('didaque')

  // Volumes PO permanecem sempre na Patrística Oriental, independentemente
  // dos vários idiomas presentes na edição.
  if (isPatrologiaOrientalis(book)) {
    return ['oriental']
  }

  // Edições integralmente em inglês têm uma estante própria e exclusiva.
  if (isEnglishEdition) {
    return ['inglesa']
  }

  if (isDidaque && isBilingualGreekPortuguese) {
    return ['grega', 'portuguesa']
  }

  return [book.patristic_tradition ?? 'latina']
}

const OFFICIAL_DOCUMENT_TYPES: DocumentType[] = [
  'concilio',
  'bula',
  'enciclica',
  'constituicao_apostolica',
  'carta_apostolica',
  'motu_proprio',
  'exortacao_apostolica',
  'catecismo',
  'catequese',
  'liturgia',
  'doutrina_social',
  'direito_canonico',
]

function normalizeName(value: string | null | undefined): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

function bookAuthorName(book: Book): string {
  return (book.canonical_author ?? book.author ?? 'Autor desconhecido').trim()
}

function isSaintWork(book: Book): boolean {
  if (book.library_section === 'patristica') return false

  const documentType = (book.document_type ?? 'outro') as DocumentType
  if (OFFICIAL_DOCUMENT_TYPES.includes(documentType)) return false

  const author = normalizeName(bookAuthorName(book))
  return /\b(santo|santa|sao|beato|beata)\b/.test(author)
}

function addAuthorWork(map: Record<string, Record<string, Book[]>>, book: Book): void {
  const author = bookAuthorName(book)
  const title = book.canonical_title ?? book.title
  if (!map[author]) map[author] = {}
  if (!map[author][title]) map[author][title] = []
  map[author][title].push(book)
}

function authorEntriesFromMap(map: Record<string, Record<string, Book[]>>): AuthorEntry[] {
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b, 'pt'))
    .map(([author, works]) => ({
      author,
      works: Object.entries(works)
        .sort(([a], [b]) => a.localeCompare(b, 'pt'))
        .map(([title, bks]) => ({ title, books: bks })),
    }))
}

function countDocumentos(documentos: DocumentosLibrary): number {
  const papal = documentos.byPope.reduce((sum, entry) => sum + entry.totalCount, 0)
  const nonPapal = Object.values(documentos.nonPapal)
    .reduce((sum, items) => sum + (items?.length ?? 0), 0)
  return papal + nonPapal
}

function countAuthorBooks(entries: AuthorEntry[]): number {
  return entries.reduce(
    (sum, entry) => sum + entry.works.reduce((workSum, work) => workSum + work.books.length, 0),
    0
  )
}

function organizeLibrary(books: Book[]): LibraryStructure {
  const patristica: LibraryStructure['patristica'] = {
    grega: [],
    oriental: [],
    latina: [],
    inglesa: [],
    portuguesa: [],
  }

  const popeMap: Record<string, Book[]> = {}
  const nonPapalMap: Partial<Record<DocumentType, Book[]>> = {}
  const autorMap: Record<string, Record<string, Book[]>> = {}
  const santoMap: Record<string, Record<string, Book[]>> = {}

  for (const book of books) {
    if (isSaintWork(book)) {
      addAuthorWork(santoMap, book)
    } else if (book.library_section === 'documentos') {
      const dt = (book.document_type ?? 'outro') as DocumentType
      const NON_PAPAL_TYPES: DocumentType[] = ['concilio', 'catecismo', 'catequese', 'direito_canonico']
      if (!NON_PAPAL_TYPES.includes(dt) && book.pope) {
        const popeName = book.pope
        if (!popeMap[popeName]) popeMap[popeName] = []
        popeMap[popeName].push(book)
      } else {
        if (!nonPapalMap[dt]) nonPapalMap[dt] = []
        nonPapalMap[dt]!.push(book)
      }
    } else {
      for (const shelf of patristicShelvesFor(book)) {
        patristica[shelf].push(book)
      }

      addAuthorWork(autorMap, book)
    }
  }

  const byPope: PopeDocumentEntry[] = Object.entries(popeMap).map(([pope, popeBooks]) => {
    const types: Partial<Record<DocumentType, Book[]>> = {}
    for (const book of popeBooks) {
      const dt = (book.document_type ?? 'outro') as DocumentType
      if (!types[dt]) types[dt] = []
      types[dt]!.push(book)
    }
    const years = popeBooks.map(b => b.document_year).filter(Boolean) as number[]
    return {
      pope,
      latestYear: years.length ? Math.max(...years) : null,
      totalCount: popeBooks.length,
      types,
    }
  })
  byPope.sort((a, b) => {
    if (a.pope === 'Outros') return 1
    if (b.pope === 'Outros') return -1
    return (b.latestYear ?? 0) - (a.latestYear ?? 0)
  })

  const documentos: DocumentosLibrary = { byPope, nonPapal: nonPapalMap }

  const obras_por_autor = authorEntriesFromMap(autorMap)
  const obras_santos = authorEntriesFromMap(santoMap)

  return { patristica, obras_por_autor, obras_santos, documentos }
}

type Section = 'patristica' | 'autores' | 'santos' | 'documentos'
type SourceScope = 'todos' | 'primarias' | 'pdf' | 'indexadas'
type SortMode = 'catalogo' | 'titulo' | 'autor' | 'ano'

const SECTION_TABS: { id: Section; label: string }[] = [
  { id: 'patristica', label: 'Biblioteca Patrística' },
  { id: 'autores', label: 'Obras dos Padres' },
  { id: 'santos', label: 'Obras dos Santos' },
  { id: 'documentos', label: 'Documentos da Igreja' },
]

function normalizeForSearch(value: string | null | undefined): string {
  return (value ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

function bookSearchText(book: Book): string {
  return normalizeForSearch([
    book.title,
    book.canonical_title,
    book.author,
    book.canonical_author,
    book.collection,
    book.edition_label,
    book.source_label,
    book.pope,
    book.document_status,
  ].filter(Boolean).join(' '))
}

function hasPdf(book: Book): boolean {
  return (book.files?.length ?? 0) > 0
}

function filterBooks(books: Book[], query: string, scope: SourceScope): Book[] {
  const cleanQuery = normalizeForSearch(query.trim())

  return books.filter((book) => {
    if (cleanQuery && !bookSearchText(book).includes(cleanQuery)) return false
    if (scope === 'primarias' && !book.is_primary_source) return false
    if (scope === 'pdf' && !hasPdf(book)) return false
    if (scope === 'indexadas' && (book.chunk_count ?? 0) <= 0) return false
    return true
  })
}

function sortBooks(books: Book[], sortMode: SortMode): Book[] {
  const sorted = [...books]
  if (sortMode === 'titulo') {
    sorted.sort((a, b) => a.title.localeCompare(b.title, 'pt'))
  }
  if (sortMode === 'autor') {
    sorted.sort((a, b) =>
      (a.canonical_author ?? a.author ?? '').localeCompare(b.canonical_author ?? b.author ?? '', 'pt')
      || a.title.localeCompare(b.title, 'pt')
    )
  }
  if (sortMode === 'ano') {
    sorted.sort((a, b) => (b.document_year ?? 0) - (a.document_year ?? 0) || a.title.localeCompare(b.title, 'pt'))
  }
  return sorted
}

function SearchLoginPrompt({ mode }: { mode: string }) {
  return (
    <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center space-y-3">
      <p className="text-sm font-medium text-texto">{mode} requer uma conta</p>
      <p className="text-xs text-texto-terciario">
        Faça login para pesquisar nos trechos dos Padres e documentos do acervo.
      </p>
      <Link
        href="/login"
        className="inline-block rounded-lg border border-dourado/40 bg-dourado/10 px-5 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/20"
      >
        Entrar na conta
      </Link>
    </div>
  )
}

function SearchQuotaPrompt({ usage }: { usage: SearchUsageInfo | null }) {
  const limitStr = usage?.limit != null ? String(usage.limit) : '—'
  const usedStr = usage?.used != null ? String(usage.used) : '—'
  return (
    <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center space-y-3">
      <p className="text-sm font-medium text-texto">Limite diário de buscas atingido</p>
      <p className="text-xs text-texto-terciario">
        {usage?.limit != null
          ? `Você usou ${usedStr} de ${limitStr} buscas hoje.`
          : 'Limite diário atingido.'}{' '}
        Renova automaticamente à meia-noite.
      </p>
      <Link
        href="/planos"
        className="inline-block rounded-lg border border-dourado/40 bg-dourado/10 px-5 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/20"
      >
        Ver planos e aumentar limite →
      </Link>
    </div>
  )
}

function SearchUsageBadge({ usage }: { usage: SearchUsageInfo | null }) {
  if (!usage) return null
  if (usage.limit === null) {
    return (
      <span className="text-[10px] text-texto-terciario">Buscas ilimitadas</span>
    )
  }
  const pct = Math.min(100, Math.round((usage.used / usage.limit) * 100))
  const isAlmost = pct >= 80
  return (
    <span className={`flex items-center gap-1.5 text-[10px] ${isAlmost ? 'text-vermelho/70' : 'text-texto-terciario'}`}>
      <span className="inline-block h-1 w-16 rounded-full bg-fundo-borda overflow-hidden">
        <span
          className={`block h-full rounded-full ${isAlmost ? 'bg-vermelho/60' : 'bg-dourado/60'}`}
          style={{ width: `${pct}%` }}
        />
      </span>
      {usage.used}/{usage.limit} hoje
    </span>
  )
}

export default function LibraryView({
  books,
  catalog,
}: {
  books: Book[]
  catalog: AuthorCatalogEntry[]
}) {
  const [section, setSection] = useState<Section>('patristica')
  const [query, setQuery] = useState('')
  const [scope, setScope] = useState<SourceScope>('todos')
  const [sortMode, setSortMode] = useState<SortMode>('catalogo')

  // ── Busca no conteúdo do acervo ──
  type SearchMode = 'catalogo' | 'conteudo' | 'biblia' | 'catecismo'
  const [searchMode, setSearchMode] = useState<SearchMode>('catalogo')
  const [contentQuery, setContentQuery] = useState('')
  const [acervoCollection, setAcervoCollection] = useState<'patristica' | 'all'>('patristica')
  const [lastAcervoCollection, setLastAcervoCollection] = useState<'patristica' | 'all'>('patristica')
  const [bibleQuery, setBibleQuery] = useState('')
  const [acervoResults, setAcervoResults] = useState<AcervoSearchResult[]>([])
  const [contentReadableTotal, setContentReadableTotal] = useState(0)
  const [contentNextCursor, setContentNextCursor] = useState<string | null>(null)
  const [acervoLoading, setAcervoLoading] = useState(false)
  const [contentLoadingMore, setContentLoadingMore] = useState(false)
  const [contentLoadMoreError, setContentLoadMoreError] = useState('')
  const [acervoError, setAcervoError] = useState('')
  const [totalMatchingPages, setTotalMatchingPages] = useState(0)
  const [totalMatchingWorks, setTotalMatchingWorks] = useState(0)
  const [expandedTerms, setExpandedTerms] = useState<string[]>([])
  const [lastAcervoQuery, setLastAcervoQuery] = useState('')
  const contentInputRef = useRef<HTMLInputElement>(null)
  const bibleInputRef = useRef<HTMLInputElement>(null)
  const acervoRequestSeq = useRef(0)
  const acervoAbortRef = useRef<AbortController | null>(null)
  // ── Catecismo ──
  const [cccInput, setCccInput] = useState('')
  const [cccConcordance, setCccConcordance] = useState<CatechismConcordanceResponse | null>(null)
  const [cccLoading, setCccLoading] = useState(false)
  const [cccError, setCccError] = useState('')
  const [lastCccArticle, setLastCccArticle] = useState<number | null>(null)
  const cccRequestSeq = useRef(0)
  const cccRequestInFlight = useRef(false)
  const cccAbortRef = useRef<AbortController | null>(null)
  // ── Quota de busca ──
  const [searchUsage, setSearchUsage] = useState<SearchUsageInfo | null>(null)

  const isLoggedIn = !!getToken()

  const loadSearchUsage = useCallback(async () => {
    if (!getToken()) return
    try {
      const usage = await getSearchUsage()
      setSearchUsage(usage)
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => () => {
    acervoRequestSeq.current += 1
    acervoAbortRef.current?.abort()
    cccRequestSeq.current += 1
    cccAbortRef.current?.abort()
  }, [])

  const runContentSearch = useCallback(async (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || trimmed.length < 2) return
    acervoAbortRef.current?.abort()
    const controller = new AbortController()
    const requestSeq = acervoRequestSeq.current + 1
    acervoRequestSeq.current = requestSeq
    acervoAbortRef.current = controller
    setAcervoLoading(true)
    setAcervoError('')
    setAcervoResults([])
    setContentReadableTotal(0)
    setContentNextCursor(null)
    setContentLoadMoreError('')
    setTotalMatchingPages(0)
    setTotalMatchingWorks(0)
    setExpandedTerms([])
    setLastAcervoQuery(trimmed)
    setLastAcervoCollection(acervoCollection)
    try {
      // quotes_only=true uses the lexical scan with theological variant
      // expansion (e.g. "Eucaristia" → "Eucharistia" for Migne Latin chunks).
      // For patrística, the backend also includes OCR locators as highlighted
      // excerpt cards. For todo o acervo, strict verified-text gate applies.
      // Patrística: request up to 200 at once (OCR locators + source_text).
      // Todo o acervo: strict page size with cursor pagination.
      const isPatristica = acervoCollection === 'patristica'
      const res = await searchAcervo(trimmed, {
        limit: isPatristica ? 200 : CONTENT_SEARCH_PAGE_SIZE,
        // '' → backend defaults to patristica; 'all' → todo o acervo
        collection: isPatristica ? '' : 'all',
        quotesOnly: true,
        signal: controller.signal,
      })
      if (acervoRequestSeq.current !== requestSeq) return
      setAcervoResults(res.results)
      setContentReadableTotal(
        res.results.filter(hit => hit.source_fidelity !== 'unverified_ocr' && hit.text.trim()).length,
      )
      setContentNextCursor(res.next_cursor ?? null)
      setTotalMatchingPages(res.total_matching_pages ?? 0)
      setTotalMatchingWorks(res.total_matching_works ?? 0)
      setExpandedTerms(res.expanded_terms ?? [])
      if (res.results.length === 0) {
        setAcervoError(
          acervoCollection === 'patristica'
            ? 'Nenhuma citação dos Padres da Igreja foi encontrada. Tente "Todo o acervo" para buscar em todos os documentos.'
            : 'Nenhuma citação conferida do acervo foi encontrada para essa busca.',
        )
      }
    } catch (err: unknown) {
      if (acervoRequestSeq.current !== requestSeq) return
      if (err instanceof ApiError && err.status === 401) {
        setAcervoError('LOGIN_REQUIRED')
      } else if (err instanceof ApiError && err.status === 429) {
        setAcervoError('QUOTA_EXCEEDED')
      } else if (err instanceof ApiError && err.status === 408) {
        setAcervoError('A busca demorou demais. Tente novamente.')
      } else {
        setAcervoError('Erro ao buscar no acervo. Verifique sua conexão.')
      }
    } finally {
      if (acervoRequestSeq.current === requestSeq) {
        acervoAbortRef.current = null
        setAcervoLoading(false)
        void loadSearchUsage()
      }
    }
  }, [loadSearchUsage, acervoCollection])

  const showMoreContentResults = useCallback(async () => {
    if (!contentNextCursor || contentLoadingMore || !lastAcervoQuery) return

    const controller = new AbortController()
    const requestSeq = acervoRequestSeq.current
    acervoAbortRef.current = controller
    setContentLoadingMore(true)
    setContentLoadMoreError('')
    try {
      const isPatristica = lastAcervoCollection === 'patristica'
      const res = await searchAcervo(lastAcervoQuery, {
        limit: isPatristica ? 200 : CONTENT_SEARCH_PAGE_SIZE,
        collection: isPatristica ? '' : 'all',
        quotesOnly: true,
        cursor: contentNextCursor,
        signal: controller.signal,
      })
      if (acervoRequestSeq.current !== requestSeq) return

      setAcervoResults(current => {
        const identities = new Set(current.map(searchResultIdentity))
        const appended = res.results.filter(hit => {
          const identity = searchResultIdentity(hit)
          if (identities.has(identity)) return false
          identities.add(identity)
          return true
        })
        const combined = [...current, ...appended]
        // BUG FIX: count only readable (verified) hits, not OCR locators.
        // combined.length previously included unverified_ocr locator pages,
        // causing "254 trechos exibidos" when only 9 readable cards rendered.
        setContentReadableTotal(
          combined.filter(hit => hit.source_fidelity !== 'unverified_ocr' && Boolean(hit.text.trim())).length
        )
        return combined
      })
      setContentNextCursor(res.next_cursor ?? null)
    } catch (err: unknown) {
      if (acervoRequestSeq.current !== requestSeq) return
      if (err instanceof ApiError && err.status === 422) {
        setContentNextCursor(null)
        setContentLoadMoreError('A continuação expirou. Faça a busca novamente para atualizar os resultados.')
      } else if (err instanceof ApiError && err.status === 408) {
        setContentLoadMoreError('O carregamento demorou demais. Tente carregar novamente.')
      } else {
        setContentLoadMoreError('Não foi possível carregar as próximas páginas. Tente novamente.')
      }
    } finally {
      if (acervoRequestSeq.current === requestSeq) {
        acervoAbortRef.current = null
        setContentLoadingMore(false)
      }
    }
  }, [
    contentLoadingMore,
    contentNextCursor,
    lastAcervoQuery,
    lastAcervoCollection,
  ])

  // Auto-load all remaining pages for patrística so user never needs to click "load more"
  useEffect(() => {
    if (
      lastAcervoCollection === 'patristica'
      && contentNextCursor
      && !contentLoadingMore
      && !acervoLoading
    ) {
      void showMoreContentResults()
    }
  }, [lastAcervoCollection, contentNextCursor, contentLoadingMore, acervoLoading, showMoreContentResults])

  const runBibleSearch = useCallback(async (ref: string) => {
    const trimmed = ref.trim()
    if (!trimmed) return
    acervoAbortRef.current?.abort()
    const controller = new AbortController()
    const requestSeq = acervoRequestSeq.current + 1
    acervoRequestSeq.current = requestSeq
    acervoAbortRef.current = controller
    setAcervoLoading(true)
    setAcervoError('')
    setAcervoResults([])
    setLastAcervoQuery(trimmed)
    try {
      const res = await searchBible(trimmed, 20, controller.signal)
      if (acervoRequestSeq.current !== requestSeq) return
      setAcervoResults(res.results)
      setLastAcervoQuery(res.query)
      if (res.results.length === 0) setAcervoError('Nenhum trecho dos Padres encontrado para essa referência.')
    } catch (err: unknown) {
      if (acervoRequestSeq.current !== requestSeq) return
      if (err instanceof ApiError && err.status === 401) {
        setAcervoError('LOGIN_REQUIRED')
      } else if (err instanceof ApiError && err.status === 429) {
        setAcervoError('QUOTA_EXCEEDED')
      } else if (err instanceof ApiError && err.status === 408) {
        setAcervoError('A busca demorou demais. Tente novamente.')
      } else {
        setAcervoError('Erro ao buscar. Verifique o formato da referência.')
      }
    } finally {
      if (acervoRequestSeq.current === requestSeq) {
        acervoAbortRef.current = null
        setAcervoLoading(false)
        void loadSearchUsage()
      }
    }
  }, [loadSearchUsage])

  const runCccSearch = useCallback(async (raw: string) => {
    // State updates are asynchronous. This synchronous lock prevents a held
    // Enter key (or a near-simultaneous click) from issuing two quota-bearing
    // requests before `cccLoading` has reached the DOM.
    if (cccRequestInFlight.current) return
    const normalized = raw.trim()
    const n = /^\d+$/.test(normalized) ? Number(normalized) : Number.NaN
    if (!Number.isInteger(n) || n < 1 || n > 2865) {
      setCccConcordance(null)
      setCccError('Digite um número de parágrafo válido entre 1 e 2865.')
      return
    }
    cccRequestInFlight.current = true
    cccAbortRef.current?.abort()
    const controller = new AbortController()
    cccAbortRef.current = controller
    const requestSeq = cccRequestSeq.current + 1
    cccRequestSeq.current = requestSeq
    setCccLoading(true)
    setCccError('')
    setCccConcordance(null)
    setLastCccArticle(n)
    try {
      const res = await getCatechismConcordance(n, {
        patristicLimit: 8,
        signal: controller.signal,
      })
      if (cccRequestSeq.current !== requestSeq) return
      setCccConcordance(res)
    } catch (err: unknown) {
      if (cccRequestSeq.current !== requestSeq) return
      if (err instanceof ApiError && err.status === 401) {
        setCccError('LOGIN_REQUIRED')
      } else if (err instanceof ApiError && err.status === 429) {
        setCccError('QUOTA_EXCEEDED')
      } else if (err instanceof ApiError && err.status === 408) {
        setCccError('A busca demorou demais. Tente novamente.')
      } else {
        setCccError('Erro ao buscar. Tente novamente.')
      }
    } finally {
      cccRequestInFlight.current = false
      if (cccRequestSeq.current === requestSeq) {
        cccAbortRef.current = null
        setCccLoading(false)
        cccRequestSeq.current = 0
        void loadSearchUsage()
      }
    }
  }, [loadSearchUsage])

  const switchSearchMode = useCallback((mode: SearchMode) => {
    acervoRequestSeq.current += 1
    acervoAbortRef.current?.abort()
    acervoAbortRef.current = null
    cccRequestSeq.current += 1
    cccAbortRef.current?.abort()
    cccAbortRef.current = null
    cccRequestInFlight.current = false
    setAcervoLoading(false)
    setCccLoading(false)
    setAcervoResults([])
    setContentReadableTotal(0)
    setAcervoError('')
    setCccError('')
    setSearchMode(mode)
    if (mode !== 'catalogo') void loadSearchUsage()
  }, [loadSearchUsage])


  const visibleBooks = sortBooks(filterBooks(books, query, scope), sortMode)
  const library = organizeLibrary(visibleBooks)
  const hasFocusedCatalog = query.trim().length > 0 || scope !== 'todos'
  const primaryCount = books.filter(book => book.is_primary_source).length
  const pdfCount = books.filter(hasPdf).length
  const chunkTotal = books.reduce((sum, book) => sum + (book.chunk_count ?? 0), 0)
  const patristicCount = Object.values(library.patristica).reduce((sum, items) => sum + items.length, 0)
  const saintWorksCount = countAuthorBooks(library.obras_santos)
  const documentCount = countDocumentos(library.documentos)
  const readableAcervoResults = acervoResults.filter(
    hit => hit.source_fidelity !== 'unverified_ocr' && Boolean(hit.text.trim()),
  )
  const sectionCount: Record<Section, number> = {
    patristica: patristicCount,
    autores: catalog.filter(entry => entry.book_count > 0).length,
    santos: saintWorksCount,
    documentos: documentCount,
  }

  return (
    <div className="space-y-5">
      <section className="border-y border-fundo-borda py-4">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
              Acervo de referência
            </p>
            <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
              Fontes catalogadas para estudo e verificação
            </h2>
            <p className="mt-1 max-w-xl text-sm leading-relaxed text-texto-secundario">
              Biblioteca, documentos, edições e PDFs tratados como acervo consultável, não apenas como lista de arquivos.
            </p>
          </div>

          <div className="grid shrink-0 grid-cols-2 gap-2 sm:grid-cols-4">
            {[
              { label: 'obras', value: books.length, tone: 'text-texto' },
              { label: 'primárias', value: primaryCount, tone: 'text-dourado' },
              { label: 'PDFs', value: pdfCount, tone: 'text-texto' },
              { label: 'trechos', value: chunkTotal, tone: 'text-dourado' },
            ].map(stat => (
              <div key={stat.label} className="rounded-md border border-fundo-borda bg-fundo-card px-3 py-2 text-right">
                <p className={`font-mono text-sm font-semibold ${stat.tone}`}>
                  {stat.value.toLocaleString('pt-BR')}
                </p>
                <p className="mt-0.5 text-[10px] leading-tight text-texto-terciario">
                  {stat.label}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="library-search">
              Busca universal
            </label>
            <p className="mt-0.5 text-xs text-texto-terciario">
              Procure por obra, autor, papa, concílio, coleção, edição ou tema.
            </p>
          </div>
          <button
            type="button"
            onClick={() => {
              setQuery('')
              setScope('todos')
              setSortMode('catalogo')
            }}
            className={`self-start rounded-md border px-2 py-1 text-xs transition-colors sm:self-auto ${
              hasFocusedCatalog
                ? 'border-dourado/30 text-dourado hover:bg-dourado/10'
                : 'border-fundo-borda text-texto-terciario hover:border-dourado/30 hover:text-texto'
            }`}
          >
            Limpar
          </button>
        </div>
        <div className="mt-2 grid gap-2 sm:grid-cols-[minmax(0,1fr)_160px_150px]">
          <input
            id="library-search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Buscar por obra, autor, coleção ou edição"
            className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
          />
          <select
            value={scope}
            onChange={(event) => setScope(event.target.value as SourceScope)}
            className="rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none focus:border-dourado/50"
          >
            <option value="todos">Todo o acervo</option>
            <option value="primarias">Fontes primárias</option>
            <option value="pdf">Com PDF</option>
            <option value="indexadas">Indexadas</option>
          </select>
          <select
            value={sortMode}
            onChange={(event) => setSortMode(event.target.value as SortMode)}
            className="rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none focus:border-dourado/50"
          >
            <option value="catalogo">Ordem do catálogo</option>
            <option value="titulo">Título A-Z</option>
            <option value="autor">Autor A-Z</option>
            <option value="ano">Ano recente</option>
          </select>
        </div>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="rounded-md border border-fundo-borda bg-fundo px-2 py-1 text-texto-terciario">
            Patrística: <span className="text-texto">{patristicCount.toLocaleString('pt-BR')}</span>
          </span>
          <span className="rounded-md border border-fundo-borda bg-fundo px-2 py-1 text-texto-terciario">
            Documentos: <span className="text-texto">{documentCount.toLocaleString('pt-BR')}</span>
          </span>
          <span className="rounded-md border border-fundo-borda bg-fundo px-2 py-1 text-texto-terciario">
            Obras dos Santos: <span className="text-texto">{saintWorksCount.toLocaleString('pt-BR')}</span>
          </span>
          <span className="rounded-md border border-fundo-borda bg-fundo px-2 py-1 text-texto-terciario">
            Autores com obras: <span className="text-texto">{sectionCount.autores.toLocaleString('pt-BR')}</span>
          </span>
        </div>
      </section>

      {/* ── Seletor de modo de busca ── */}
      <div className="flex gap-1 rounded-lg border border-fundo-borda bg-fundo-card p-1">
        {([
          { id: 'catalogo' as const, label: 'Catálogo', desc: 'Navegar obras' },
          { id: 'conteudo' as const, label: 'Citações do Acervo', desc: 'Corpo de todas as obras' },
          { id: 'biblia' as const, label: 'Catena Patrum', desc: 'Por versículo bíblico' },
          { id: 'catecismo' as const, label: 'Catecismos', desc: 'Comparar e aprofundar' },
        ]).map(mode => (
          <button
            key={mode.id}
            type="button"
            onClick={() => switchSearchMode(mode.id)}
            className={`flex-1 rounded-md px-2 py-2 text-xs font-medium leading-tight transition-colors ${
              searchMode === mode.id
                ? 'bg-dourado/15 text-dourado'
                : 'text-texto-terciario hover:text-texto-secundario'
            }`}
          >
            <span className="block">{mode.label}</span>
            <span className="mt-0.5 block text-[10px] opacity-70">{mode.desc}</span>
          </button>
        ))}
      </div>

      {/* ── Busca no conteúdo do acervo ── */}
      {searchMode === 'conteudo' && (
        <section className="space-y-3">
          {!isLoggedIn ? (
            <SearchLoginPrompt mode="Citações do Acervo" />
          ) : (
          <div className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="acervo-search">
                Citações do Acervo
              </label>
              <SearchUsageBadge usage={searchUsage} />
            </div>
            {/* Filtro de coleção */}
            <div className="mb-2 flex flex-wrap gap-1.5">
              {([
                { key: 'patristica' as const, label: 'Patrística e Patrologia' },
                { key: 'all' as const, label: 'Todo o acervo' },
              ]).map(({ key, label }) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => {
                    if (acervoCollection !== key) {
                      setAcervoCollection(key)
                      setAcervoResults([])
                      setContentReadableTotal(0)
                      setContentNextCursor(null)
                      setAcervoError('')
                    }
                  }}
                  className={`rounded-full border px-3 py-0.5 text-[11px] font-medium transition-colors ${
                    acervoCollection === key
                      ? 'border-dourado bg-dourado/15 text-dourado'
                      : 'border-fundo-borda text-texto-terciario hover:border-dourado/40 hover:text-texto-secundario'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
            <p className="mb-2 text-xs text-texto-terciario">
              {acervoCollection === 'patristica'
                ? 'Busca nos escritos dos Padres da Igreja e na Patrologia, em qualquer idioma. Somente citações do corpo das obras com texto fiel à edição.'
                : 'Pesquise qualquer palavra ou frase em todo o acervo, inclusive entre idiomas. Somente citações com redação fiel à edição; índices, sumários e OCR não conferido são excluídos.'}
            </p>
            <form
              className="flex gap-2"
              onSubmit={event => {
                event.preventDefault()
                void runContentSearch(contentQuery)
              }}
            >
              <input
                ref={contentInputRef}
                id="acervo-search"
                type="search"
                value={contentQuery}
                onChange={e => setContentQuery(e.target.value)}
                disabled={acervoLoading}
                placeholder="Ex: eucaristia, batismo, Trindade, ressurreição…"
                className="flex-1 rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
                style={{ fontSize: '16px' }}
              />
              <button
                type="submit"
                disabled={acervoLoading || contentQuery.trim().length < 2}
                className="rounded-lg border border-dourado/40 bg-dourado/10 px-4 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/20 disabled:opacity-40"
              >
                {acervoLoading ? 'Buscando…' : 'Buscar'}
              </button>
            </form>
          </div>
          )}

          {isLoggedIn && acervoLoading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-texto-terciario">
              <span className="animate-pulse">
              {acervoCollection === 'patristica' ? 'Buscando nos escritos dos Padres da Igreja…' : 'Buscando citações em todo o acervo…'}
            </span>
            </div>
          )}

          {isLoggedIn && !acervoLoading && acervoError === 'LOGIN_REQUIRED' && (
            <SearchLoginPrompt mode="Citações do Acervo" />
          )}

          {isLoggedIn && !acervoLoading && acervoError === 'QUOTA_EXCEEDED' && (
            <SearchQuotaPrompt usage={searchUsage} />
          )}

          {isLoggedIn && !acervoLoading && acervoError && acervoError !== 'LOGIN_REQUIRED' && acervoError !== 'QUOTA_EXCEEDED' && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">{acervoError}</p>
            </div>
          )}

          {isLoggedIn && !acervoLoading && acervoResults.length > 0 && (
            <div className="space-y-3">
              <div className="space-y-1">
                {totalMatchingWorks > 0 && (
                  <p className="text-xs text-texto-terciario">
                    <span className="font-medium text-dourado">{totalMatchingWorks}</span>{' '}
                    {totalMatchingWorks === 1 ? 'obra com correspondência' : 'obras com correspondência'}
                    {totalMatchingPages > 0 && (
                      <>
                        {' · '}
                        <span className="font-medium text-dourado">{totalMatchingPages}</span>{' '}
                        {totalMatchingPages === 1 ? 'página indexada' : 'páginas indexadas'}
                      </>
                    )}
                    {contentReadableTotal > 0 && (
                      <>
                        {' · '}
                        <span className="font-medium text-dourado">
                          {contentReadableTotal}{contentNextCursor ? '+' : ''}
                        </span>{' '}
                        {contentReadableTotal === 1 ? 'trecho verificado' : 'trechos verificados'}
                      </>
                    )}{' '}
                    para{' '}
                    <span className="font-medium text-texto">&ldquo;{lastAcervoQuery}&rdquo;</span>
                  </p>
                )}
                {totalMatchingWorks === 0 && (
                  <p className="text-xs text-texto-terciario">
                    <span className="font-medium text-texto">
                      {contentReadableTotal}{contentNextCursor ? '+' : ''}
                    </span>{' '}
                    {contentReadableTotal === 1 ? 'trecho verificado' : 'trechos verificados'} para{' '}
                    <span className="font-medium text-texto">&ldquo;{lastAcervoQuery}&rdquo;</span>
                  </p>
                )}
                {totalMatchingPages > 0 && contentReadableTotal < totalMatchingPages && !contentNextCursor && (
                  <p className="text-[10px] text-texto-terciario">
                    {totalMatchingPages - contentReadableTotal} {totalMatchingPages - contentReadableTotal === 1 ? 'página adicional localizada' : 'páginas adicionais localizadas'} por OCR — abrir PDF para ler o texto original.
                  </p>
                )}
                {expandedTerms.length > 1 && (
                  <p className="text-xs text-texto-terciario">
                    Termos buscados:{' '}
                    {expandedTerms.map((t, i) => (
                      <span key={t}>
                        <span className="font-medium text-texto-secundario">{t}</span>
                        {i < expandedTerms.length - 1 ? ', ' : ''}
                      </span>
                    ))}
                  </p>
                )}
              </div>
              {readableAcervoResults.length === 0 && !contentNextCursor && (
                <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4 text-xs text-texto-terciario">
                  Todas as {totalMatchingPages} páginas encontradas estão em formato OCR não conferido.
                  Os PDFs estão disponíveis para leitura direta, mas o texto ainda não foi verificado para exibição aqui.
                </div>
              )}
              {readableAcervoResults.map(hit => (
                <SearchResultCard key={hit.chunk_id} hit={hit} query={lastAcervoQuery} />
              ))}
              {contentNextCursor && (
                lastAcervoCollection === 'patristica' ? (
                  <p className="py-2 text-center text-xs text-texto-terciario">
                    {contentLoadingMore ? 'Localizando mais trechos patrísticos…' : 'Aguardando carregamento…'}
                  </p>
                ) : (
                  <button
                    type="button"
                    onClick={() => void showMoreContentResults()}
                    disabled={contentLoadingMore}
                    className="w-full rounded-lg border border-dourado/30 bg-dourado/5 px-4 py-3 text-sm font-medium text-dourado transition-colors hover:bg-dourado/10"
                  >
                    {contentLoadingMore
                      ? 'Carregando próximas páginas…'
                      : 'Carregar mais trechos'}
                  </button>
                )
              )}
              {contentLoadMoreError && (
                <p className="rounded border border-amber-800/35 bg-amber-950/20 px-3 py-2 text-xs text-amber-300">
                  {contentLoadMoreError}
                </p>
              )}
            </div>
          )}
        </section>
      )}

      {/* ── Catena Patrum (busca por referência bíblica) ── */}
      {searchMode === 'biblia' && (
        <section className="space-y-3">
          {!isLoggedIn ? (
            <SearchLoginPrompt mode="Catena Patrum" />
          ) : (
          <div className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="bible-search">
                Catena Patrum
              </label>
              <SearchUsageBadge usage={searchUsage} />
            </div>
            <p className="mb-2 text-xs text-texto-terciario">
              O que os Padres disseram sobre este versículo? Digite uma referência bíblica.
            </p>
            <div className="flex gap-2">
              <input
                ref={bibleInputRef}
                id="bible-search"
                type="search"
                value={bibleQuery}
                onChange={e => setBibleQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runBibleSearch(bibleQuery)}
                placeholder="Ex: Jo 6,53 · Mt 16,18 · Rm 6,3 · Gn 1,1"
                className="flex-1 rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
                style={{ fontSize: '16px' }}
              />
              <button
                type="button"
                onClick={() => runBibleSearch(bibleQuery)}
                disabled={acervoLoading || bibleQuery.trim().length < 3}
                className="rounded-lg border border-dourado/40 bg-dourado/10 px-4 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/20 disabled:opacity-40"
              >
                {acervoLoading ? 'Buscando…' : 'Buscar'}
              </button>
            </div>
            <p className="mt-1.5 text-[10px] text-texto-terciario">
              Formatos aceitos: Jo 6,53 · João 6:53 · Ioh 6,53 · Mt 16,18
            </p>
          </div>
          )}

          {isLoggedIn && acervoLoading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-texto-terciario">
              <span className="animate-pulse">Consultando os Padres sobre este versículo…</span>
            </div>
          )}

          {isLoggedIn && !acervoLoading && acervoError === 'LOGIN_REQUIRED' && (
            <SearchLoginPrompt mode="Catena Patrum" />
          )}

          {isLoggedIn && !acervoLoading && acervoError === 'QUOTA_EXCEEDED' && (
            <SearchQuotaPrompt usage={searchUsage} />
          )}

          {isLoggedIn && !acervoLoading && acervoError && acervoError !== 'LOGIN_REQUIRED' && acervoError !== 'QUOTA_EXCEEDED' && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">{acervoError}</p>
            </div>
          )}

          {isLoggedIn && !acervoLoading && acervoResults.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs text-texto-terciario">
                <span className="font-medium text-texto">{acervoResults.length}</span> trechos patrísticos sobre{' '}
                <span className="font-medium text-texto">{lastAcervoQuery}</span>
              </p>
              {acervoResults.map(hit => (
                <SearchResultCard key={hit.chunk_id} hit={hit} query={lastAcervoQuery} />
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── Concordância dos Catecismos por parágrafo do CCC ── */}
      {searchMode === 'catecismo' && (
        <section className="space-y-3">
          {!isLoggedIn ? (
            <SearchLoginPrompt mode="Concordância dos Catecismos" />
          ) : (
          <div className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="ccc-search">
                Concordância dos Catecismos
              </label>
              <SearchUsageBadge usage={searchUsage} />
            </div>
            <p className="mb-2 text-xs text-texto-terciario">
              Digite um parágrafo do Catecismo da Igreja Católica para ler o texto exato,
              compará-lo com outros catecismos e encontrar suas raízes nos Padres.
            </p>
            <form
              className="flex gap-2"
              onSubmit={event => {
                event.preventDefault()
                void runCccSearch(cccInput)
              }}
            >
              <input
                id="ccc-search"
                type="number"
                min={1}
                max={2865}
                value={cccInput}
                onChange={e => setCccInput(e.target.value)}
                disabled={cccLoading}
                placeholder="Ex: 1422 (Confissão) · 1324 (Eucaristia) · 233 (Trindade)"
                className="flex-1 rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
                style={{ fontSize: '16px' }}
              />
              <button
                type="submit"
                disabled={cccLoading || !cccInput.trim()}
                className="rounded-lg border border-dourado/40 bg-dourado/10 px-4 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/20 disabled:opacity-40"
              >
                {cccLoading ? 'Buscando…' : 'Buscar'}
              </button>
            </form>
            <p className="mt-1.5 text-[10px] text-texto-terciario">
              O número identifica apenas o parágrafo do CCC. Cada outro catecismo aparece com sua própria numeração.
            </p>
          </div>
          )}

          {isLoggedIn && cccLoading && (
            <div className="space-y-3 py-2" aria-live="polite">
              {['Localizando o texto exato…', 'Comparando os catecismos…', 'Buscando raízes nos Padres…'].map(label => (
                <div key={label} className="animate-pulse rounded-lg border border-fundo-borda bg-fundo-card p-5 text-sm text-texto-terciario">
                  {label}
                </div>
              ))}
            </div>
          )}

          {isLoggedIn && !cccLoading && cccError === 'LOGIN_REQUIRED' && (
            <SearchLoginPrompt mode="Concordância dos Catecismos" />
          )}

          {isLoggedIn && !cccLoading && cccError === 'QUOTA_EXCEEDED' && (
            <SearchQuotaPrompt usage={searchUsage} />
          )}

          {isLoggedIn && !cccLoading && cccError && cccError !== 'LOGIN_REQUIRED' && cccError !== 'QUOTA_EXCEEDED' && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">{cccError}</p>
            </div>
          )}

          {isLoggedIn && !cccLoading && cccConcordance && (
            <div className="space-y-6">
              <section className="space-y-2" aria-labelledby="ccc-anchor-title">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-dourado">
                    Texto exato solicitado
                  </p>
                  <h2 id="ccc-anchor-title" className="mt-0.5 font-garamond text-xl font-medium text-texto">
                    Catecismo da Igreja Católica — § {lastCccArticle}
                  </h2>
                  <p className="text-xs text-texto-terciario">
                    Promulgado por São João Paulo II. Transcrição extraída do parágrafo na edição indexada.
                  </p>
                </div>
                <CatechismPassageCard passage={cccConcordance.anchor} />
                {cccConcordance.themes.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {cccConcordance.themes.slice(0, 8).map(theme => (
                      <span key={theme} className="rounded-full border border-dourado/20 bg-dourado/5 px-2 py-0.5 text-[10px] text-dourado/80">
                        {theme}
                      </span>
                    ))}
                  </div>
                )}
              </section>

              <section className="space-y-3" aria-labelledby="catechism-comparisons-title">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-dourado">
                    Concordância dos Catecismos
                  </p>
                  <h2 id="catechism-comparisons-title" className="mt-0.5 font-garamond text-xl font-medium text-texto">
                    A mesma doutrina em outras fontes
                  </h2>
                  <p className="text-xs text-texto-terciario">
                    São correspondências verificadas, não números equivalentes. Cada texto mantém seu localizador próprio.
                  </p>
                </div>
                {cccConcordance.comparisons.some(item => item.status === 'matched' && item.passage) ? (
                  cccConcordance.comparisons.map(item => (
                    item.status === 'matched' && item.passage && item.match ? (
                      <CatechismPassageCard
                        key={`${item.source}-${item.passage.locator}`}
                        passage={item.passage}
                        comparisonLabel={item.match.kind === 'explicit_cross_reference'
                          ? 'Correspondência indicada explicitamente pela fonte'
                          : 'Correspondência temática verificada'}
                        evidenceTerms={item.match.evidence_terms}
                      />
                    ) : null
                  ))
                ) : (
                  <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4 text-xs text-texto-terciario">
                    Nenhuma correspondência segura foi encontrada nas fontes disponíveis.
                  </div>
                )}
                {cccConcordance.comparisons
                  .filter(item => item.status !== 'matched')
                  .map(item => (
                    <p key={item.source} className="text-[10px] text-texto-terciario">
                      <span className="font-medium text-texto-secundario">{item.source_title}:</span>{' '}
                      {item.message ?? 'Nenhuma correspondência confiável encontrada.'}
                    </p>
                  ))}
              </section>

              <section className="space-y-3" aria-labelledby="patristic-roots-title">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-dourado">
                    Raízes nos Padres
                  </p>
                  <h2 id="patristic-roots-title" className="mt-0.5 font-garamond text-xl font-medium text-texto">
                    Testemunhos patrísticos relacionados
                  </h2>
                  <p className="text-xs text-texto-terciario">
                    Passagens do corpo das obras dos Padres ligadas à doutrina; não são parte do texto do Catecismo.
                  </p>
                </div>
                {cccConcordance.patristic_roots.results.length > 0 ? (
                  cccConcordance.patristic_roots.results.map(hit => (
                    <SearchResultCard key={hit.chunk_id} hit={hit} query={cccConcordance.themes.join(' ')} />
                  ))
                ) : (
                  <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4 text-xs text-texto-terciario">
                    Nenhuma citação patrística suficientemente segura foi encontrada para este parágrafo.
                  </div>
                )}
              </section>

              {cccConcordance.notices.length > 0 && (
                <div className="space-y-1 rounded-lg border border-fundo-borda bg-fundo-card/60 p-3">
                  {cccConcordance.notices.map(notice => (
                    <p key={`${notice.scope}-${notice.code}`} className="text-[10px] text-texto-terciario">
                      {notice.message}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      )}

      {searchMode === 'catalogo' && hasFocusedCatalog && (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3 border-b border-fundo-borda pb-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
                Resultado da consulta
              </p>
              <h2 className="mt-1 font-garamond text-xl font-medium text-texto">
                Acervo filtrado
              </h2>
              <p className="text-xs text-texto-terciario">
                Mostrando até 80 resultados para manter a leitura rápida.
              </p>
            </div>
            <span className="rounded-full bg-dourado/15 px-2.5 py-1 text-xs font-medium text-dourado">
              {visibleBooks.length.toLocaleString('pt-BR')}
            </span>
          </div>
          {visibleBooks.length > 0 ? (
            <div className="space-y-3">
              {visibleBooks.slice(0, 80).map(book => (
                <BookCard key={book.id} book={book} />
              ))}
            </div>
          ) : (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">
                Nenhuma obra encontrada com estes critérios.
              </p>
            </div>
          )}
        </section>
      )}

      {searchMode === 'catalogo' && !hasFocusedCatalog && (
        <>
          <div className="flex gap-1 rounded-lg border border-fundo-borda bg-fundo-card p-1">
            {SECTION_TABS.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setSection(tab.id)}
                className={`flex-1 rounded-md px-2 py-2 text-xs font-medium leading-tight transition-colors ${
                  section === tab.id
                    ? 'bg-dourado/15 text-dourado'
                    : 'text-texto-terciario hover:text-texto-secundario'
                }`}
              >
                <span className="block">{tab.label}</span>
                <span className={`mt-0.5 inline-block rounded-full px-1.5 py-0.5 font-mono text-[10px] ${
                  section === tab.id ? 'bg-dourado/15 text-dourado' : 'bg-fundo text-texto-terciario'
                }`}>
                  {sectionCount[tab.id].toLocaleString('pt-BR')}
                </span>
              </button>
            ))}
          </div>

          {section === 'patristica' && (
            <PatristicaSection patristica={library.patristica} />
          )}
          {section === 'autores' && (
            <AutoresSection catalog={catalog} />
          )}
          {section === 'santos' && (
            <SantosObrasSection entries={library.obras_santos} />
          )}
          {section === 'documentos' && (
            <DocumentosSection documentos={library.documentos} />
          )}
        </>
      )}
    </div>
  )
}


