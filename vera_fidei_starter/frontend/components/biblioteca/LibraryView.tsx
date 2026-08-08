'use client'

import { useState, useCallback, useRef } from 'react'
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
import { searchAcervo, searchBible, getCccCommentary, getPdfUrl, ApiError, getSearchUsage } from '@/lib/api'
import { getToken } from '@/lib/auth'
import type { AcervoSearchResult, SearchUsageInfo } from '@/lib/types'

function cleanChunkText(text: string): string {
  return text
    .replace(/(\.\s*){4,}/g, ' ')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

type ResultCategory = 'patristica' | 'catecismo' | 'liturgia' | 'documentos' | 'santos' | 'outros'

const CATEGORY_LABELS: Record<ResultCategory, string> = {
  patristica: 'Patrística',
  catecismo: 'Catecismo e Compêndios',
  liturgia: 'Liturgia e Missal',
  documentos: 'Documentos da Igreja',
  santos: 'Obras dos Santos',
  outros: 'Outras fontes',
}

const CATEGORY_SHORT: Record<ResultCategory, string> = {
  patristica: 'Patrística',
  catecismo: 'Catecismo',
  liturgia: 'Liturgia',
  documentos: 'Documentos',
  santos: 'Santos',
  outros: 'Outros',
}

function normStr(s: string | null | undefined): string {
  return (s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')
}

function categorizeResult(hit: AcervoSearchResult): ResultCategory {
  const col = (hit.collection ?? '').trim().toUpperCase()
  const title = normStr(hit.work_title)
  const author = normStr(hit.author)
  const chunkAuthor = normStr(hit.chunk_author)

  // Primary: library_section or patristic_tradition from database
  // (covers ALL patristic works: PL/PG/PO + Paulus PT + English editions)
  if (hit.library_section === 'patristica') return 'patristica'
  if (hit.patristic_tradition) return 'patristica'

  // Fallback: Patrologia collection codes (PL/PG/PO = Latin/Greek/Oriental originals; PT = Paulus Portuguese)
  if (['PL', 'PG', 'PO', 'PT'].includes(col)) return 'patristica'

  if (
    title.includes('catecismo') || title.includes('catechism') ||
    title.includes('compendio') || title.includes('catequese')
  ) return 'catecismo'
  if (
    title.includes('missal') || title.includes('breviario') ||
    title.includes('ritual') || title.includes('liturgia')
  ) return 'liturgia'
  if (
    title.includes('enciclica') || title.includes('constituicao apostolica') ||
    title.includes('concilio') || title.includes('decreto') ||
    title.includes('exortacao apostolica') || title.includes('carta apostolica') ||
    title.includes('motu proprio')
  ) return 'documentos'
  // chunk_author takes precedence over book-level author for saint classification
  const effectiveAuthor = chunkAuthor || author
  if (/\b(santo|santa|sao|beato|beata)\b/.test(effectiveAuthor)) return 'santos'
  return 'outros'
}

function groupByCategory(results: AcervoSearchResult[]): Array<{ category: ResultCategory; hits: AcervoSearchResult[] }> {
  const groups = new Map<ResultCategory, AcervoSearchResult[]>()
  for (const hit of results) {
    const cat = categorizeResult(hit)
    if (!groups.has(cat)) groups.set(cat, [])
    groups.get(cat)!.push(hit)
  }
  const order: ResultCategory[] = ['patristica', 'catecismo', 'liturgia', 'documentos', 'santos', 'outros']
  return order.filter(cat => groups.has(cat)).map(cat => ({ category: cat, hits: groups.get(cat)! }))
}

function SearchResultCard({ hit, query }: { hit: AcervoSearchResult; query: string }) {
  const text = cleanChunkText(hit.text)

  function highlight(str: string) {
    const q = query.trim()
    if (!q) return str
    try {
      const esc = q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
      const parts = str.split(new RegExp(`(${esc})`, 'gi'))
      return (
        <>
          {parts.map((p, i) =>
            p.toLowerCase() === q.toLowerCase()
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
            <p className="text-xs text-texto-secundario">{hit.work_title}</p>
          )}
          <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-[10px] text-texto-terciario">
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
          {hit.book_file_id != null && (
            <Link
              href={`/viewer/pdf?file=${encodeURIComponent(getPdfUrl(hit.book_file_id!))}${hit.pdf_page ? `&page=${hit.pdf_page}` : ''}`}
              className="rounded border border-dourado/30 px-2 py-1 text-[10px] font-medium text-dourado transition-colors hover:bg-dourado/10"
            >
              Abrir PDF
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
      <blockquote className="border-l-2 border-dourado/30 pl-3 text-sm leading-relaxed text-texto">
        {highlight(text)}
      </blockquote>
      {hit.translation_text && (
        <p className="border-l-2 border-fundo-borda pl-3 text-xs leading-relaxed italic text-texto-secundario">
          {highlight(hit.translation_text)}
        </p>
      )}
    </div>
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
  const [bibleQuery, setBibleQuery] = useState('')
  const [acervoResults, setAcervoResults] = useState<AcervoSearchResult[]>([])
  const [patristicResults, setPatristicResults] = useState<AcervoSearchResult[]>([])
  const [acervoLoading, setAcervoLoading] = useState(false)
  const [acervoError, setAcervoError] = useState('')
  const [lastAcervoQuery, setLastAcervoQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<ResultCategory | null>(null)
  const contentInputRef = useRef<HTMLInputElement>(null)
  const bibleInputRef = useRef<HTMLInputElement>(null)
  // ── Catecismo ──
  const [cccInput, setCccInput] = useState('')
  const [cccResults, setCccResults] = useState<AcervoSearchResult[]>([])
  const [cccLoading, setCccLoading] = useState(false)
  const [cccError, setCccError] = useState('')
  const [cccSectionTitle, setCccSectionTitle] = useState('')
  const [cccThemes, setCccThemes] = useState<string[]>([])
  const [lastCccArticle, setLastCccArticle] = useState<number | null>(null)
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

  const runContentSearch = useCallback(async (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || trimmed.length < 2) return
    setAcervoLoading(true)
    setAcervoError('')
    setAcervoResults([])
    setPatristicResults([])
    setLastAcervoQuery(trimmed)
    setCategoryFilter(null)
    try {
      // Run two searches in parallel:
      // 1) General (limit=50) for all categories — counts 1 quota unit
      // 2) Dedicated patristic (limit=500) — no quota consumed (collection='patristica')
      const [generalRes, patRes] = await Promise.all([
        searchAcervo(trimmed, { limit: 50 }),
        searchAcervo(trimmed, { limit: 500, collection: 'patristica' }),
      ])
      setAcervoResults(generalRes.results)
      // Sort patristic by author → work → sequential position for grouped reading
      const sorted = [...patRes.results].sort((a, b) => {
        const da = ((a.chunk_author || a.author) ?? '').toLowerCase()
        const db = ((b.chunk_author || b.author) ?? '').toLowerCase()
        if (da !== db) return da.localeCompare(db, 'pt')
        const wa = (a.work_title ?? '').toLowerCase()
        const wb = (b.work_title ?? '').toLowerCase()
        if (wa !== wb) return wa.localeCompare(wb, 'pt')
        return a.chunk_id - b.chunk_id
      })
      setPatristicResults(sorted)
      if (generalRes.results.length === 0 && patRes.results.length === 0) {
        setAcervoError('Nenhum trecho encontrado para essa busca.')
      }
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setAcervoError('LOGIN_REQUIRED')
      } else if (err instanceof ApiError && err.status === 429) {
        setAcervoError('QUOTA_EXCEEDED')
      } else {
        setAcervoError('Erro ao buscar no acervo. Verifique sua conexão.')
      }
    } finally {
      setAcervoLoading(false)
      void loadSearchUsage()
    }
  }, [loadSearchUsage])

  const runBibleSearch = useCallback(async (ref: string) => {
    const trimmed = ref.trim()
    if (!trimmed) return
    setAcervoLoading(true)
    setAcervoError('')
    setAcervoResults([])
    setLastAcervoQuery(trimmed)
    try {
      const res = await searchBible(trimmed, 20)
      setAcervoResults(res.results)
      if (res.results.length === 0) setAcervoError('Nenhum trecho dos Padres encontrado para essa referência.')
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setAcervoError('LOGIN_REQUIRED')
      } else if (err instanceof ApiError && err.status === 429) {
        setAcervoError('QUOTA_EXCEEDED')
      } else {
        setAcervoError('Erro ao buscar. Verifique o formato da referência.')
      }
    } finally {
      setAcervoLoading(false)
      void loadSearchUsage()
    }
  }, [loadSearchUsage])

  const runCccSearch = useCallback(async (raw: string) => {
    const n = parseInt(raw.trim(), 10)
    if (!n || n < 1 || n > 2865) {
      setCccError('Digite um número de artigo válido entre 1 e 2865.')
      return
    }
    setCccLoading(true)
    setCccError('')
    setCccResults([])
    setCccSectionTitle('')
    setCccThemes([])
    setLastCccArticle(n)
    try {
      const res = await getCccCommentary(n, 12)
      setCccResults(res.results)
      setCccSectionTitle(res.section_title)
      setCccThemes(res.themes.slice(0, 6))
      if (res.results.length === 0) setCccError('Nenhum trecho patrístico encontrado para esse artigo ainda.')
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 401) {
        setCccError('LOGIN_REQUIRED')
      } else if (err instanceof ApiError && err.status === 429) {
        setCccError('QUOTA_EXCEEDED')
      } else {
        setCccError('Erro ao buscar. Tente novamente.')
      }
    } finally {
      setCccLoading(false)
      void loadSearchUsage()
    }
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
          { id: 'conteudo' as const, label: 'Busca no conteúdo', desc: 'Trechos dos Padres' },
          { id: 'biblia' as const, label: 'Catena Patrum', desc: 'Por versículo bíblico' },
          { id: 'catecismo' as const, label: 'Catecismo', desc: 'Por artigo do CCC' },
        ]).map(mode => (
          <button
            key={mode.id}
            type="button"
            onClick={() => {
              setSearchMode(mode.id)
              setAcervoResults([])
              setPatristicResults([])
              setAcervoError('')
              if (mode.id !== 'catalogo') void loadSearchUsage()
            }}
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
            <SearchLoginPrompt mode="Busca no conteúdo" />
          ) : (
          <div className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="acervo-search">
                Busca semântica no acervo
              </label>
              <SearchUsageBadge usage={searchUsage} />
            </div>
            <p className="mb-2 text-xs text-texto-terciario">
              Digite um tema, palavra ou frase para encontrar trechos dos Padres e documentos indexados.
            </p>
            <div className="flex gap-2">
              <input
                ref={contentInputRef}
                id="acervo-search"
                type="search"
                value={contentQuery}
                onChange={e => setContentQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runContentSearch(contentQuery)}
                placeholder="Ex: eucaristia, batismo, Trindade, ressurreição…"
                className="flex-1 rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
                style={{ fontSize: '16px' }}
              />
              <button
                type="button"
                onClick={() => runContentSearch(contentQuery)}
                disabled={acervoLoading || contentQuery.trim().length < 2}
                className="rounded-lg border border-dourado/40 bg-dourado/10 px-4 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/20 disabled:opacity-40"
              >
                {acervoLoading ? 'Buscando…' : 'Buscar'}
              </button>
            </div>
          </div>
          )}

          {isLoggedIn && acervoLoading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-texto-terciario">
              <span className="animate-pulse">Buscando nos trechos do acervo…</span>
            </div>
          )}

          {isLoggedIn && !acervoLoading && acervoError === 'QUOTA_EXCEEDED' && (
            <SearchQuotaPrompt usage={searchUsage} />
          )}

          {isLoggedIn && !acervoLoading && acervoError && acervoError !== 'LOGIN_REQUIRED' && acervoError !== 'QUOTA_EXCEEDED' && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">{acervoError}</p>
            </div>
          )}

          {isLoggedIn && !acervoLoading && (acervoResults.length > 0 || patristicResults.length > 0) && (() => {
            const grouped = groupByCategory(acervoResults)
            // Patrística pill always reflects the dedicated deep search count
            const patCount = patristicResults.length

            // Build patristic author groups for the dedicated patristic view
            const patByAuthor: Array<{ author: string; hits: AcervoSearchResult[] }> = []
            if (categoryFilter === 'patristica') {
              const authorMap = new Map<string, AcervoSearchResult[]>()
              for (const hit of patristicResults) {
                const key = (hit.chunk_author || hit.author || 'Autor desconhecido').trim()
                if (!authorMap.has(key)) authorMap.set(key, [])
                authorMap.get(key)!.push(hit)
              }
              for (const [author, hits] of authorMap) {
                patByAuthor.push({ author, hits })
              }
            }

            const activeGroups = categoryFilter && categoryFilter !== 'patristica'
              ? grouped.filter(g => g.category === categoryFilter)
              : grouped

            const totalDisplay = acervoResults.length

            return (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <p className="text-xs text-texto-terciario">
                    {categoryFilter === 'patristica' ? (
                      <>
                        <span className="font-medium text-texto">{patCount}</span> trechos patrísticos para{' '}
                        <span className="font-medium text-texto">&ldquo;{lastAcervoQuery}&rdquo;</span>
                      </>
                    ) : (
                      <>
                        <span className="font-medium text-texto">{totalDisplay}</span> trechos para{' '}
                        <span className="font-medium text-texto">&ldquo;{lastAcervoQuery}&rdquo;</span>
                        {patCount > 0 && (
                          <span className="ml-1 text-dourado/70">
                            · {patCount} patrísticos disponíveis
                          </span>
                        )}
                      </>
                    )}
                  </p>
                </div>

                {/* Filter pills */}
                <div className="flex flex-wrap gap-1.5">
                  <button
                    type="button"
                    onClick={() => setCategoryFilter(null)}
                    className={`rounded-full border px-3 py-1 text-[10px] font-semibold transition-colors ${
                      categoryFilter === null
                        ? 'border-dourado bg-dourado/15 text-dourado'
                        : 'border-fundo-borda text-texto-terciario hover:border-dourado/30 hover:text-texto'
                    }`}
                  >
                    Tudo · {totalDisplay}
                  </button>
                  {(Object.keys(CATEGORY_SHORT) as ResultCategory[]).map(cat => {
                    const count = cat === 'patristica'
                      ? patCount
                      : (grouped.find(g => g.category === cat)?.hits.length ?? 0)
                    const active = categoryFilter === cat
                    return (
                      <button
                        key={cat}
                        type="button"
                        disabled={count === 0}
                        onClick={() => count > 0 && setCategoryFilter(c => c === cat ? null : cat)}
                        className={`rounded-full border px-3 py-1 text-[10px] font-semibold transition-colors ${
                          active
                            ? 'border-dourado bg-dourado/15 text-dourado'
                            : count > 0
                              ? 'border-fundo-borda text-texto-terciario hover:border-dourado/30 hover:text-texto'
                              : 'cursor-not-allowed border-fundo-borda/30 text-texto-terciario/30'
                        }`}
                      >
                        {CATEGORY_SHORT[cat]} · {count}
                      </button>
                    )
                  })}
                </div>

                {/* Results */}
                {categoryFilter === 'patristica' ? (
                  // Dedicated patristic view: all results grouped by Church Father
                  <div className="space-y-8">
                    {patByAuthor.map(({ author, hits: authorHits }) => (
                      <section key={author}>
                        <div className="mb-3 flex items-center gap-3">
                          <div className="h-px flex-1 bg-fundo-borda" />
                          <span className="flex items-center gap-2 rounded-full border border-dourado/30 bg-dourado/8 px-3 py-1 text-[10px] font-bold text-dourado">
                            {author}
                            <span className="rounded-full bg-dourado/15 px-1.5 py-0.5 text-[9px]">
                              {authorHits.length} {authorHits.length === 1 ? 'trecho' : 'trechos'}
                            </span>
                          </span>
                          <div className="h-px flex-1 bg-fundo-borda" />
                        </div>
                        <div className="space-y-3">
                          {authorHits.map(hit => (
                            <SearchResultCard key={hit.chunk_id} hit={hit} query={lastAcervoQuery} />
                          ))}
                        </div>
                      </section>
                    ))}
                  </div>
                ) : categoryFilter ? (
                  // Other category filter from general search
                  <div className="space-y-3">
                    {(activeGroups[0]?.hits ?? []).map(hit => (
                      <SearchResultCard key={hit.chunk_id} hit={hit} query={lastAcervoQuery} />
                    ))}
                  </div>
                ) : (
                  // No filter: grouped general results
                  <div className="space-y-6">
                    {activeGroups.map(({ category, hits }) => (
                      <section key={category}>
                        <div className="mb-3 flex items-center gap-3">
                          <div className="h-px flex-1 bg-fundo-borda" />
                          <span className="flex items-center gap-2 rounded-full border border-fundo-borda bg-fundo-card px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-texto-terciario">
                            {CATEGORY_LABELS[category]}
                            <span className="rounded-full bg-dourado/10 px-1.5 py-0.5 text-[9px] font-bold text-dourado">
                              {category === 'patristica' ? patCount : hits.length}
                            </span>
                          </span>
                          <div className="h-px flex-1 bg-fundo-borda" />
                        </div>
                        <div className="space-y-3">
                          {hits.map(hit => (
                            <SearchResultCard key={hit.chunk_id} hit={hit} query={lastAcervoQuery} />
                          ))}
                          {category === 'patristica' && patCount > hits.length && (
                            <button
                              type="button"
                              onClick={() => setCategoryFilter('patristica')}
                              className="w-full rounded-lg border border-dourado/30 py-2.5 text-xs font-medium text-dourado transition-colors hover:bg-dourado/10"
                            >
                              Ver todos os {patCount} trechos patrísticos →
                            </button>
                          )}
                        </div>
                      </section>
                    ))}
                  </div>
                )}
              </div>
            )
          })()}
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

      {/* ── Comentário patrístico por artigo do Catecismo ── */}
      {searchMode === 'catecismo' && (
        <section className="space-y-3">
          {!isLoggedIn ? (
            <SearchLoginPrompt mode="Catecismo" />
          ) : (
          <div className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
            <div className="mb-1.5 flex items-center justify-between">
              <label className="block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="ccc-search">
                Comentário patrístico do Catecismo
              </label>
              <SearchUsageBadge usage={searchUsage} />
            </div>
            <p className="mb-2 text-xs text-texto-terciario">
              Digite o número de um artigo do CCC (1–2865) para ver o que os Padres disseram sobre essa doutrina.
            </p>
            <div className="flex gap-2">
              <input
                id="ccc-search"
                type="number"
                min={1}
                max={2865}
                value={cccInput}
                onChange={e => setCccInput(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && runCccSearch(cccInput)}
                placeholder="Ex: 1324  (Eucaristia)  ·  460  (Encarnação)  ·  2759  (Pai-Nosso)"
                className="flex-1 rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
                style={{ fontSize: '16px' }}
              />
              <button
                type="button"
                onClick={() => runCccSearch(cccInput)}
                disabled={cccLoading || !cccInput.trim()}
                className="rounded-lg border border-dourado/40 bg-dourado/10 px-4 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/20 disabled:opacity-40"
              >
                {cccLoading ? 'Buscando…' : 'Buscar'}
              </button>
            </div>
            <p className="mt-1.5 text-[10px] text-texto-terciario">
              Exemplos: 233 (Trindade) · 460 (Encarnação) · 1324 (Eucaristia) · 1422 (Confissão) · 2558 (Oração)
            </p>
          </div>
          )}

          {isLoggedIn && cccLoading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-texto-terciario">
              <span className="animate-pulse">Consultando os Padres sobre este artigo…</span>
            </div>
          )}

          {isLoggedIn && !cccLoading && cccError === 'QUOTA_EXCEEDED' && (
            <SearchQuotaPrompt usage={searchUsage} />
          )}

          {isLoggedIn && !cccLoading && cccError && cccError !== 'LOGIN_REQUIRED' && cccError !== 'QUOTA_EXCEEDED' && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">{cccError}</p>
            </div>
          )}

          {isLoggedIn && !cccLoading && cccSectionTitle && (
            <div className="rounded-lg border border-dourado/20 bg-dourado/5 px-4 py-3">
              <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
                Artigo {lastCccArticle} do CCC
              </p>
              <p className="mt-1 text-sm font-medium text-texto">{cccSectionTitle}</p>
              {cccThemes.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {cccThemes.map(t => (
                    <span key={t} className="rounded-full border border-dourado/20 bg-dourado/5 px-2 py-0.5 text-[10px] text-dourado/80">
                      {t}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )}

          {isLoggedIn && !cccLoading && cccResults.length > 0 && (
            <div className="space-y-3">
              <p className="text-xs text-texto-terciario">
                <span className="font-medium text-texto">{cccResults.length}</span> trechos para o artigo{' '}
                <span className="font-medium text-texto">{lastCccArticle}</span>
              </p>
              {cccResults.map(hit => (
                <SearchResultCard key={hit.chunk_id} hit={hit} query="" />
              ))}
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


