'use client'

import { useState } from 'react'
import type {
  Book,
  LibraryStructure,
  PatristicTradition,
  DocumentType,
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

  const documentos: LibraryStructure['documentos'] = {
    concilio: [],
    bula: [],
    enciclica: [],
    constituicao_apostolica: [],
    carta_apostolica: [],
    outro: [],
  }

  const autorMap: Record<string, Record<string, Book[]>> = {}

  for (const book of books) {
    if (book.library_section === 'documentos') {
      const dt = (book.document_type ?? 'outro') as DocumentType
      if (dt in documentos) {
        documentos[dt].push(book)
      } else {
        documentos.outro.push(book)
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
