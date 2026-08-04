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
import { searchAcervo, searchBible, getPdfUrl } from '@/lib/api'
import type { AcervoSearchResult } from '@/lib/types'

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
  type SearchMode = 'catalogo' | 'conteudo' | 'biblia'
  const [searchMode, setSearchMode] = useState<SearchMode>('catalogo')
  const [contentQuery, setContentQuery] = useState('')
  const [bibleQuery, setBibleQuery] = useState('')
  const [acervoResults, setAcervoResults] = useState<AcervoSearchResult[]>([])
  const [acervoLoading, setAcervoLoading] = useState(false)
  const [acervoError, setAcervoError] = useState('')
  const [lastAcervoQuery, setLastAcervoQuery] = useState('')
  const contentInputRef = useRef<HTMLInputElement>(null)
  const bibleInputRef = useRef<HTMLInputElement>(null)

  const runContentSearch = useCallback(async (q: string) => {
    const trimmed = q.trim()
    if (!trimmed || trimmed.length < 2) return
    setAcervoLoading(true)
    setAcervoError('')
    setAcervoResults([])
    setLastAcervoQuery(trimmed)
    try {
      const res = await searchAcervo(trimmed, { limit: 20 })
      setAcervoResults(res.results)
      if (res.results.length === 0) setAcervoError('Nenhum trecho encontrado para essa busca.')
    } catch {
      setAcervoError('Erro ao buscar no acervo. Verifique sua conexão.')
    } finally {
      setAcervoLoading(false)
    }
  }, [])

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
    } catch {
      setAcervoError('Erro ao buscar. Verifique o formato da referência.')
    } finally {
      setAcervoLoading(false)
    }
  }, [])

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
        ]).map(mode => (
          <button
            key={mode.id}
            type="button"
            onClick={() => {
              setSearchMode(mode.id)
              setAcervoResults([])
              setAcervoError('')
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
          <div className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="acervo-search">
              Busca semântica no acervo
            </label>
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

          {acervoLoading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-texto-terciario">
              <span className="animate-pulse">Buscando nos trechos do acervo…</span>
            </div>
          )}

          {!acervoLoading && acervoError && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">{acervoError}</p>
            </div>
          )}

          {!acervoLoading && acervoResults.length > 0 && (
            <>
              <p className="text-xs text-texto-terciario">
                {acervoResults.length} trechos encontrados para <span className="font-medium text-texto">&ldquo;{lastAcervoQuery}&rdquo;</span>
              </p>
              <div className="space-y-3">
                {acervoResults.map(hit => (
                  <div key={hit.chunk_id} className="rounded-lg border border-fundo-borda bg-fundo-card p-4 space-y-2">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        {hit.author && (
                          <p className="text-xs font-semibold text-dourado">{hit.author}</p>
                        )}
                        {hit.work_title && (
                          <p className="text-xs text-texto-secundario">{hit.work_title}</p>
                        )}
                        <div className="mt-0.5 flex flex-wrap gap-1.5 text-[10px] text-texto-terciario">
                          {hit.edition_label && <span>{hit.edition_label}</span>}
                          {hit.collection && <span>{hit.collection}</span>}
                          {hit.volume != null && <span>vol. {hit.volume}</span>}
                          {hit.chapter_or_section && <span>{hit.chapter_or_section}</span>}
                          {hit.pdf_page != null && <span>p. {hit.pdf_page}</span>}
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
                      {hit.text}
                    </blockquote>
                    {hit.translation_text && (
                      <p className="border-l-2 border-fundo-borda pl-3 text-xs leading-relaxed text-texto-secundario italic">
                        {hit.translation_text}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </section>
      )}

      {/* ── Catena Patrum (busca por referência bíblica) ── */}
      {searchMode === 'biblia' && (
        <section className="space-y-3">
          <div className="rounded-lg border border-fundo-borda bg-fundo-card/80 p-3">
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-dourado" htmlFor="bible-search">
              Catena Patrum
            </label>
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

          {acervoLoading && (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-texto-terciario">
              <span className="animate-pulse">Consultando os Padres sobre este versículo…</span>
            </div>
          )}

          {!acervoLoading && acervoError && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">{acervoError}</p>
            </div>
          )}

          {!acervoLoading && acervoResults.length > 0 && (
            <>
              <p className="text-xs text-texto-terciario">
                {acervoResults.length} trechos patrísticos sobre <span className="font-medium text-texto">{lastAcervoQuery}</span>
              </p>
              <div className="space-y-3">
                {acervoResults.map(hit => (
                  <div key={hit.chunk_id} className="rounded-lg border border-fundo-borda bg-fundo-card p-4 space-y-2">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        {hit.author && (
                          <p className="text-xs font-semibold text-dourado">{hit.author}</p>
                        )}
                        {hit.work_title && (
                          <p className="text-xs text-texto-secundario">{hit.work_title}</p>
                        )}
                        <div className="mt-0.5 flex flex-wrap gap-1.5 text-[10px] text-texto-terciario">
                          {hit.edition_label && <span>{hit.edition_label}</span>}
                          {hit.collection && <span>{hit.collection}</span>}
                          {hit.volume != null && <span>vol. {hit.volume}</span>}
                          {hit.chapter_or_section && <span>{hit.chapter_or_section}</span>}
                          {hit.pdf_page != null && <span>p. {hit.pdf_page}</span>}
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
                      {hit.text}
                    </blockquote>
                    {hit.translation_text && (
                      <p className="border-l-2 border-fundo-borda pl-3 text-xs leading-relaxed text-texto-secundario italic">
                        {hit.translation_text}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </>
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


