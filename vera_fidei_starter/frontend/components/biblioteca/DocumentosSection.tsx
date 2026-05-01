'use client'

import { useState } from 'react'
import type { DocumentType, DocumentosLibrary } from '@/lib/types'
import BookCard from './BookCard'
import ConciliosSection from './ConciliosSection'

// Tipos de documento dentro da aba Papas
const PAPAL_DOC_TYPES: { id: DocumentType; label: string; tabLabel: string }[] = [
  { id: 'enciclica',               label: 'Encíclicas',                tabLabel: 'Encíclicas' },
  { id: 'bula',                    label: 'Bulas Papais',              tabLabel: 'Bulas' },
  { id: 'constituicao_apostolica', label: 'Constituições Apostólicas', tabLabel: 'Const. Apostólicas' },
  { id: 'carta_apostolica',        label: 'Cartas Apostólicas',        tabLabel: 'Cartas Ap.' },
  { id: 'motu_proprio',            label: 'Motu Proprio',              tabLabel: 'Motu Proprio' },
  { id: 'exortacao_apostolica',    label: 'Exortacoes Apostolicas',    tabLabel: 'Exort. Ap.' },
  { id: 'outro',                   label: 'Outros',                    tabLabel: 'Outros' },
]

// Abas fixas de nível superior — sempre visíveis
const TOP_TABS: { id: TopTab; label: string }[] = [
  { id: 'papas',           label: 'Papas' },
  { id: 'concilio',        label: 'Concílios' },
  { id: 'catecismo',       label: 'Catecismo' },
  { id: 'direito_canonico',label: 'Direito Canônico' },
]

type TopTab = 'papas' | 'concilio' | 'catecismo' | 'direito_canonico'

interface DocumentosSectionProps {
  documentos: DocumentosLibrary
}

function EmptyTab({ label }: { label: string }) {
  return (
    <div className="rounded-lg border border-fundo-borda bg-fundo-card p-8 text-center">
      <p className="text-sm text-texto-terciario">Nenhum documento em {label} catalogado ainda.</p>
    </div>
  )
}

export default function DocumentosSection({ documentos }: DocumentosSectionProps) {
  const { byPope, nonPapal } = documentos

  const [activeTab, setActiveTab] = useState<TopTab>('papas')

  // Sub-navegação Papas
  const [activePope, setActivePope] = useState<string>(byPope[0]?.pope ?? '')
  const [activeType, setActiveType] = useState<DocumentType>('enciclica')

  // Contagens por aba
  const papalCount = byPope.reduce((s, e) => s + e.totalCount, 0)
  function tabCount(id: TopTab): number {
    if (id === 'papas') return papalCount
    return (nonPapal[id as DocumentType]?.length ?? 0)
  }

  // Dados da sub-navegação de papas
  const activePopeEntry = byPope.find(e => e.pope === activePope)
  const availablePopeTypes = PAPAL_DOC_TYPES.filter(
    t => (activePopeEntry?.types[t.id]?.length ?? 0) > 0
  )
  const resolvedActiveType = availablePopeTypes.some(t => t.id === activeType)
    ? activeType
    : availablePopeTypes[0]?.id ?? activeType
  const activeTypeBooks = activePopeEntry?.types[resolvedActiveType] ?? []

  return (
    <div className="space-y-4">
      {/* Abas fixas de nível superior */}
      <div className="flex flex-wrap gap-1.5">
        {TOP_TABS.map(tab => {
          const count = tabCount(tab.id)
          const isActive = activeTab === tab.id
          const isEmpty = count === 0
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                isActive
                  ? 'border-dourado/40 bg-dourado/10 text-dourado'
                  : isEmpty
                  ? 'border-fundo-borda/50 bg-fundo-card/50 text-texto-terciario hover:border-dourado/20'
                  : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
              }`}
            >
              {tab.label}
              <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
                isActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
              }`}>
                {count}
              </span>
            </button>
          )
        })}
      </div>

      {/* ── Aba: Papas ─────────────────────────────────────────────────────── */}
      {activeTab === 'papas' && (
        byPope.length === 0 ? <EmptyTab label="Papas" /> : (
          <div className="space-y-4">
            <div className="space-y-1">
              {byPope.map(entry => {
                const isActive = entry.pope === activePope
                return (
                  <button
                    key={entry.pope}
                    onClick={() => setActivePope(entry.pope)}
                    className={`w-full flex items-center justify-between rounded-lg border px-4 py-3 text-left transition-colors ${
                      isActive
                        ? 'border-dourado/40 bg-dourado/10'
                        : 'border-fundo-borda bg-fundo-card hover:border-dourado/20'
                    }`}
                  >
                    <span className={`text-sm font-medium ${isActive ? 'text-dourado' : 'text-texto'}`}>
                      {entry.pope}
                    </span>
                    <span className={`shrink-0 ml-3 text-xs rounded-full px-2 py-0.5 ${
                      isActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
                    }`}>
                      {entry.totalCount}
                    </span>
                  </button>
                )
              })}
            </div>

            {activePopeEntry && availablePopeTypes.length > 0 && (
              <div className="space-y-3">
                {availablePopeTypes.length > 1 && (
                  <div className="flex flex-wrap gap-2">
                    {availablePopeTypes.map(dt => {
                      const count = activePopeEntry.types[dt.id]?.length ?? 0
                      const isTypeActive = resolvedActiveType === dt.id
                      return (
                        <button
                          key={dt.id}
                          onClick={() => setActiveType(dt.id)}
                          className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                            isTypeActive
                              ? 'border-dourado/40 bg-dourado/10 text-dourado'
                              : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
                          }`}
                        >
                          {dt.tabLabel}
                          <span className={`rounded-full px-1.5 py-0.5 text-xs ${
                            isTypeActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
                          }`}>
                            {count}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                )}
                <div>
                  <h2 className="font-garamond text-lg font-medium text-texto mb-3">
                    {PAPAL_DOC_TYPES.find(t => t.id === resolvedActiveType)?.label} — {activePopeEntry.pope}
                  </h2>
                  <div className="space-y-3">
                    {activeTypeBooks.map(book => (
                      <BookCard key={book.id} book={book} />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        )
      )}

      {/* ── Aba: Concílios ─────────────────────────────────────────────────── */}
      {activeTab === 'concilio' && (
        <ConciliosSection books={nonPapal['concilio'] ?? []} />
      )}

      {/* ── Abas: Catecismo / Direito Canônico ─────────────────────────────── */}
      {(activeTab === 'catecismo' || activeTab === 'direito_canonico') && (
        (() => {
          const books = nonPapal[activeTab] ?? []
          const label = TOP_TABS.find(t => t.id === activeTab)!.label
          if (books.length === 0) return <EmptyTab label={label} />
          return (
            <div>
              <h2 className="font-garamond text-lg font-medium text-texto mb-3">{label}</h2>
              <div className="space-y-3">
                {books.map(book => <BookCard key={book.id} book={book} />)}
              </div>
            </div>
          )
        })()
      )}
    </div>
  )
}
