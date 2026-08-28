'use client'

import { type KeyboardEvent, type ReactNode, useMemo, useState } from 'react'
import FavoriteButton from '@/components/favorites/FavoriteButton'
import PrayerCategoryIcon from '@/components/oracoes/PrayerCategoryIcon'
import IconMedallion from '@/components/ui/IconMedallion'
import SurfaceCard from '@/components/ui/SurfaceCard'
import { searchPrayerGroups } from '@/lib/prayer-search'

type PrayerVersion = {
  lang: 'Português' | 'Latim' | 'Inglês'
  text: string
}

type PrayerItem = {
  id: string
  title: string
  modified?: string
  source?: string
  versions: PrayerVersion[]
  note?: string
}

type PrayerGroup = {
  title: string
  description: string
  code: string
  items: PrayerItem[]
}

interface OracoesViewProps {
  groups: PrayerGroup[]
  source: string
  sourceUrl?: string
  latestModified?: string
  isFallback: boolean
  initialGroupCode?: string
  initialPrayerId?: string
}

type PrayerIconName =
  | 'back'
  | 'book'
  | 'candle'
  | 'chalice'
  | 'chevron'
  | 'cross'
  | 'document'
  | 'dove'
  | 'globe'
  | 'lily'
  | 'mary'
  | 'music'
  | 'prayer'
  | 'search'
  | 'close'
  | 'scroll'
  | 'star'
  | 'sun'

function LineIcon({ name, className = '' }: { name: PrayerIconName; className?: string }) {
  const common = {
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    className,
    'aria-hidden': true,
    focusable: false,
  }

  switch (name) {
    case 'back':
      return <svg {...common}><path d="m14.5 5-7 7 7 7" /></svg>
    case 'book':
      return (
        <svg {...common}>
          <path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v17H7.5A3.5 3.5 0 0 0 4 22V5.5Z" />
          <path d="M20 5.5A3.5 3.5 0 0 0 16.5 2H13v17h3.5A3.5 3.5 0 0 1 20 22V5.5Z" />
        </svg>
      )
    case 'candle':
      return (
        <svg {...common}>
          <path d="M9 22h6M10 18h4v4h-4zM12 3c2 2 2.5 3.7 1.7 5.2A2 2 0 0 1 10 7.1C10 5.8 10.8 4.4 12 3Z" />
          <path d="M10 11h4v7h-4z" />
        </svg>
      )
    case 'chalice':
      return (
        <svg {...common}>
          <path d="M7 3h10l-1 5.5a4 4 0 0 1-8 0L7 3Z" />
          <path d="M12 12.5V19M8.5 21h7M9.5 19h5" />
        </svg>
      )
    case 'chevron':
      return <svg {...common}><path d="m9 5 7 7-7 7" /></svg>
    case 'close':
      return <svg {...common}><path d="m6 6 12 12M18 6 6 18" /></svg>
    case 'cross':
      return (
        <svg {...common}>
          <path d="M12 2v20M7 7h10M5 21h14" />
        </svg>
      )
    case 'document':
      return (
        <svg {...common}>
          <path d="M6 2h8l4 4v16H6V2Z" />
          <path d="M14 2v5h5M9 12h6M9 16h6" />
        </svg>
      )
    case 'dove':
      return (
        <svg {...common}>
          <path d="M3 13c5.5 1.2 8.2-.5 9.5-5.5.7 2.5 2.2 4 4.5 4.5l4-2-2 5c-2.7 3-6 4.5-10 4.5" />
          <path d="m4 17 5-1.5L6 21" />
        </svg>
      )
    case 'globe':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="9" />
          <path d="M3.5 9h17M3.5 15h17M12 3c2.3 2.5 3.4 5.5 3.4 9S14.3 18.5 12 21M12 3C9.7 5.5 8.6 8.5 8.6 12s1.1 6.5 3.4 9" />
        </svg>
      )
    case 'lily':
      return (
        <svg {...common}>
          <path d="M12 22V9" />
          <path d="M12 10C8 9 6 6 7 3c2.7.5 4.3 2.1 5 4.8C12.7 5.1 14.3 3.5 17 3c1 3-1 6-5 7Z" />
          <path d="M12 15c-2.7-.2-4.5-1.2-5.5-3M12 18c2.7-.2 4.5-1.2 5.5-3" />
        </svg>
      )
    case 'mary':
      return (
        <svg {...common}>
          <path d="M12 3c2.7 2.8 4.5 7 4.5 11.5A4.5 4.5 0 0 1 12 19a4.5 4.5 0 0 1-4.5-4.5C7.5 10 9.3 5.8 12 3Z" />
          <path d="M7 21h10M9.5 12c.8.8 1.6 1.2 2.5 1.2s1.7-.4 2.5-1.2" />
        </svg>
      )
    case 'music':
      return (
        <svg {...common}>
          <path d="M9 18V5l10-2v13" />
          <ellipse cx="6.5" cy="18" rx="2.5" ry="2" />
          <ellipse cx="16.5" cy="16" rx="2.5" ry="2" />
        </svg>
      )
    case 'scroll':
      return (
        <svg {...common}>
          <path d="M7 4h11a3 3 0 0 0-3 3v12H7a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3Z" />
          <path d="M15 7a3 3 0 0 1 6 0v1h-6M7 9h5M7 13h5" />
        </svg>
      )
    case 'star':
      return (
        <svg {...common}>
          <path d="m12 2.5 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.1l6.2-.9L12 2.5Z" />
        </svg>
      )
    case 'sun':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" />
        </svg>
      )
    case 'prayer':
      return (
        <svg {...common}>
          <path d="M10.3 21 6.8 10.8A2 2 0 0 1 8.6 8h.2l3.2 8 3.2-8h.2a2 2 0 0 1 1.8 2.8L13.7 21" />
          <path d="M8.8 8V3.8A1.8 1.8 0 0 1 10.6 2v8M15.2 8V3.8A1.8 1.8 0 0 0 13.4 2v8M7 21h10" />
        </svg>
      )
    case 'search':
      return (
        <svg {...common}>
          <circle cx="10.8" cy="10.8" r="6.8" />
          <path d="m16 16 4.5 4.5" />
        </svg>
      )
  }
}

function BackButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="-ml-2 mb-2 inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 text-xs font-medium text-texto-terciario transition-colors hover:bg-dourado/5 hover:text-dourado focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dourado/50"
    >
      <LineIcon name="back" className="h-4 w-4" />
      {children}
    </button>
  )
}

function PrayerDetail({ group, item }: { group: PrayerGroup; item: PrayerItem }) {
  const [selectedLang, setSelectedLang] = useState<PrayerVersion['lang']>(
    item.versions[0]?.lang ?? 'Português'
  )
  const selectedVersion = item.versions.find(version => version.lang === selectedLang) ?? item.versions[0]

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2" role="group" aria-label={item.title}>
          {item.versions.map(version => {
            const isActive = selectedLang === version.lang
            return (
              <button
                key={version.lang}
                type="button"
                aria-pressed={isActive}
                onClick={() => setSelectedLang(version.lang)}
                className={`inline-flex min-h-11 items-center gap-2 rounded-full border px-3.5 py-2 text-xs font-semibold transition-[border-color,background-color,color,transform] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dourado/50 active:scale-[0.98] ${
                  isActive
                    ? 'border-dourado/50 bg-dourado/15 text-dourado shadow-[inset_0_0_0_1px_rgba(201,168,76,0.08)]'
                    : 'border-fundo-borda bg-fundo/70 text-texto-terciario hover:border-dourado/30 hover:text-texto'
                }`}
              >
                <LineIcon name="globe" className="h-3.5 w-3.5" />
                {version.lang}
              </button>
            )
          })}
        </div>
        <div className="[&_button]:min-h-11 [&_button]:px-4">
          <FavoriteButton
            payload={{
              kind: 'prayer',
              item_id: item.id,
              title: item.title,
              subtitle: group.title,
              href: `/oracoes?grupo=${encodeURIComponent(group.code)}&oracao=${encodeURIComponent(item.id)}`,
              source: item.source || group.title,
              metadata: { group: group.code },
            }}
            compact
          />
        </div>
      </div>

      <SurfaceCard tone="transparent" className="px-4 py-5 sm:px-5 sm:py-6">
        <p className="whitespace-pre-line font-garamond text-lg leading-[1.75] text-texto sm:text-xl">
          {selectedVersion?.text}
        </p>
      </SurfaceCard>

      <div className="space-y-2 border-t border-dourado/10 pt-3">
        <p className="text-xs leading-relaxed text-texto-terciario">
          {item.source}
          {item.modified ? ` · atualizado em ${item.modified}` : ''}
        </p>
        {item.note && (
          <p className="text-xs leading-relaxed text-texto-terciario">
            {item.note}
          </p>
        )}
      </div>
    </div>
  )
}

