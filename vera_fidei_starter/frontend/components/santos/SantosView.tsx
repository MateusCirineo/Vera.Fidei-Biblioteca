'use client'

import Image from 'next/image'
import Link from 'next/link'
import { type ReactNode, useEffect, useMemo, useState } from 'react'
import type { Book, DailyCitationResponse } from '@/lib/types'
import type { CalendarSaint, SaintSource, SaintWorkProfile } from '@/lib/roman-calendar'
import {
  SAINT_WORK_PROFILES,
  normalizeText,
} from '@/lib/roman-calendar'
import { formatLanguage } from '@/lib/language'
import { getDailyCitation, getPdfUrl } from '@/lib/api'
import type { DailySaintPortrait } from '@/lib/saint-portrait'
import IconMedallion from '@/components/ui/IconMedallion'
import SectionHeading from '@/components/ui/SectionHeading'
import SurfaceCard from '@/components/ui/SurfaceCard'

type SantosViewProps = {
  books: Book[]
  today: CalendarSaint
  upcoming: CalendarSaint[]
  portrait: DailySaintPortrait | null
}

type SaintCatalogEntry = SaintWorkProfile & {
  works: Book[]
}

type TabId = 'dia' | 'obras'

type VisualIconName =
  | 'book'
  | 'calendar'
  | 'church'
  | 'info'
  | 'prayer'
  | 'quote'
  | 'search'
  | 'shield'
  | 'source'
  | 'star'

function VisualIcon({ name }: { name: VisualIconName }) {
  const commonProps = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.7,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    focusable: false,
    className: 'h-full w-full',
  }

  if (name === 'book') {
    return (
      <svg {...commonProps}>
        <path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5v-16Z" />
        <path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5v-16Z" />
      </svg>
    )
  }

  if (name === 'calendar') {
    return (
      <svg {...commonProps}>
        <path d="M6.5 2.5v3M17.5 2.5v3M3.5 8.5h17" />
        <rect x="3.5" y="4.5" width="17" height="16" rx="2.5" />
        <path d="M8 12h3M8 16h3M14 12h2M14 16h2" />
      </svg>
    )
  }

  if (name === 'church') {
    return (
      <svg {...commonProps}>
        <path d="M12 2v5M9.5 4.5h5M5 21V10.5L12 7l7 3.5V21M3 21h18" />
        <path d="M9.5 21v-5a2.5 2.5 0 0 1 5 0v5M8 12h.01M16 12h.01" />
      </svg>
    )
  }

  if (name === 'info') {
    return (
      <svg {...commonProps}>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 10.5V17M12 7h.01" />
      </svg>
    )
  }

  if (name === 'prayer') {
    return (
      <svg {...commonProps}>
        <path d="M9.5 3.5c1.3 2.1 1.8 4.1 1.5 6l-2 10M14.5 3.5c-1.3 2.1-1.8 4.1-1.5 6l2 10" />
        <path d="M11 9.5h2M9 19.5h6M7.5 22h9" />
      </svg>
    )
  }

  if (name === 'quote') {
    return (
      <svg {...commonProps}>
        <path d="M9.5 7H6.8A2.8 2.8 0 0 0 4 9.8V13h5.5v4H4" />
        <path d="M20 7h-2.7a2.8 2.8 0 0 0-2.8 2.8V13H20v4h-5.5" />
      </svg>
    )
  }

  if (name === 'search') {
    return (
      <svg {...commonProps}>
        <circle cx="10.5" cy="10.5" r="6.5" />
        <path d="m15.5 15.5 5 5" />
      </svg>
    )
  }

  if (name === 'shield') {
    return (
      <svg {...commonProps}>
        <path d="M12 2.5 19 5v5.5c0 4.6-2.8 8.4-7 11-4.2-2.6-7-6.4-7-11V5l7-2.5Z" />
        <path d="m8.5 12 2.2 2.2 4.8-5" />
      </svg>
    )
  }

  if (name === 'source') {
    return (
      <svg {...commonProps}>
        <path d="M6.5 3.5h8l3 3V20a1.5 1.5 0 0 1-1.5 1.5H6.5A1.5 1.5 0 0 1 5 20V5a1.5 1.5 0 0 1 1.5-1.5Z" />
        <path d="M14.5 3.5V7h3M8.5 11h6M8.5 14.5h6M8.5 18h4" />
      </svg>
    )
  }

  return (
    <svg {...commonProps}>
      <path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9L12 3Z" />
    </svg>
  )
}

