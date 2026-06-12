'use client'

import { useState } from 'react'
import Link from 'next/link'
import type { Book } from '@/lib/types'
import { groupByCentury } from '@/lib/century'
import { formatLanguage } from '@/lib/language'

// ─── Tipos internos ────────────────────────────────────────────────────────────

interface CouncilGroup {
  name: string
  year: number | null
  totalCount: number
  books: Book[]
}

interface DocGroup {
  title: string
  books: Book[]
}

type CouncilScope = 'ecumenicos' | 'regionais' | 'locais'

// ─── Agrupamentos ─────────────────────────────────────────────────────────────

function groupByCouncil(books: Book[]): CouncilGroup[] {
  const map: Record<string, Book[]> = {}
  for (const book of books) {
    const name = book.canonical_author ?? book.author ?? 'Desconhecido'
    if (!map[name]) map[name] = []
    map[name].push(book)
  }
  return Object.entries(map)
    .map(([name, bks]) => {
      const years = bks.map(b => b.document_year).filter(Boolean) as number[]
      return { name, year: years.length ? Math.min(...years) : null, totalCount: bks.length, books: bks }
    })
    .sort((a, b) => (a.year ?? 9999) - (b.year ?? 9999))
}

function groupByDocument(books: Book[]): DocGroup[] {
  const map: Record<string, Book[]> = {}
  for (const book of books) {
    const key = book.canonical_title ?? book.title
    if (!map[key]) map[key] = []
    map[key].push(book)
  }
  return Object.entries(map).map(([title, bks]) => ({ title, books: bks }))
}

function capitalize(s: string) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s
}

// ─── Ícones inline ─────────────────────────────────────────────────────────────

