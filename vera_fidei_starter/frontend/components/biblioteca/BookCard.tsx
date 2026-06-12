import Link from 'next/link'
import type { Book } from '@/lib/types'
import { formatLanguage } from '@/lib/language'

function sourceText(book: Book): string {
  return book.edition_label || book.source_label || 'Ficha bibliográfica'
}

function chipClass(kind: 'gold' | 'plain' = 'plain'): string {
  return kind === 'gold'
    ? 'rounded-full border border-dourado/25 bg-dourado/10 px-2 py-0.5 text-dourado'
    : 'rounded-full border border-fundo-borda bg-fundo px-2 py-0.5 text-texto-terciario'
}

function authorityLabel(book: Book): string {
  if (book.is_primary_source) return 'Fonte primária'
  if (book.library_section === 'documentos') return 'Documento'
  return 'Apoio'
}

export default function BookCard({ book }: { book: Book }) {
  const hasPdf = (book.files?.length ?? 0) > 0
  const isIndexed = (book.chunk_count ?? 0) > 0
  const source = sourceText(book)
  const authority = authorityLabel(book)

  return (
    <Link
      href={`/biblioteca/${book.id}`}
      className="group block overflow-hidden rounded-lg border border-fundo-borda bg-fundo-card transition-colors hover:border-dourado/45 hover:bg-vinho-escuro/10"
    >
      <div className="flex">
        <div className={`w-1 shrink-0 ${book.is_primary_source ? 'bg-dourado/70' : 'bg-fundo-borda'}`} />
        <div className="min-w-0 flex-1 px-4 py-3.5">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0 space-y-0.5">
              <p className="font-garamond text-lg font-semibold leading-snug text-texto transition-colors group-hover:text-dourado-claro">
                {book.title}
              </p>
              {book.author && (
                <p className="text-sm leading-snug text-texto-secundario">{book.author}</p>
              )}
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1">
              <span className={`rounded-full px-2.5 py-1 text-xs font-medium ${
                book.is_primary_source
                  ? 'bg-dourado/15 text-dourado'
                  : 'bg-fundo text-texto-terciario'
              }`}>
                {authority}
              </span>
              <span className="hidden text-xs text-texto-terciario transition-colors group-hover:text-dourado sm:inline">
                Abrir ficha
              </span>
            </div>
          </div>

          <div className="mt-2 grid gap-1.5 border-t border-fundo-borda/70 pt-2 text-xs sm:grid-cols-[96px_minmax(0,1fr)]">
            <span className="font-medium uppercase tracking-wide text-texto-terciario">Edição</span>
            <span className="min-w-0 truncate text-texto-secundario">{source}</span>
            {book.document_status && (
              <>
                <span className="font-medium uppercase tracking-wide text-texto-terciario">Status</span>
                <span className="min-w-0 truncate text-texto-secundario">{book.document_status}</span>
              </>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs">
            {book.collection && (
              <span className={`${chipClass('plain')} font-mono`}>
                {book.collection}
              </span>
            )}
            {book.language && <span className={chipClass()}>{formatLanguage(book.language)}</span>}
            {book.document_year && <span className={chipClass()}>{book.document_year}</span>}
            {book.chunk_count !== undefined && (
              <span className={chipClass()}>{book.chunk_count.toLocaleString('pt-BR')} trechos</span>
            )}
            {hasPdf && <span className={chipClass('gold')}>PDF</span>}
            {isIndexed && <span className={chipClass()}>indexada</span>}
          </div>
        </div>
      </div>
    </Link>
  )
}
