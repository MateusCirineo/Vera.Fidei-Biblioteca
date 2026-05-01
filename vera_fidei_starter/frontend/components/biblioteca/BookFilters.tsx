'use client'

import { formatLanguage } from '@/lib/language'

export interface Filters {
  collection: string
  language: string
  onlyPrimary: boolean
}

interface BookFiltersProps {
  filters: Filters
  collections: string[]
  languages: string[]
  onChange: (filters: Filters) => void
}

export default function BookFilters({
  filters,
  collections,
  languages,
  onChange,
}: BookFiltersProps) {
  return (
    <div className="flex flex-wrap gap-3">
      <select
        value={filters.collection}
        onChange={(e) => onChange({ ...filters, collection: e.target.value })}
        className="rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2 text-sm text-texto focus:border-dourado/60 focus:outline-none"
      >
        <option value="">Todas as coleções</option>
        {collections.map((c) => (
          <option key={c} value={c}>
            {c}
          </option>
        ))}
      </select>

      <select
        value={filters.language}
        onChange={(e) => onChange({ ...filters, language: e.target.value })}
        className="rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2 text-sm text-texto focus:border-dourado/60 focus:outline-none"
      >
        <option value="">Todos os idiomas</option>
        {languages.map((l) => (
          <option key={l} value={l}>
            {formatLanguage(l)}
          </option>
        ))}
      </select>

      <button
        onClick={() =>
          onChange({ ...filters, onlyPrimary: !filters.onlyPrimary })
        }
        className={`flex items-center gap-1.5 rounded-lg border px-3 py-2 text-sm transition-colors ${
          filters.onlyPrimary
            ? 'border-dourado/60 bg-dourado/10 text-dourado'
            : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/30'
        }`}
      >
        <span
          className={`inline-block w-3.5 h-3.5 rounded-sm border ${
            filters.onlyPrimary
              ? 'border-dourado bg-dourado'
              : 'border-texto-terciario'
          }`}
        />
        Só fontes primárias
      </button>
    </div>
  )
}
