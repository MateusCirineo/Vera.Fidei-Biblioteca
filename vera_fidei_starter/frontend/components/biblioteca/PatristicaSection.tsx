'use client'

import { useState } from 'react'
import type { Book, PatristicTradition, LibraryStructure } from '@/lib/types'
import BookCard from './BookCard'

type TraditionTab = {
  id: PatristicTradition
  label: string
  description: string
}

const TRADITIONS: TraditionTab[] = [
  {
    id: 'grega',
    label: 'Patrística Grega',
    description: 'Fontes primárias em grego',
  },
  {
    id: 'oriental',
    label: 'Patrística Oriental',
    description: 'Siríaco, copta, árabe e outras línguas orientais',
  },
  {
    id: 'latina',
    label: 'Patrística Latina',
    description: 'Fontes primárias latinas — PL e coleções equivalentes',
  },
  {
    id: 'portuguesa',
    label: 'em Português',
    description: 'Traduções, edições vernáculas e materiais de apoio',
  },
]

interface PatristicaSectionProps {
  patristica: LibraryStructure['patristica']
}

export default function PatristicaSection({ patristica }: PatristicaSectionProps) {
  const [active, setActive] = useState<PatristicTradition>('latina')

  const books = patristica[active]

  return (
    <div className="space-y-4">
      {/* Tabs de tradição */}
      <div className="space-y-1">
        {TRADITIONS.map((t) => {
          const count = patristica[t.id].length
          const isActive = active === t.id
          return (
            <button
              key={t.id}
              onClick={() => setActive(t.id)}
              className={`w-full flex items-center justify-between rounded-lg border px-4 py-3 text-left transition-colors ${
                isActive
                  ? 'border-dourado/40 bg-dourado/10'
                  : 'border-fundo-borda bg-fundo-card hover:border-dourado/20'
              }`}
            >
              <div>
                <p
                  className={`text-sm font-medium ${
                    isActive ? 'text-dourado' : 'text-texto'
                  }`}
                >
                  {t.label}
                </p>
                <p className="text-xs text-texto-terciario mt-0.5">
                  {t.description}
                </p>
              </div>
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

      {/* Lista de obras da tradição selecionada */}
      <div>
        <h2 className="font-garamond text-lg font-medium text-texto mb-3">
          {TRADITIONS.find((t) => t.id === active)?.label}
        </h2>

        {books.length === 0 ? (
          <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center">
            <p className="text-sm text-texto-terciario">
              Nenhuma obra catalogada nesta categoria ainda.
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
    </div>
  )
}