function ChevronRight() {
  return (
    <svg className="w-3.5 h-3.5 text-texto-terciario shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}

function ChevronLeft() {
  return (
    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
    </svg>
  )
}

function DocIcon() {
  return (
    <svg className="w-4 h-4 text-dourado/50 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
        d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
    </svg>
  )
}

// ─── Lista de concílios (nível 1) ─────────────────────────────────────────────

function CouncilList({
  groups,
  sectionTitle,
  onSelect,
}: {
  groups: CouncilGroup[]
  sectionTitle: string
  onSelect: (g: CouncilGroup) => void
}) {
  if (groups.length === 0) return null
  const centuries = groupByCentury(groups, g => g.year)

  return (
    <div className="space-y-3">
      <p className="px-1 text-xs font-medium uppercase tracking-wider text-texto-terciario">
        {sectionTitle}
      </p>
      {centuries.map(({ label, items }) => (
        <div key={label} className="space-y-1">
          <p className="mb-1 border-b border-fundo-borda px-1 py-0.5 text-xs text-texto-terciario">
            {label}
          </p>
          {items.map(group => (
            <button
              key={group.name}
              onClick={() => onSelect(group)}
              className="flex w-full items-center justify-between rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left transition-colors hover:border-dourado/40 hover:bg-vinho-escuro/10"
            >
              <div className="flex min-w-0 items-baseline gap-2">
                <span className="text-sm font-medium text-texto">{group.name}</span>
                {group.year && (
                  <span className="text-xs text-texto-terciario">({group.year})</span>
                )}
              </div>
              <div className="ml-3 flex shrink-0 items-center gap-2">
                <span className="rounded-full bg-fundo px-2 py-0.5 text-xs text-texto-terciario">
                  {group.totalCount}
                </span>
                <ChevronRight />
              </div>
            </button>
          ))}
        </div>
      ))}
    </div>
  )
}

// ─── Ícone chevron expandir ────────────────────────────────────────────────────

function ChevronDown({ expanded }: { expanded: boolean }) {
  return (
    <svg
      className={`w-3.5 h-3.5 text-texto-terciario shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
      fill="none" viewBox="0 0 24 24" stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
    </svg>
  )
}

// ─── Linha de documento (dentro do detalhe do concílio) ───────────────────────

function DocRow({
  group,
  councilName,
}: {
  group: DocGroup
  councilName: string
}) {
  const [expanded, setExpanded] = useState(false)

  if (group.books.length === 1) {
    const book = group.books[0]
    const lang = capitalize(formatLanguage(book.language) || book.language || '—')
    const hasChunks = (book.chunk_count ?? 0) > 0
    return (
      <Link
        href={`/biblioteca/${book.id}`}
        className="flex items-center justify-between rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 transition-colors hover:border-dourado/40 hover:bg-vinho-escuro/10"
      >
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-medium text-texto leading-snug">{group.title}</p>
          <p className="text-xs text-texto-terciario">{lang}</p>
        </div>
        <div className="ml-3 flex shrink-0 items-center gap-2">
          {hasChunks ? (
            <span className="rounded-full bg-dourado/10 px-2 py-0.5 text-xs text-dourado">
              {book.chunk_count} trechos
            </span>
          ) : (
            <span className="rounded-full bg-fundo px-2 py-0.5 text-xs text-texto-terciario">
              PDF
            </span>
          )}
          <DocIcon />
        </div>
      </Link>
    )
  }

  // Múltiplos idiomas — linha expansível
  return (
    <div className="rounded-lg border border-fundo-borda bg-fundo-card overflow-hidden">
      <button
        onClick={() => setExpanded(v => !v)}
        className="flex w-full items-center justify-between px-4 py-3 text-left transition-colors hover:bg-vinho-escuro/5"
      >
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-medium text-texto leading-snug">{group.title}</p>
          <p className="text-xs text-texto-terciario">{group.books.length} idiomas disponíveis</p>
        </div>
        <div className="ml-3 flex shrink-0 items-center gap-2">
          <span className="rounded-full bg-fundo px-2 py-0.5 text-xs text-texto-terciario">
            {group.books.length}
          </span>
          <ChevronDown expanded={expanded} />
        </div>
      </button>

      {expanded && (
        <div className="border-t border-fundo-borda divide-y divide-fundo-borda/60">
          {group.books.map(book => {
            const lang = capitalize(formatLanguage(book.language) || book.language || '—')
            const hasChunks = (book.chunk_count ?? 0) > 0
            return (
              <Link
                key={book.id}
                href={`/biblioteca/${book.id}`}
                className="flex items-center justify-between px-4 py-3 transition-colors hover:bg-vinho-escuro/5"
              >
                <div className="min-w-0 space-y-0.5">
                  <p className="text-sm text-texto">{lang}</p>
                  {book.edition_label && (
                    <p className="truncate text-xs text-texto-terciario">{book.edition_label}</p>
                  )}
                </div>
                <div className="ml-3 flex shrink-0 items-center gap-2">
                  {hasChunks ? (
                    <span className="rounded-full bg-dourado/10 px-2 py-0.5 text-xs text-dourado">
                      {book.chunk_count} trechos
                    </span>
                  ) : (
                    <span className="rounded-full bg-fundo px-2 py-0.5 text-xs text-texto-terciario">
                      PDF
                    </span>
                  )}
                  <DocIcon />
                </div>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ─── Detalhe do concílio (nível 2) ────────────────────────────────────────────

function CouncilDetail({
  council,
  onBack,
}: {
  council: CouncilGroup
  onBack: () => void
}) {
  const docGroups = groupByDocument(council.books)

  return (
    <div className="space-y-5">

      {/* Cabeçalho com botão voltar */}
      <div className="space-y-1.5">
        <button
          onClick={onBack}
          className="flex items-center gap-1.5 text-xs text-texto-terciario transition-colors hover:text-dourado"
        >
          <ChevronLeft />
          <span>Concílios</span>
        </button>
        <h2 className="font-garamond text-xl font-medium text-texto">
          {council.name}
          {council.year && (
            <span className="ml-2 font-sans text-base font-normal text-texto-terciario">
              ({council.year})
            </span>
          )}
        </h2>
      </div>

      {/* Lista de documentos — layout vertical limpo */}
      <div className="space-y-2">
        <p className="px-0.5 text-xs font-medium uppercase tracking-wider text-texto-terciario">
          Documentos · {docGroups.length}
        </p>
        <div className="space-y-1.5">
          {docGroups.map(dg => (
            <DocRow key={dg.title} group={dg} councilName={council.name} />
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Componente principal ─────────────────────────────────────────────────────

export default function ConciliosSection({ books }: { books: Book[] }) {
  const [detail, setDetail] = useState<CouncilGroup | null>(null)
  const [activeScope, setActiveScope] = useState<CouncilScope>('ecumenicos')

  const ecumenical = books.filter(b => b.is_ecumenical === true)
  const regional   = books.filter(b => b.is_ecumenical === false)
  const local      = books.filter(b => b.is_ecumenical == null)

  const ecGroups  = groupByCouncil(ecumenical)
  const regGroups = groupByCouncil(regional)
  const locGroups = groupByCouncil(local)
  const scopeTabs: { id: CouncilScope; label: string; description: string; groups: CouncilGroup[] }[] = [
    {
      id: 'ecumenicos',
      label: 'Ecumênicos',
      description: 'Concílios reconhecidos como ecumênicos na tradição católica.',
      groups: ecGroups,
    },
    {
      id: 'regionais',
      label: 'Regionais',
      description: 'Concílios e assembleias de alcance regional.',
      groups: regGroups,
    },
    {
      id: 'locais',
      label: 'Locais e Sínodos',
      description: 'Sínodos e concílios locais catalogados.',
      groups: locGroups,
    },
  ]
  const visibleScopeTabs = scopeTabs.filter(tab => tab.id === 'ecumenicos' || tab.groups.length > 0)
  const activeMeta = scopeTabs.find(tab => tab.id === activeScope) ?? scopeTabs[0]

  if (books.length === 0) {
    return (
      <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
        <p className="text-sm text-texto-terciario">Nenhum concílio catalogado ainda.</p>
      </div>
    )
  }

  if (detail) {
    return <CouncilDetail council={detail} onBack={() => setDetail(null)} />
  }

  return (
    <div className="space-y-5">
      <div className="space-y-3">
        <div className="flex flex-wrap gap-2 border-b border-fundo-borda pb-3">
          {visibleScopeTabs.map(tab => {
            const isActive = activeScope === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => {
                  setActiveScope(tab.id)
                  setDetail(null)
                }}
                className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                  isActive
                    ? 'border-dourado/40 bg-dourado/10 text-dourado'
                    : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
                }`}
              >
                {tab.label}
                <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
                  isActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
                }`}>
                  {tab.groups.reduce((sum, group) => sum + group.totalCount, 0)}
                </span>
              </button>
            )
          })}
        </div>

        <div>
          <h3 className="font-garamond text-lg font-medium text-texto">
            Concílios {activeMeta.label}
          </h3>
          <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
            {activeMeta.description}
          </p>
        </div>
      </div>

      <CouncilList groups={activeMeta.groups} sectionTitle="Organizados por século" onSelect={setDetail} />
      {activeMeta.groups.length === 0 && (
        <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
          <p className="text-sm text-texto-terciario">
            Nenhum registro catalogado nesta subdivisão ainda.
          </p>
        </div>
      )}
    </div>
  )
}
