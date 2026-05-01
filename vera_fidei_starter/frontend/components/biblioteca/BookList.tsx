'use client'

import { useState } from 'react'
import type { Book } from '@/lib/types'
import BookCard from './BookCard'
import BookFilters, { type Filters } from './BookFilters'

export default function BookList({ books }: { books: Book[] }) {
  const [filters, setFilters] = useState<Filters>({
    collection: '',
    language: '',
    onlyPrimary: false,
  })

  const collections = [
    ...new Set(books.map((b) => b.collection).filter((value): value is string => !!value)),
  ]
  const languages = [
    ...new Set(books.map((b) => b.language).filter((value): value is string => !!value)),
  ]

  const filtered = books.filter((b) => {
    if (filters.collection && b.collection !== filters.collection) return false
    if (filters.language && b.language !== filters.language) return false
    if (filters.onlyPrimary && !b.is_primary_source) return false
    return true
  })

  return (
    <div className="space-y-4">
      <BookFilters
        filters={filters}
        collections={collections}
        languages={languages}
        onChange={setFilters}
      />

      {filtered.length === 0 ? (
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center">
          <p className="text-sm text-texto-terciario">
            Nenhuma obra encontrada com esses filtros.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((book) => (
            <BookCard key={book.id} book={book} />
          ))}
        </div>
      )}
    </div>
  )
}