export default function OracoesView({
  groups,
  source,
  sourceUrl,
  latestModified,
  isFallback,
  initialGroupCode,
  initialPrayerId,
}: OracoesViewProps) {
  const initialGroup = groups.find(group => group.code === initialGroupCode) ?? null
  const [activeCode, setActiveCode] = useState<string | null>(initialGroup?.code ?? null)
  const [activePrayerId, setActivePrayerId] = useState<string | null>(initialGroup ? (initialPrayerId ?? null) : null)
  const [searchQuery, setSearchQuery] = useState('')
  const activeGroup = groups.find(group => group.code === activeCode) ?? null
  const activePrayer = activeGroup?.items.find(item => item.id === activePrayerId) ?? null

  const totalPrayers = groups.reduce((sum, group) => sum + group.items.length, 0)
  const totalVersions = groups.reduce(
    (sum, group) => sum + group.items.reduce((inner, item) => inner + item.versions.length, 0),
    0
  )

  const languageStats = useMemo(() => {
    const stats = new Map<PrayerVersion['lang'], number>()
    for (const group of groups) {
      for (const item of group.items) {
        for (const version of item.versions) {
          stats.set(version.lang, (stats.get(version.lang) ?? 0) + 1)
        }
      }
    }
    return (['Português', 'Latim', 'Inglês'] as PrayerVersion['lang'][])
      .map(lang => ({ lang, count: stats.get(lang) ?? 0 }))
  }, [groups])

  const searchResults = useMemo(
    () => searchPrayerGroups(groups, searchQuery),
    [groups, searchQuery]
  )
  const hasSearch = searchQuery.trim().length > 0
  const matchedVersionCount = searchResults.reduce(
    (sum, result) => sum + result.matchedLanguages.length,
    0
  )

  function clearSearch() {
    setSearchQuery('')
  }

  function handleSearchKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape' && searchQuery) {
      event.preventDefault()
      clearSearch()
    }
  }

  function openSearchResult(groupCode: string, itemId: string) {
    setActiveCode(groupCode)
    setActivePrayerId(itemId)
    clearSearch()
  }

  return (
    <>
      {!activeGroup && (
        <>
          <section className="mb-5 space-y-4 border-y border-fundo-borda py-5">
            <div>
              <p className="font-garamond text-xl italic text-texto">
                Ora et stude
              </p>
              <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
                Escolha uma categoria para abrir uma tela própria de orações.
              </p>
              <p className="mt-2 text-xs leading-relaxed text-texto-terciario">
                Fonte: {source}
                {latestModified ? ` · atualizado em ${latestModified}` : ''}
                {isFallback ? ' · modo fallback' : ''}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2.5">
              <SurfaceCard tone="gold" className="p-0">
                <div className="flex min-h-24 items-center gap-3 px-3 py-3.5 sm:px-4">
                  <IconMedallion size="md" className="shrink-0">
                    <LineIcon name="prayer" />
                  </IconMedallion>
                  <div className="min-w-0">
                    <p className="font-mono text-2xl font-semibold leading-none text-texto sm:text-3xl">
                      {totalPrayers}
                    </p>
                    <p className="mt-1.5 text-xs text-texto-terciario">orações</p>
                  </div>
                </div>
              </SurfaceCard>
              <SurfaceCard tone="gold" className="p-0">
                <div className="flex min-h-24 items-center gap-3 px-3 py-3.5 sm:px-4">
                  <IconMedallion size="md" className="shrink-0">
                    <LineIcon name="document" />
                  </IconMedallion>
                  <div className="min-w-0">
                    <p className="font-mono text-2xl font-semibold leading-none text-texto sm:text-3xl">
                      {totalVersions}
                    </p>
                    <p className="mt-1.5 text-xs text-texto-terciario">versões</p>
                  </div>
                </div>
              </SurfaceCard>
            </div>

            <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
              {languageStats.map(stat => (
                <span
                  key={stat.lang}
                  className="inline-flex min-h-11 items-center justify-center gap-2 rounded-lg border border-dourado/15 bg-fundo/80 px-3 py-2 text-xs text-texto-terciario"
                >
                  <LineIcon name="globe" className="h-4 w-4 shrink-0 text-dourado" />
                  {stat.lang}: <span className="font-mono font-semibold text-dourado">{stat.count}</span>
                </span>
              ))}
            </div>
          </section>

          <section className="mb-5" aria-labelledby="prayer-search-label">
            <SurfaceCard tone="gold" className="p-3 sm:p-4">
              <label
                id="prayer-search-label"
                htmlFor="prayer-search"
                className="block font-garamond text-lg font-medium text-texto"
              >
                Pesquisar orações
              </label>
              <p id="prayer-search-help" className="mt-1 text-xs leading-relaxed text-texto-terciario">
                Busque pelo título, categoria, fonte, idioma ou por palavras do texto.
              </p>

              <div className="relative mt-3">
                <LineIcon
                  name="search"
                  className="pointer-events-none absolute left-3 top-1/2 h-4.5 w-4.5 -translate-y-1/2 text-dourado"
                />
                <input
                  id="prayer-search"
                  type="search"
                  value={searchQuery}
                  onChange={event => setSearchQuery(event.target.value)}
                  onKeyDown={handleSearchKeyDown}
                  aria-describedby="prayer-search-help prayer-search-status"
                  aria-controls="prayer-search-results"
                  placeholder="Ex.: Eucaristia, Ave Maria, gratia plena"
                  autoComplete="off"
                  className="min-h-12 w-full rounded-lg border border-dourado/25 bg-fundo/80 py-2.5 pl-10 pr-11 text-sm text-texto outline-none transition-[border-color,box-shadow] placeholder:text-texto-terciario/75 focus:border-dourado/55 focus:shadow-[0_0_0_3px_rgba(201,168,76,0.1)]"
                />
                {hasSearch && (
                  <button
                    type="button"
                    onClick={clearSearch}
                    aria-label="Limpar pesquisa de orações"
                    title="Limpar pesquisa (Esc)"
                    className="absolute right-1.5 top-1/2 inline-flex h-9 w-9 -translate-y-1/2 items-center justify-center rounded-md text-texto-terciario transition-colors hover:bg-dourado/10 hover:text-dourado focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dourado/50"
                  >
                    <LineIcon name="close" className="h-4 w-4" />
                  </button>
                )}
              </div>

              <p
                id="prayer-search-status"
                className="mt-2 min-h-5 text-xs text-texto-terciario"
                aria-live="polite"
                aria-atomic="true"
              >
                {hasSearch
                  ? `${searchResults.length} ${searchResults.length === 1 ? 'oração encontrada' : 'orações encontradas'}${matchedVersionCount > 0 ? ` · correspondência em ${matchedVersionCount} ${matchedVersionCount === 1 ? 'versão' : 'versões'}` : ''}`
                  : `${totalPrayers} orações disponíveis`}
              </p>
            </SurfaceCard>

            {hasSearch && (
              <div id="prayer-search-results" className="mt-3" role="region" aria-label="Resultados da pesquisa de orações">
                {searchResults.length > 0 ? (
                  <ul className="space-y-2.5">
                    {searchResults.map(result => (
                      <li key={result.key}>
                        <SurfaceCard interactive className="group p-0">
                          <button
                            type="button"
                            onClick={() => openSearchResult(result.groupCode, result.itemId)}
                            className="grid min-h-[82px] w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 px-3 py-3 text-left outline-none transition-colors focus-visible:bg-dourado/5 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-dourado/50 sm:px-4"
                          >
                            <IconMedallion size="sm" className="shrink-0 self-start sm:self-center">
                              <PrayerCategoryIcon code={result.groupCode} />
                            </IconMedallion>
                            <span className="min-w-0">
                              <span className="block font-garamond text-lg font-medium leading-tight text-texto">
                                {result.itemTitle}
                              </span>
                              <span className="mt-1 block text-xs font-medium text-dourado">
                                {result.groupTitle}
                              </span>
                              {result.excerpt && (
                                <span className="mt-1.5 block text-xs leading-relaxed text-texto-terciario">
                                  {result.excerpt}
                                </span>
                              )}
                              <span className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px] text-texto-terciario">
                                {result.languages.map(language => (
                                  <span
                                    key={language}
                                    className={`rounded-full border px-2 py-0.5 ${result.matchedLanguages.includes(language) ? 'border-dourado/35 bg-dourado/10 text-dourado' : 'border-fundo-borda bg-fundo/60'}`}
                                  >
                                    {language}
                                  </span>
                                ))}
                                {result.source && <span>· {result.source}</span>}
                              </span>
                            </span>
                            <LineIcon
                              name="chevron"
                              className="h-4 w-4 shrink-0 text-dourado/70 transition-transform group-hover:translate-x-0.5"
                            />
                          </button>
                        </SurfaceCard>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <SurfaceCard tone="transparent" className="px-4 py-6 text-center">
                    <IconMedallion size="md" className="mx-auto">
                      <LineIcon name="search" />
                    </IconMedallion>
                    <p className="mt-3 font-garamond text-lg text-texto">
                      Nenhuma oração encontrada
                    </p>
                    <p className="mt-1 text-xs leading-relaxed text-texto-terciario">
                      Tente outra palavra, um idioma, uma categoria ou um trecho da oração.
                    </p>
                    <button
                      type="button"
                      onClick={clearSearch}
                      className="mt-4 inline-flex min-h-10 items-center rounded-md border border-dourado/30 px-3 py-2 text-xs font-medium text-dourado transition-colors hover:bg-dourado/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-dourado/50"
                    >
                      Limpar pesquisa
                    </button>
                  </SurfaceCard>
                )}
              </div>
            )}
          </section>

          <nav className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {groups.map(group => (
              <SurfaceCard key={group.code} interactive className="group p-0">
                <button
                  type="button"
                  onClick={() => {
                    setActiveCode(group.code)
                    setActivePrayerId(null)
                  }}
                  className="grid min-h-[88px] w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-3 px-3 py-3 text-left text-sm text-texto-secundario outline-none transition-colors hover:text-texto focus-visible:bg-dourado/5 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-dourado/50 sm:min-h-[96px] sm:px-4 sm:py-3.5"
                >
                  <IconMedallion size="md" className="shrink-0">
                    <PrayerCategoryIcon code={group.code} />
                  </IconMedallion>
                  <span className="min-w-0 flex-1">
                    <span className="block font-garamond text-lg font-medium leading-tight text-texto">
                      {group.title}
                    </span>
                    <span className="mt-1 block text-xs leading-relaxed text-texto-terciario">
                      {group.description}
                    </span>
                  </span>
                  <span className="flex shrink-0 items-center gap-1.5 self-center">
                    <span className="inline-flex min-w-9 justify-center rounded-full border border-dourado/25 bg-dourado/5 px-2 py-1 font-mono text-xs text-dourado">
                      {group.items.length}
                    </span>
                    <LineIcon
                      name="chevron"
                      className="h-4 w-4 shrink-0 text-dourado/70 transition-transform group-hover:translate-x-0.5"
                    />
                  </span>
                </button>
              </SurfaceCard>
            ))}
          </nav>
        </>
      )}

      {activeGroup && !activePrayer && (
        <section>
          <SurfaceCard tone="gold" className="p-0">
            <div className="border-b border-dourado/15 bg-[linear-gradient(135deg,rgba(201,168,76,0.08),rgba(17,17,17,0.12))] px-4 pb-4 pt-3 sm:px-5">
              <BackButton
                onClick={() => {
                  setActiveCode(null)
                  setActivePrayerId(null)
                }}
              >
                Voltar para categorias
              </BackButton>
              <div className="flex items-start gap-3.5">
                <IconMedallion size="lg" className="shrink-0">
                  <PrayerCategoryIcon code={activeGroup.code} />
                </IconMedallion>
                <div className="min-w-0 flex-1">
                  <p className="font-garamond text-2xl font-medium leading-tight text-texto">
                    {activeGroup.title}
                  </p>
                  <p className="mt-1.5 text-sm leading-relaxed text-texto-secundario">
                    {activeGroup.description}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <span className="rounded-md border border-dourado/20 bg-fundo/70 px-2 py-1 font-mono text-xs text-dourado">
                    {activeGroup.code}
                  </span>
                  <p className="mt-2 text-xs text-texto-terciario">
                    {activeGroup.items.length} textos
                  </p>
                </div>
              </div>
            </div>

            <div className="space-y-2.5 p-3 sm:p-4">
              {activeGroup.items.map((item) => (
                <SurfaceCard key={item.id} tone="transparent" interactive className="group p-0">
                  <button
                    type="button"
                    onClick={() => setActivePrayerId(item.id)}
                    className="flex min-h-16 w-full items-center gap-3 px-3 py-2.5 text-left outline-none transition-colors focus-visible:bg-dourado/5 focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-dourado/50"
                  >
                    <IconMedallion size="sm" className="shrink-0">
                      <LineIcon name="document" />
                    </IconMedallion>
                    <span className="min-w-0 flex-1">
                      <span className="block font-garamond text-base font-medium leading-snug text-texto sm:text-lg">
                        {item.title}
                      </span>
                      <span className="mt-1 block text-xs text-texto-terciario">
                        {item.versions.map(version => version.lang).join(' / ')}
                      </span>
                    </span>
                    <LineIcon
                      name="chevron"
                      className="h-4 w-4 shrink-0 text-dourado/70 transition-transform group-hover:translate-x-0.5"
                    />
                  </button>
                </SurfaceCard>
              ))}
            </div>
          </SurfaceCard>
        </section>
      )}

      {activeGroup && activePrayer && (
        <section>
          <SurfaceCard tone="gold" className="p-0">
            <div className="border-b border-dourado/15 bg-[linear-gradient(135deg,rgba(201,168,76,0.08),rgba(17,17,17,0.12))] px-4 pb-4 pt-3 sm:px-5">
              <BackButton onClick={() => setActivePrayerId(null)}>
                Voltar para {activeGroup.title}
              </BackButton>
              <div className="flex items-start gap-3.5">
                <IconMedallion size="lg" className="shrink-0">
                  <PrayerCategoryIcon code={activeGroup.code} />
                </IconMedallion>
                <div className="min-w-0 flex-1">
                  <p className="font-garamond text-2xl font-medium leading-tight text-texto sm:text-3xl">
                    {activePrayer.title}
                  </p>
                  <p className="mt-1.5 text-sm text-texto-secundario">
                    {activeGroup.title}
                  </p>
                </div>
              </div>
            </div>
            <div className="p-4 sm:p-5">
              <PrayerDetail group={activeGroup} item={activePrayer} />
            </div>
          </SurfaceCard>
        </section>
      )}

      {sourceUrl && (
        <p className="mt-5 text-center text-xs leading-relaxed text-texto-terciario">
          Acervo externo consultado em cache pelo Vera.Fidei: {sourceUrl}
        </p>
      )}
    </>
  )
}
