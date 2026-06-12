'use client'

import { useState } from 'react'
import type {
  Book,
  LibraryStructure,
  PatristicTradition,
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

function languageParts(language: string | null): string[] {
  return (language ?? '')
    .toLowerCase()
    .replace(/\s+e\s+/g, '+')
    .split(/[+/;,|]/)
    .map(part => part.trim())
    .filter(Boolean)
}

function patristicTraditionsFor(book: Book): PatristicTradition[] {
  const parts = languageParts(book.language)
  const isBilingualGreekPortuguese = parts.includes('grc') && parts.includes('pt')
  const isDidaque = [book.collection, book.title, book.canonical_title]
    .filter(Boolean)
    .join(' ')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .includes('didaque')

  if (isDidaque && isBilingualGreekPortuguese) {
    return ['grega', 'portuguesa']
  }

  return [(book.patristic_tradition ?? 'latina') as PatristicTradition]
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
      for (const trad of patristicTraditionsFor(book)) {
        patristica[trad].push(book)
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

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
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
                <p className="mt-0.5 text-xs text-texto-terciario">
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

      {hasFocusedCatalog && (
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

      {!hasFocusedCatalog && (
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


