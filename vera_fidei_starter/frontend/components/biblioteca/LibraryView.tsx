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

// ─── Organização do acervo ────────────────────────────────────────────────────

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

  for (const book of books) {
    if (book.library_section === 'documentos') {
      const dt = (book.document_type ?? 'outro') as DocumentType
      // Concílios, Catecismo e Direito Canônico são documentos da Igreja, não de um papa específico
      const NON_PAPAL_TYPES: DocumentType[] = ['concilio', 'catecismo', 'direito_canonico']
      if (!NON_PAPAL_TYPES.includes(dt) && book.pope) {
        const popeName = book.pope
        if (!popeMap[popeName]) popeMap[popeName] = []
        popeMap[popeName].push(book)
      } else {
        if (!nonPapalMap[dt]) nonPapalMap[dt] = []
        nonPapalMap[dt]!.push(book)
      }
    } else {
      // Patrística (seção padrão)
      const trad = (book.patristic_tradition ?? 'latina') as PatristicTradition
      patristica[trad].push(book)

      // Organizar por autor (todos os patrísticos, não documentos)
      const author = book.canonical_author ?? book.author ?? 'Anônimo'
      const title = book.canonical_title ?? book.title
      if (!autorMap[author]) autorMap[author] = {}
      if (!autorMap[author][title]) autorMap[author][title] = []
      autorMap[author][title].push(book)
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

  const obras_por_autor: AuthorEntry[] = Object.entries(autorMap)
    .sort(([a], [b]) => a.localeCompare(b, 'pt'))
    .map(([author, works]) => ({
      author,
      works: Object.entries(works)
        .sort(([a], [b]) => a.localeCompare(b, 'pt'))
        .map(([title, bks]) => ({ title, books: bks })),
    }))

  return { patristica, obras_por_autor, documentos }
}

// ─── Seções principais ────────────────────────────────────────────────────────

type Section = 'patristica' | 'autores' | 'documentos'

const SECTION_TABS: { id: Section; label: string; sub?: string }[] = [
  { id: 'patristica', label: 'Biblioteca Patrística' },
  { id: 'autores', label: 'Obras dos Padres' },
  { id: 'documentos', label: 'Documentos da Igreja' },
]

// ─── Componente principal ─────────────────────────────────────────────────────

export default function LibraryView({
  books,
  catalog,
}: {
  books: Book[]
  catalog: AuthorCatalogEntry[]
}) {
  const [section, setSection] = useState<Section>('patristica')
  const library = organizeLibrary(books)

  return (
    <div className="space-y-5">
      {/* Tabs de seção */}
      <div className="flex gap-1 rounded-xl border border-fundo-borda bg-fundo-card p-1">
        {SECTION_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setSection(tab.id)}
            className={`flex-1 rounded-lg px-2 py-2 text-xs font-medium transition-colors leading-tight ${
              section === tab.id
                ? 'bg-dourado/15 text-dourado'
                : 'text-texto-terciario hover:text-texto-secundario'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Conteúdo da seção ativa */}
      {section === 'patristica' && (
        <PatristicaSection patristica={library.patristica} />
      )}
      {section === 'autores' && (
        <AutoresSection catalog={catalog} />
      )}
      {section === 'documentos' && (
        <DocumentosSection documentos={library.documentos} />
      )}
    </div>
  )
}
