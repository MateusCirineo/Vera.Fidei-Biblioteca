'use client'

import { getPdfUrl } from '@/lib/api'
import type { Book } from '@/lib/types'

export default function BookDetail({ book }: { book: Book }) {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="space-y-1">
        <div className="flex items-start gap-3 flex-wrap">
          <h1 className="font-garamond text-2xl font-semibold text-texto leading-snug">
            {book.title}
          </h1>
          {book.is_primary_source && (
            <span className="mt-1 shrink-0 rounded-full bg-dourado/15 px-2.5 py-0.5 text-xs font-medium text-dourado">
              Fonte Primária
            </span>
          )}
        </div>
        {book.author && (
          <p className="text-base text-texto-secundario">{book.author}</p>
        )}
      </div>

      {/* Metadata */}
      <div className="grid grid-cols-2 gap-3 rounded-lg border border-fundo-borda bg-fundo-card p-4 text-sm">
        {book.collection && (
          <div>
            <p className="text-xs text-texto-terciario uppercase tracking-wider mb-0.5">
              Coleção
            </p>
            <p className="font-mono text-texto">{book.collection}</p>
          </div>
        )}
        {book.language && (
          <div>
            <p className="text-xs text-texto-terciario uppercase tracking-wider mb-0.5">
              Idioma
            </p>
            <p className="text-texto">{book.language}</p>
          </div>
        )}
        {book.edition_label && (
          <div className="col-span-2">
            <p className="text-xs text-texto-terciario uppercase tracking-wider mb-0.5">
              Edição
            </p>
            <p className="text-texto">{book.edition_label}</p>
          </div>
        )}
        {book.source_label && (
          <div className="col-span-2">
            <p className="text-xs text-texto-terciario uppercase tracking-wider mb-0.5">
              Fonte
            </p>
            <p className="text-texto">{book.source_label}</p>
          </div>
        )}
        {book.chunk_count !== undefined && (
          <div>
            <p className="text-xs text-texto-terciario uppercase tracking-wider mb-0.5">
              Trechos indexados
            </p>
            <p className="text-texto">{book.chunk_count}</p>
          </div>
        )}
      </div>

      {/* Files */}
      {book.files && book.files.length > 0 && (
        <div>
          <h2 className="font-garamond text-xl font-medium text-texto mb-3">
            Arquivos / Edições
          </h2>
          <div className="space-y-3">
            {book.files.map((file) => (
              <div
                key={file.id}
                className="flex items-start justify-between gap-3 rounded-lg border border-fundo-borda bg-fundo-card p-4"
              >
                <div className="min-w-0 space-y-1">
                  <p className="text-sm text-texto truncate">
                    {file.original_filename}
                  </p>
                  <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-texto-terciario">
                    {file.volume_number && (
                      <span>Vol. {file.volume_number}</span>
                    )}
                    {file.editor && <span>Ed. {file.editor}</span>}
                    {file.translator && <span>Trad. {file.translator}</span>}
                    <span>
                      {new Date(file.created_at).toLocaleDateString('pt-BR')}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() =>
                    window.open(
                      getPdfUrl(file.id),
                      '_blank',
                      'noopener,noreferrer'
                    )
                  }
                  className="shrink-0 rounded-md border border-dourado/50 px-3 py-1.5 text-xs font-medium text-dourado transition-colors hover:bg-dourado/10"
                >
                  Abrir PDF
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {(!book.files || book.files.length === 0) && (
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
          <p className="text-sm text-texto-terciario">
            Nenhum arquivo PDF vinculado ainda.
          </p>
        </div>
      )}
    </div>
  )
}