function CardTitle({
  children,
  icon,
  className = '',
}: {
  children: ReactNode
  icon: VisualIconName
  className?: string
}) {
  return (
    <div className={`flex items-center gap-3 ${className}`.trim()}>
      <IconMedallion size="sm">
        <VisualIcon name={icon} />
      </IconMedallion>
      <h3 className="font-garamond text-xl font-medium leading-tight text-texto">
        {children}
      </h3>
    </div>
  )
}

const CENTURY_ORDER = [
  'Séc. II',
  'Séc. II-III',
  'Séc. III',
  'Séc. IV',
  'Séc. IV-V',
  'Séc. V',
  'Séc. VI',
  'Séc. XIII',
]

function bookAuthorText(book: Book): string {
  return [
    book.canonical_author,
    book.author,
    book.title,
    book.canonical_title,
  ]
    .filter(Boolean)
    .join(' ')
}

function uniqueBooks(books: Book[]): Book[] {
  return Array.from(new Map(books.map(book => [book.id, book])).values())
}

function worksForAliases(books: Book[], aliases: string[]): Book[] {
  const normalizedAliases = aliases.map(alias => normalizeText(alias)).filter(Boolean)

  if (!normalizedAliases.length) return []

  return uniqueBooks(
    books.filter((book) => {
      const haystack = normalizeText(bookAuthorText(book))
      return normalizedAliases.some(alias => haystack.includes(alias))
    })
  ).sort((a, b) => a.title.localeCompare(b.title, 'pt'))
}

