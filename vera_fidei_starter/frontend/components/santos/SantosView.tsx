'use client'

import Link from 'next/link'
import { useMemo, useState } from 'react'
import type { Book } from '@/lib/types'
import type { CalendarSaint, SaintSource, SaintWorkProfile } from '@/lib/roman-calendar'
import {
  SAINT_WORK_PROFILES,
  normalizeText,
} from '@/lib/roman-calendar'
import { formatLanguage } from '@/lib/language'

type SantosViewProps = {
  books: Book[]
  today: CalendarSaint
  upcoming: CalendarSaint[]
}

type SaintCatalogEntry = SaintWorkProfile & {
  works: Book[]
}

type TabId = 'dia' | 'obras'

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
      className="block rounded-md border border-fundo-borda bg-fundo px-3 py-2 transition-colors hover:border-dourado/40 hover:bg-vinho-escuro/20"
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
        className="rounded bg-fundo px-2 py-1 text-xs text-texto-secundario underline-offset-4 hover:text-dourado hover:underline"
      >
        {source.label}
      </a>
    )
  }

  return (
    <span className="rounded bg-fundo px-2 py-1 text-xs text-texto-terciario">
      {source.label}
    </span>
  )
}

export default function SantosView({ books, today, upcoming }: SantosViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('dia')
  const [selectedSaint, setSelectedSaint] = useState<SaintCatalogEntry | null>(null)
  const [saintQuery, setSaintQuery] = useState('')

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
    <div className="space-y-5">
      <div className="flex gap-2 overflow-x-auto pb-1">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id)
              if (tab.id === 'dia') setSelectedSaint(null)
            }}
            className={`shrink-0 rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'border-dourado bg-dourado/15 text-dourado'
                : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/30 hover:text-texto'
            }`}
          >
            {tab.label}
            {tab.count !== undefined && (
              <span className="ml-2 rounded-full bg-fundo px-2 py-0.5 text-xs text-texto-terciario">
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {activeTab === 'dia' && (
        <section className="space-y-4">
          <div className="rounded-lg border border-dourado/25 bg-dourado/5 p-5">
            <div className="flex items-start gap-4">
              <div className="shrink-0 rounded-lg border border-dourado/30 bg-fundo-card px-3 py-2 text-center">
                <p className="font-mono text-xs text-texto-terciario">
                  {today.dateLabel}
                </p>
                <p className="mt-1 text-xs font-medium text-dourado">
                  Hoje
                </p>
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
                  {today.rank}
                </p>
                <h2 className="mt-1 font-garamond text-3xl font-semibold leading-tight text-texto">
                  {today.name}
                </h2>
                <p className="mt-2 text-sm leading-relaxed text-texto-secundario">
                  {today.summary}
                </p>
              </div>
            </div>

            <div className="mt-4 rounded-md border border-fundo-borda bg-fundo-card px-3 py-2">
              <p className="text-xs text-texto-terciario">Caminho de estudo</p>
              <p className="font-garamond text-lg text-texto">
                {today.theme}
              </p>
            </div>

            <div className="mt-3 rounded-md border border-fundo-borda bg-fundo-card px-3 py-2">
              <p className="text-xs text-texto-terciario">Fontes hagiográficas consultadas</p>
              <div className="mt-2 flex flex-wrap gap-2">
                {hagiography.sources.slice(0, 4).map(source => (
                  <SourceLine key={`hero-${source.label}-${source.url ?? 'local'}`} source={source} />
                ))}
              </div>
            </div>
          </div>

          <article className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
              Vida do santo
            </p>
            <h3 className="mt-1 font-garamond text-2xl font-medium text-texto">
              {hagiography.storyTitle}
            </h3>
            <div className="mt-3 space-y-3">
              {hagiography.history.map(paragraph => (
                <p key={paragraph} className="text-sm leading-relaxed text-texto-secundario">
                  {paragraph}
                </p>
              ))}
            </div>
          </article>

          <div className="grid gap-4 sm:grid-cols-2">
            <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
              <h3 className="font-garamond text-xl font-medium text-texto">
                Testemunho
              </h3>
              <ul className="mt-3 space-y-2">
                {hagiography.witness.map(item => (
                  <li key={item} className="flex gap-2 text-sm leading-relaxed text-texto-secundario">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-dourado" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
              <h3 className="font-garamond text-xl font-medium text-texto">
                Devoção na Igreja
              </h3>
              <ul className="mt-3 space-y-2">
                {hagiography.devotion.map(item => (
                  <li key={item} className="flex gap-2 text-sm leading-relaxed text-texto-secundario">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-dourado" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <section className="rounded-lg border border-vinho/40 bg-vinho-escuro/20 p-4">
            <h3 className="font-garamond text-xl font-medium text-texto">
              Oração
            </h3>
            <p className="mt-2 font-garamond text-lg italic leading-relaxed text-texto">
              {hagiography.prayer}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {hagiography.virtues.map(virtue => (
                <span
                  key={virtue}
                  className="rounded-full border border-dourado/20 bg-dourado/10 px-2.5 py-1 text-xs font-medium text-dourado"
                >
                  {virtue}
                </span>
              ))}
            </div>
          </section>

          <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div>
                <h3 className="font-garamond text-xl font-medium text-texto">
                  Obras ligadas ao santo de hoje
                </h3>
                <p className="text-sm text-texto-secundario">
                  Quando houver obra no acervo, ela aparece aqui com acesso direto.
                </p>
              </div>
              <span className="rounded-full bg-dourado/15 px-2 py-0.5 text-xs font-medium text-dourado">
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
              <p className="rounded-md border border-fundo-borda bg-fundo px-3 py-3 text-sm leading-relaxed text-texto-secundario">
                Ainda não há obra vinculada a este santo no acervo. Quando a Biblioteca
                tiver um autor correspondente, o vínculo aparece automaticamente.
              </p>
            )}
          </div>

          {hagiography.otherCelebrations.length > 0 && (
            <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
              <h3 className="font-garamond text-xl font-medium text-texto">
                Outros santos recordados neste dia
              </h3>
              <div className="mt-3 space-y-2">
                {hagiography.otherCelebrations.map(name => (
                  <div
                    key={name}
                    className="rounded-md border border-fundo-borda bg-fundo px-3 py-2 text-sm leading-relaxed text-texto-secundario"
                  >
                    {name}
                  </div>
                ))}
              </div>
            </section>
          )}

          <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
            <h3 className="font-garamond text-xl font-medium text-texto">
              Próximos dias
            </h3>
            <div className="mt-3 space-y-2">
              {upcoming.slice(1).map(day => (
                <div
                  key={day.key}
                  className="flex items-start gap-3 rounded-md border border-fundo-borda bg-fundo px-3 py-2"
                >
                  <span className="mt-0.5 rounded bg-fundo-card px-2 py-1 font-mono text-xs text-dourado">
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
          </div>

          <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
            <h3 className="font-garamond text-xl font-medium text-texto">
              Fontes
            </h3>
            <div className="mt-3 flex flex-wrap gap-2">
              {hagiography.sources.map(source => (
                <SourceLine key={`${source.label}-${source.url ?? 'local'}`} source={source} />
              ))}
            </div>
          </section>
        </section>
      )}

      {activeTab === 'obras' && (
        <section className="space-y-4">
          {!selectedSaint && (
            <>
              <div className="flex items-start gap-3 rounded-lg border border-dourado/20 bg-dourado/5 px-4 py-3">
                <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-dourado/20 text-sm font-semibold text-dourado">
                  i
                </span>
                <p className="text-sm leading-relaxed text-texto-secundario">
                  Catálogo hagiológico por século e coleção. Toque no nome do santo
                  para abrir suas obras já presentes no Vera.Fidei.
                </p>
              </div>

              <div className="grid grid-cols-3 gap-2">
                <div className="rounded-md border border-fundo-borda bg-fundo-card px-3 py-2">
                  <p className="font-mono text-sm font-semibold text-texto">{saintCatalog.length}</p>
                  <p className="text-xs text-texto-terciario">santos</p>
                </div>
                <div className="rounded-md border border-fundo-borda bg-fundo-card px-3 py-2">
                  <p className="font-mono text-sm font-semibold text-texto">{saintsWithWorks}</p>
                  <p className="text-xs text-texto-terciario">com obras</p>
                </div>
                <div className="rounded-md border border-fundo-borda bg-fundo-card px-3 py-2">
                  <p className="font-mono text-sm font-semibold text-texto">{catalogWorkCount}</p>
                  <p className="text-xs text-texto-terciario">vínculos</p>
                </div>
              </div>

              <div className="rounded-lg border border-fundo-borda bg-fundo-card p-3">
                <div className="flex items-center justify-between gap-3">
                  <label htmlFor="saint-search" className="block text-xs font-medium uppercase tracking-wide text-texto-terciario">
                    Buscar santo ou coleção
                  </label>
                  {saintQuery && (
                    <button
                      type="button"
                      onClick={() => setSaintQuery('')}
                      className="rounded-md border border-fundo-borda px-2 py-1 text-xs text-texto-terciario transition-colors hover:border-dourado/30 hover:text-texto"
                    >
                      Limpar
                    </button>
                  )}
                </div>
                <input
                  id="saint-search"
                  value={saintQuery}
                  onChange={(event) => setSaintQuery(event.target.value)}
                  placeholder="Ex.: Agostinho, PL, PG, Tomás"
                  className="mt-2 w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto outline-none transition-colors placeholder:text-texto-terciario focus:border-dourado/50"
                />
              </div>

              {filteredGroupedSaints.map(group => (
                <div key={group.century} className="space-y-2">
                  <h2 className="font-garamond text-xl font-medium text-texto">
                    {group.century}
                  </h2>
                  {group.saints.map(profile => (
                    <button
                      key={profile.name}
                      onClick={() => setSelectedSaint(profile)}
                      className="flex w-full items-center justify-between gap-3 rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left transition-colors hover:border-dourado/40 hover:bg-vinho-escuro/20"
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
                          <span className="rounded-full bg-dourado/15 px-2 py-0.5 text-xs font-medium text-dourado">
                            {profile.works.length}
                          </span>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              ))}

              {filteredGroupedSaints.length === 0 && (
                <div className="rounded-lg border border-fundo-borda bg-fundo-card p-6 text-center">
                  <p className="text-sm text-texto-terciario">
                    Nenhum santo encontrado com estes critérios.
                  </p>
                </div>
              )}
            </>
          )}

          {selectedSaint && (
            <article className="space-y-4">
              <button
                onClick={() => setSelectedSaint(null)}
                className="inline-flex items-center gap-2 text-sm text-texto-secundario hover:text-texto"
              >
                <span aria-hidden>←</span>
                Santos e obras
              </button>

              <div className="rounded-lg border border-dourado/25 bg-dourado/5 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="font-garamond text-3xl font-semibold leading-tight text-texto">
                      {selectedSaint.name}
                    </h2>
                    <p className="mt-1 text-sm text-dourado">{selectedSaint.title}</p>
                    <p className="mt-1 text-xs text-texto-terciario">
                      {selectedSaint.century} · {selectedSaint.collection}
                    </p>
                    <p className="mt-3 text-sm leading-relaxed text-texto-secundario">
                      {selectedSaint.summary}
                    </p>
                  </div>
                  <span className="rounded-full bg-dourado/15 px-2 py-0.5 text-xs font-medium text-dourado">
                    {selectedSaint.works.length}
                  </span>
                </div>
              </div>

              <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
                <h3 className="font-garamond text-xl font-medium text-texto">
                  Obras no Vera.Fidei
                </h3>
                {selectedSaint.works.length > 0 ? (
                  <div className="mt-3 space-y-2">
                    {selectedSaint.works.map(book => (
                      <WorkLink key={book.id} book={book} />
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 rounded-md border border-fundo-borda bg-fundo px-3 py-3 text-sm leading-relaxed text-texto-secundario">
                    Ainda não há obras deste santo cadastradas no acervo. Ele permanece
                    no catálogo hagiológico para manter a organização por século e coleção.
                  </p>
                )}
              </section>
            </article>
          )}
        </section>
      )}
    </div>
  )
}
