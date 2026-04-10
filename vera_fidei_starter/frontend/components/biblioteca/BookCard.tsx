import Link from 'next/link'
import type { Book } from '@/lib/types'

export default function BookCard({ book }: { book: Book }) {
  return (
    <Link
      href={`/biblioteca/${book.id}`}
      className="block rounded-lg border border-fundo-borda bg-fundo-card p-4 transition-colors hover:border-dourado/40 hover:bg-vinho-escuro/20"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 space-y-0.5">
          <p className="font-garamond text-base font-medium text-texto leading-snug">
            {book.title}
          </p>
          {book.author && (
            <p className="text-sm text-texto-secundario">{book.author}</p>
          )}
        </div>
        {book.is_primary_source && (
          <span className="shrink-0 rounded-full bg-dourado/15 px-2 py-0.5 text-xs font-medium text-dourado">
            Primária
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-texto-terciario">
        {book.collection && (
          <span className="rounded bg-fundo px-1.5 py-0.5 font-mono">
            {book.collection}
          </span>
        )}
        {book.language && <span>{book.language}</span>}
        {book.chunk_count !== undefined && (
          <span>{book.chunk_count} trechos</span>
        )}
      </div>
    </Link>
  )
}