function WorkLink({ book }: { book: Book }) {
  return (
    <Link
      href={`/biblioteca/${book.id}`}
      className="group block min-h-12 rounded-lg border border-dourado/15 bg-black/20 px-3.5 py-3 transition-[border-color,background-color,transform] hover:-translate-y-0.5 hover:border-dourado/40 hover:bg-vinho-escuro/20 focus-visible:border-dourado/50 motion-reduce:transform-none motion-reduce:transition-none"
    >
      <div className="flex items-start justify-between gap-2">
        <p className="font-garamond text-base font-medium leading-snug text-texto">
          {book.title}
        </p>
        {book.is_primary_source && (
          <span className="shrink-0 rounded-full bg-dourado/15 px-2 py-0.5 text-xs font-medium text-dourado">
            Primária
          </span>
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-texto-terciario">
        {book.collection && (
          <span className="rounded bg-fundo-card px-1.5 py-0.5 font-mono">
            {book.collection}
          </span>
        )}
        {book.language && <span>{formatLanguage(book.language)}</span>}
        {book.edition_label && <span>{book.edition_label}</span>}
        {book.chunk_count !== undefined && <span>{book.chunk_count} trechos</span>}
      </div>
    </Link>
  )
}

function SourceLine({ source }: { source: SaintSource }) {
  if (source.url) {
    return (
      <a
        href={source.url}
        target="_blank"
        rel="noreferrer"
        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-dourado/15 bg-black/20 px-3 py-2 text-xs leading-snug text-texto-secundario transition-colors hover:border-dourado/40 hover:text-dourado focus-visible:border-dourado/50"
      >
        <span className="h-3.5 w-3.5 shrink-0 text-dourado/80" aria-hidden="true">
          <VisualIcon name="source" />
        </span>
        {source.label}
      </a>
    )
  }

  return (
    <span className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-fundo-borda bg-black/20 px-3 py-2 text-xs leading-snug text-texto-terciario">
      <span className="h-3.5 w-3.5 shrink-0 text-dourado/60" aria-hidden="true">
        <VisualIcon name="source" />
      </span>
      {source.label}
    </span>
  )
}

export default function SantosView({ books, today, upcoming, portrait }: SantosViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('dia')
  const [selectedSaint, setSelectedSaint] = useState<SaintCatalogEntry | null>(null)
  const [saintQuery, setSaintQuery] = useState('')
  const [dailyCitation, setDailyCitation] = useState<DailyCitationResponse | null>(null)
  const [citationLoading, setCitationLoading] = useState(Boolean(today.name))
  const [portraitVisible, setPortraitVisible] = useState(Boolean(portrait))

  useEffect(() => {
    setPortraitVisible(Boolean(portrait))
  }, [portrait])

  useEffect(() => {
    if (!today.name) return
    getDailyCitation(today.name)
      .then(res => setDailyCitation(res.text ? res : null))
      .catch(() => setDailyCitation(null))
      .finally(() => setCitationLoading(false))
  }, [today.name])

  const saintCatalog = useMemo<SaintCatalogEntry[]>(
    () =>
      SAINT_WORK_PROFILES.map(profile => ({
        ...profile,
        works: worksForAliases(books, profile.aliases),
      })),
    [books]
  )

  const groupedSaints = useMemo(() => {
    const groups = new Map<string, SaintCatalogEntry[]>()

    for (const profile of saintCatalog) {
      if (!groups.has(profile.century)) groups.set(profile.century, [])
      groups.get(profile.century)!.push(profile)
    }

    return Array.from(groups.entries())
      .sort(([a], [b]) => {
        const ai = CENTURY_ORDER.indexOf(a)
        const bi = CENTURY_ORDER.indexOf(b)
        return (ai === -1 ? 99 : ai) - (bi === -1 ? 99 : bi)
      })
      .map(([century, saints]) => ({
        century,
        saints: saints.sort((a, b) => a.name.localeCompare(b.name, 'pt')),
      }))
  }, [saintCatalog])

  const filteredGroupedSaints = useMemo(() => {
    const query = normalizeText(saintQuery)
    if (!query) return groupedSaints

    return groupedSaints
      .map(group => ({
        ...group,
        saints: group.saints.filter(profile =>
          normalizeText([
            profile.name,
            profile.title,
            profile.summary,
            profile.collection,
            profile.century,
          ].join(' ')).includes(query)
        ),
      }))
      .filter(group => group.saints.length > 0)
  }, [groupedSaints, saintQuery])

  const todayWorks = useMemo(
    () => worksForAliases(books, [today.name, ...today.aliases]),
    [books, today]
  )
  const saintsWithWorks = saintCatalog.filter(profile => profile.works.length > 0).length
  const catalogWorkCount = saintCatalog.reduce((sum, profile) => sum + profile.works.length, 0)

  const tabs: { id: TabId; label: string; count?: number }[] = [
    { id: 'dia', label: 'Santo do dia' },
    { id: 'obras', label: 'Santos e obras', count: saintCatalog.length },
  ]

  const hagiography = today.hagiography

  return (
    <div className="space-y-5 sm:space-y-6">
      <div
        className="grid grid-cols-2 gap-1.5 rounded-xl border border-dourado/15 bg-black/25 p-1.5 shadow-[inset_0_1px_rgba(255,255,255,0.02)]"
        role="tablist"
        aria-label="Santos"
      >
        {tabs.map(tab => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            id={`saints-tab-${tab.id}`}
            aria-controls={`saints-panel-${tab.id}`}
            aria-selected={activeTab === tab.id}
            onClick={() => {
              setActiveTab(tab.id)
              if (tab.id === 'dia') setSelectedSaint(null)
            }}
            className={`flex min-h-12 min-w-0 items-center justify-center gap-2 rounded-lg border px-2.5 py-2 text-sm font-medium transition-[border-color,background-color,color,box-shadow] ${
              activeTab === tab.id
                ? 'border-dourado/55 bg-[linear-gradient(145deg,rgba(201,168,76,0.18),rgba(201,168,76,0.07))] text-dourado shadow-[0_8px_22px_rgba(0,0,0,0.2)]'
                : 'border-transparent bg-transparent text-texto-terciario hover:border-dourado/20 hover:bg-white/[0.025] hover:text-texto-secundario'
            }`}
          >
            <span className="h-4 w-4 shrink-0" aria-hidden="true">
              <VisualIcon name={tab.id === 'dia' ? 'calendar' : 'book'} />
            </span>
            <span className="truncate">{tab.label}</span>
            {tab.count !== undefined && (
              <span className="shrink-0 rounded-full border border-dourado/15 bg-black/25 px-2 py-0.5 text-xs text-texto-terciario">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {activeTab === 'dia' && (
        <section
          id="saints-panel-dia"
          role="tabpanel"
          aria-labelledby="saints-tab-dia"
          className="space-y-4 sm:space-y-5"
        >
          <SurfaceCard tone="gold" className="relative min-h-[18rem] overflow-hidden p-4 sm:min-h-[19rem] sm:p-6">
            {portrait && portraitVisible && (
              <>
                <div className="pointer-events-none absolute inset-y-0 right-0 w-[58%] sm:w-[48%]">
                  <Image
                    src={portrait.src}
                    alt={portrait.alt}
                    fill
                    sizes="(max-width: 640px) 58vw, 320px"
                    className="object-cover object-top opacity-80 saturate-[0.88]"
                    onError={() => setPortraitVisible(false)}
                    priority
                  />
                  <div className="absolute inset-0 bg-[linear-gradient(90deg,#171918_0%,rgba(23,25,24,0.82)_22%,rgba(23,23,23,0.04)_78%),linear-gradient(0deg,rgba(12,13,13,0.84),transparent_52%)]" />
                </div>
              </>
            )}

            <div className={`relative z-10 flex items-start gap-3 sm:gap-4 ${portrait && portraitVisible ? 'max-w-[78%] sm:max-w-[68%]' : ''}`}>
              <div className="min-w-14 shrink-0 rounded-lg border border-dourado/35 bg-black/35 px-2.5 py-2 text-center shadow-[inset_0_1px_rgba(255,255,255,0.025)] backdrop-blur-sm sm:px-3">
                <p className="font-mono text-xs text-texto-terciario">
                  {today.dateLabel}
                </p>
                <p className="mt-1 text-xs font-medium text-dourado">
                  Hoje
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-dourado sm:text-xs">
                  {today.rank}
                </p>
                <h2 className="mt-1 font-garamond text-[1.75rem] font-semibold leading-[1.02] text-texto drop-shadow-[0_2px_12px_rgba(0,0,0,0.55)] sm:text-4xl">
                  {today.name}
                </h2>
                <p className="mt-2 text-xs leading-relaxed text-texto-secundario sm:text-sm">
                  {today.summary}
                </p>
              </div>
            </div>

            <div className={`relative z-10 mt-5 rounded-lg border border-dourado/15 bg-black/35 px-3.5 py-3 backdrop-blur-md ${portrait && portraitVisible ? 'max-w-[82%] sm:max-w-[70%]' : ''}`}>
              <div className="flex items-center gap-2">
                <span className="h-4 w-4 shrink-0 text-dourado" aria-hidden="true">
                  <VisualIcon name="book" />
                </span>
                <p className="text-xs text-texto-terciario">Caminho de estudo</p>
              </div>
              <p className="mt-1 font-garamond text-lg leading-snug text-texto">
                {today.theme}
              </p>
            </div>

            <div className="relative z-10 mt-3 rounded-lg border border-dourado/15 bg-black/45 px-3.5 py-3 backdrop-blur-md">
              <div className="flex items-center gap-2">
                <span className="h-4 w-4 shrink-0 text-dourado" aria-hidden="true">
                  <VisualIcon name="source" />
                </span>
                <p className="text-xs text-texto-terciario">Fontes hagiográficas consultadas</p>
              </div>
              <div className="mt-2.5 grid gap-2 sm:grid-cols-2">
                {hagiography.sources.slice(0, 4).map(source => (
                  <SourceLine key={`hero-${source.label}-${source.url ?? 'local'}`} source={source} />
                ))}
              </div>
            </div>
            {portrait && portraitVisible && (
              <a
                href={portrait.sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="relative z-20 ml-auto mt-3 flex min-h-11 w-fit max-w-full items-center rounded-lg border border-white/10 bg-black/55 px-3 py-2 text-right text-[10px] leading-snug text-texto-secundario backdrop-blur-md transition-colors hover:border-dourado/35 hover:text-dourado"
              >
                Imagem: {portrait.sourceLabel}
              </a>
            )}
          </SurfaceCard>

          <article>
            <SurfaceCard className="p-5 sm:p-6">
              <SectionHeading as="h3" eyebrow="Vida do santo">
              {hagiography.storyTitle}
              </SectionHeading>
              <div className="mt-5 space-y-4 border-t border-dourado/10 pt-4">
                {hagiography.history.map(paragraph => (
                  <p key={paragraph} className="text-sm leading-[1.75] text-texto-secundario">
                    {paragraph}
                  </p>
                ))}
              </div>
            </SurfaceCard>
          </article>

          <div className="grid gap-4 sm:grid-cols-2">
            <SurfaceCard className="h-full p-4 sm:p-5">
              <CardTitle icon="shield">
                Testemunho
              </CardTitle>
              <ul className="mt-4 space-y-3 border-t border-dourado/10 pt-4">
                {hagiography.witness.map(item => (
                  <li key={item} className="flex gap-3 text-sm leading-relaxed text-texto-secundario">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-dourado shadow-[0_0_8px_rgba(201,168,76,0.35)]" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </SurfaceCard>

            <SurfaceCard className="h-full p-4 sm:p-5">
              <CardTitle icon="church">
                Devoção na Igreja
              </CardTitle>
              <ul className="mt-4 space-y-3 border-t border-dourado/10 pt-4">
                {hagiography.devotion.map(item => (
                  <li key={item} className="flex gap-3 text-sm leading-relaxed text-texto-secundario">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-dourado shadow-[0_0_8px_rgba(201,168,76,0.35)]" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </SurfaceCard>
          </div>

          <SurfaceCard tone="wine" className="p-5 sm:p-6">
            <CardTitle icon="prayer">
              Oração
            </CardTitle>
            <p className="mt-4 border-l border-dourado/40 pl-4 font-garamond text-lg italic leading-[1.75] text-texto sm:text-xl">
              {hagiography.prayer}
            </p>
            <div className="mt-4 flex flex-wrap gap-2 border-t border-dourado/10 pt-4">
              {hagiography.virtues.map(virtue => (
                <span
                  key={virtue}
                  className="inline-flex min-h-8 items-center rounded-full border border-dourado/25 bg-dourado/10 px-3 py-1 text-xs font-medium text-dourado"
                >
                  {virtue}
                </span>
              ))}
            </div>
          </SurfaceCard>

          <SurfaceCard className="p-4 sm:p-5">
            <div className="mb-4 flex items-start justify-between gap-3 border-b border-dourado/10 pb-4">
              <div className="min-w-0">
                <CardTitle icon="book">
                  Obras ligadas ao santo de hoje
                </CardTitle>
                <p className="mt-2 text-sm leading-relaxed text-texto-secundario">
                  Quando houver obra no acervo, ela aparece aqui com acesso direto.
                </p>
              </div>
              <span className="inline-flex min-h-8 min-w-8 shrink-0 items-center justify-center rounded-full border border-dourado/20 bg-dourado/10 px-2 text-xs font-medium text-dourado">
                {todayWorks.length}
              </span>
            </div>

            {todayWorks.length > 0 ? (
              <div className="space-y-2">
                {todayWorks.slice(0, 6).map(book => (
                  <WorkLink key={book.id} book={book} />
                ))}
              </div>
            ) : (
              <p className="rounded-lg border border-dourado/10 bg-black/20 px-4 py-4 text-sm leading-relaxed text-texto-secundario">
                Ainda não há obra vinculada a este santo no acervo. Quando a Biblioteca
                tiver um autor correspondente, o vínculo aparece automaticamente.
              </p>
            )}
          </SurfaceCard>

          {hagiography.otherCelebrations.length > 0 && (
            <SurfaceCard className="p-4 sm:p-5">
              <CardTitle icon="star">
                Outros santos recordados neste dia
              </CardTitle>
              <div className="mt-4 grid gap-2 border-t border-dourado/10 pt-4 sm:grid-cols-2">
                {hagiography.otherCelebrations.map(name => (
                  <div
                    key={name}
                    className="rounded-lg border border-dourado/10 bg-black/20 px-3.5 py-3 text-sm leading-relaxed text-texto-secundario"
                  >
                    {name}
                  </div>
                ))}
              </div>
            </SurfaceCard>
          )}

          {/* ── Citação do dia do acervo ── */}
          {(citationLoading || dailyCitation?.text) && (
            <SurfaceCard tone="gold" className="p-4 sm:p-5">
              <div className="flex items-center gap-3">
                <IconMedallion size="sm">
                  <VisualIcon name="quote" />
                </IconMedallion>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-dourado">
                  Citação do dia — do acervo verificado
                </p>
              </div>
              {citationLoading && (
                <p className="mt-3 animate-pulse text-sm text-texto-terciario motion-reduce:animate-none">Carregando citação…</p>
              )}
              {!citationLoading && dailyCitation && (
                <>
                  <blockquote className="mt-4 border-l-2 border-dourado/45 pl-4 font-garamond text-lg italic leading-[1.7] text-texto sm:text-xl">
                    {dailyCitation.translation_text ?? dailyCitation.text}
                  </blockquote>
                  {dailyCitation.source_fidelity_label && (
                    <p className="mt-2 inline-flex rounded border border-emerald-700/35 bg-emerald-950/25 px-2 py-1 text-[10px] font-semibold text-emerald-300">
                      {dailyCitation.source_fidelity_label}
                    </p>
                  )}
                  {dailyCitation.translation_text && dailyCitation.language && dailyCitation.language !== 'pt' && (
                    <p className="mt-2 border-l-2 border-fundo-borda pl-3 text-xs text-texto-terciario italic">
                      {dailyCitation.text}
                    </p>
                  )}
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <div>
                      {dailyCitation.author && (
                        <p className="text-sm font-medium text-texto">{dailyCitation.author}</p>
                      )}
                      <div className="flex flex-wrap gap-2 text-xs text-texto-terciario">
                        {dailyCitation.work_title && <span>{dailyCitation.work_title}</span>}
                        {dailyCitation.edition_label && <span>{dailyCitation.edition_label}</span>}
                        {dailyCitation.chapter_or_section && <span>{dailyCitation.chapter_or_section}</span>}
                        {dailyCitation.pdf_page != null && <span>p. {dailyCitation.pdf_page}</span>}
                      </div>
                    </div>
                    {dailyCitation.book_file_id != null && (
                      <Link
                        href={(() => {
                          const params = new URLSearchParams({ file: getPdfUrl(dailyCitation.book_file_id!) })
                          if (dailyCitation.pdf_page != null) params.set('page', String(dailyCitation.pdf_page))
                          if (dailyCitation.text) params.set('quote', dailyCitation.text.replace(/\s+/g, ' ').slice(0, 700))
                          return `/viewer/pdf?${params.toString()}`
                        })()}
                        className="ml-auto inline-flex min-h-11 items-center rounded-lg border border-dourado/30 px-3 py-2 text-xs font-medium text-dourado transition-colors hover:border-dourado/50 hover:bg-dourado/10"
                      >
                        Ver na fonte
                      </Link>
                    )}
                  </div>
                </>
              )}
            </SurfaceCard>
          )}

          <SurfaceCard className="p-4 sm:p-5">
            <CardTitle icon="calendar">
              Próximos dias
            </CardTitle>
            <div className="mt-4 grid gap-2 border-t border-dourado/10 pt-4 sm:grid-cols-2">
              {upcoming.slice(1).map(day => (
                <div
                  key={day.key}
                  className="flex min-h-16 items-start gap-3 rounded-lg border border-dourado/10 bg-black/20 px-3.5 py-3"
                >
                  <span className="mt-0.5 rounded-md border border-dourado/15 bg-dourado/5 px-2 py-1 font-mono text-xs text-dourado">
                    {day.dateLabel}
                  </span>
                  <div>
                    <p className="font-garamond text-base font-medium text-texto">
                      {day.name}
                    </p>
                    <p className="text-xs text-texto-terciario">{day.rank}</p>
                  </div>
                </div>
              ))}
            </div>
          </SurfaceCard>

          <SurfaceCard className="p-4 sm:p-5">
            <CardTitle icon="source">
              Fontes
            </CardTitle>
            <div className="mt-4 grid gap-2 border-t border-dourado/10 pt-4 sm:grid-cols-2">
              {hagiography.sources.map(source => (
                <SourceLine key={`${source.label}-${source.url ?? 'local'}`} source={source} />
              ))}
            </div>
          </SurfaceCard>
        </section>
      )}

      {activeTab === 'obras' && (
        <section
          id="saints-panel-obras"
          role="tabpanel"
          aria-labelledby="saints-tab-obras"
          className="space-y-4 sm:space-y-5"
        >
          {!selectedSaint && (
            <>
              <SurfaceCard tone="gold" className="flex items-start gap-3 p-4 sm:p-5">
                <IconMedallion size="sm" className="mt-0.5">
                  <VisualIcon name="info" />
                </IconMedallion>
                <p className="text-sm leading-relaxed text-texto-secundario">
                  Catálogo hagiológico por século e coleção. Toque no nome do santo
                  para abrir suas obras já presentes no Vera.Fidei.
                </p>
              </SurfaceCard>

              <div className="grid grid-cols-3 gap-2">
                <SurfaceCard className="px-2 py-3 text-center sm:px-3">
                  <p className="font-mono text-base font-semibold text-dourado">{saintCatalog.length}</p>
                  <p className="mt-0.5 text-[11px] leading-tight text-texto-terciario sm:text-xs">santos</p>
                </SurfaceCard>
                <SurfaceCard className="px-2 py-3 text-center sm:px-3">
                  <p className="font-mono text-base font-semibold text-dourado">{saintsWithWorks}</p>
                  <p className="mt-0.5 text-[11px] leading-tight text-texto-terciario sm:text-xs">com obras</p>
                </SurfaceCard>
                <SurfaceCard className="px-2 py-3 text-center sm:px-3">
                  <p className="font-mono text-base font-semibold text-dourado">{catalogWorkCount}</p>
                  <p className="mt-0.5 text-[11px] leading-tight text-texto-terciario sm:text-xs">vínculos</p>
                </SurfaceCard>
              </div>

              <SurfaceCard className="p-3.5 sm:p-4">
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor="saint-search" className="block text-xs font-medium uppercase tracking-wide text-texto-terciario">
                    Buscar santo ou coleção
                  </label>
                  {saintQuery && (
                    <button
                      type="button"
                      onClick={() => setSaintQuery('')}
                      className="inline-flex min-h-11 items-center rounded-lg border border-fundo-borda px-3 py-2 text-xs text-texto-terciario transition-colors hover:border-dourado/30 hover:text-texto"
                    >
                      Limpar
                    </button>
                  )}
                </div>
                <div className="relative mt-2">
                  <span className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-dourado/70" aria-hidden="true">
                    <VisualIcon name="search" />
                  </span>
                  <input
                    id="saint-search"
                    value={saintQuery}
                    onChange={(event) => setSaintQuery(event.target.value)}
                    placeholder="Ex.: Agostinho, PL, PG, Tomás"
                    className="min-h-12 w-full rounded-lg border border-dourado/15 bg-black/25 py-2 pl-10 pr-3 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
                  />
                </div>
              </SurfaceCard>

              {filteredGroupedSaints.map(group => (
                <div key={group.century} className="space-y-3 pt-1">
                  <SectionHeading as="h3">
                    {group.century}
                  </SectionHeading>
                  {group.saints.map(profile => (
                    <button
                      key={profile.name}
                      type="button"
                      onClick={() => setSelectedSaint(profile)}
                      className="group flex min-h-[4.75rem] w-full items-center justify-between gap-3 rounded-xl border border-dourado/15 bg-[linear-gradient(145deg,rgba(27,29,28,0.98),rgba(19,21,21,0.98))] px-4 py-3 text-left shadow-[0_10px_28px_rgba(0,0,0,0.2)] transition-[border-color,background-color,transform] hover:-translate-y-0.5 hover:border-dourado/40 hover:bg-vinho-escuro/20 focus-visible:border-dourado/50 motion-reduce:transform-none motion-reduce:transition-none"
                    >
                      <div className="min-w-0">
                        <p className="text-base font-semibold text-texto">
                          {profile.name}
                        </p>
                        <p className="mt-0.5 text-sm text-texto-terciario">
                          {profile.century}
                        </p>
                      </div>
                      <div className="flex shrink-0 items-center gap-2 text-right">
                        <span className="font-mono text-sm text-texto-terciario">
                          {profile.collection}
                        </span>
                        {profile.works.length > 0 && (
                          <span className="inline-flex min-h-7 min-w-7 items-center justify-center rounded-full border border-dourado/20 bg-dourado/10 px-2 text-xs font-medium text-dourado">
                            {profile.works.length}
                          </span>
                        )}
                        <span className="text-base text-dourado/60 transition-transform group-hover:translate-x-0.5 motion-reduce:transform-none motion-reduce:transition-none" aria-hidden="true">
                          ›
                        </span>
                      </div>
                    </button>
                  ))}
                </div>
              ))}

              {filteredGroupedSaints.length === 0 && (
                <SurfaceCard className="p-6 text-center">
                  <p className="text-sm text-texto-terciario">
                    Nenhum santo encontrado com estes critérios.
                  </p>
                </SurfaceCard>
              )}
            </>
          )}

          {selectedSaint && (
            <article className="space-y-4">
              <button
                type="button"
                onClick={() => setSelectedSaint(null)}
                className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-transparent px-2.5 py-2 text-sm text-texto-secundario transition-colors hover:border-dourado/15 hover:bg-white/[0.025] hover:text-texto"
              >
                <span aria-hidden>←</span>
                Santos e obras
              </button>

              <SurfaceCard tone="gold" className="p-5 sm:p-6">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-garamond text-3xl font-semibold leading-[1.05] text-texto sm:text-4xl">
                      {selectedSaint.name}
                    </h2>
                    <p className="mt-1 text-sm text-dourado">{selectedSaint.title}</p>
                    <p className="mt-1 text-xs text-texto-terciario">
                      {selectedSaint.century} · {selectedSaint.collection}
                    </p>
                    <p className="mt-4 border-t border-dourado/10 pt-4 text-sm leading-[1.7] text-texto-secundario">
                      {selectedSaint.summary}
                    </p>
                  </div>
                  <span className="inline-flex min-h-8 min-w-8 shrink-0 items-center justify-center rounded-full border border-dourado/20 bg-dourado/10 px-2 text-xs font-medium text-dourado">
                    {selectedSaint.works.length}
                  </span>
                </div>
              </SurfaceCard>

              <SurfaceCard className="p-4 sm:p-5">
                <CardTitle icon="book">
                  Obras no Vera.Fidei
                </CardTitle>
                {selectedSaint.works.length > 0 ? (
                  <div className="mt-4 space-y-2 border-t border-dourado/10 pt-4">
                    {selectedSaint.works.map(book => (
                      <WorkLink key={book.id} book={book} />
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 rounded-lg border border-dourado/10 bg-black/20 px-4 py-4 text-sm leading-relaxed text-texto-secundario">
                    Ainda não há obras deste santo cadastradas no acervo. Ele permanece
                    no catálogo hagiológico para manter a organização por século e coleção.
                  </p>
                )}
              </SurfaceCard>
            </article>
          )}
        </section>
      )}
    </div>
  )
}
