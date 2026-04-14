'use client'

import { useState } from 'react'
import type { DocumentType, LibraryStructure } from '@/lib/types'
import BookCard from './BookCard'

type DocTab = {
  id: DocumentType
  label: string
}

const DOC_TYPES: DocTab[] = [
  { id: 'concilio', label: 'Concílios' },
  { id: 'bula', label: 'Bulas' },
  { id: 'enciclica', label: 'Encíclicas' },
  { id: 'constituicao_apostolica', label: 'Constituições Apostólicas' },
  { id: 'carta_apostolica', label: 'Cartas Apostólicas' },
  { id: 'outro', label: 'Outros Documentos' },
]

interface DocumentosSectionProps {
  documentos: LibraryStructure['documentos']
}

export default function DocumentosSection({ documentos }: DocumentosSectionProps) {
  // Iniciar na primeira categoria com conteúdo, se houver
  const firstWithContent =
    DOC_TYPES.find((t) => documentos[t.id].length > 0)?.id ?? 'concilio'
  const [active, setActive] = useState<DocumentType>(firstWithContent)

  const books = documentos[active]
  const totalDocumentos = DOC_TYPES.reduce(
    (acc, t) => acc + documentos[t.id].length,
    0
  )

  return (
    <div className="space-y-4">
      {/* Aviso se ainda não há documentos */}
      {totalDocumentos === 0 && (
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
          <p className="text-sm text-texto-terciario">
            Nenhum documento da Igreja catalogado ainda.
          </p>
          <p className="text-xs text-texto-terciario mt-1">
            Use a coleção <span className="font-mono">CONC</span> para concílios
            ou <span className="font-mono">MAG</span> para documentos do
            magistério ao cadastrar obras.
          </p>
        </div>
      )}

      {/* Tabs de tipo documental */}
      <div className="space-y-1">
        {DOC_TYPES.map((dt) => {
          const count = documentos[dt.id].length
          const isActive = active === dt.id
          return (
            <button
              key={dt.id}
              onClick={() => setActive(dt.id)}
              className={`w-full flex items-center justify-between rounded-lg border px-4 py-3 text-left transition-colors ${
                isActive
                  ? 'border-dourado/40 bg-dourado/10'
                  : 'border-fundo-borda bg-fundo-card hover:border-dourado/20'
              }`}
            >
              <span
                className={`text-sm font-medium ${
                  isActive ? 'text-dourado' : 'text-texto'
                }`}
              >
                {dt.label}
              </span>
              <span
                className={`shrink-0 ml-3 text-xs rounded-full px-2 py-0.5 ${
                  isActive
                    ? 'bg-dourado/20 text-dourado'
                    : 'bg-fundo text-texto-terciario'
                }`}
              >
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* Lista de documentos da categoria selecionada */}
      {totalDocumentos > 0 && (
        <div>
          <h2 className="font-garamond text-lg font-medium text-texto mb-3">
            {DOC_TYPES.find((t) => t.id === active)?.label}
          </h2>

          {books.length === 0 ? (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
              <p className="text-sm text-texto-terciario">
                Nenhum documento nesta categoria.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {books.map((book) => (
                <BookCard key={book.id} book={book} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
