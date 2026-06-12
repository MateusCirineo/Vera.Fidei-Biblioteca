'use client'

import { type ReactNode, useMemo, useState } from 'react'

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
}

function BackButton({ children, onClick }: { children: ReactNode; onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="mb-2 inline-flex items-center gap-1 text-xs text-texto-terciario transition-colors hover:text-dourado"
    >
      <span aria-hidden="true">‹</span>
      {children}
    </button>
  )
}

function PrayerDetail({ item }: { item: PrayerItem }) {
  const [selectedLang, setSelectedLang] = useState<PrayerVersion['lang']>(
    item.versions[0]?.lang ?? 'Português'
  )
  const selectedVersion = item.versions.find(version => version.lang === selectedLang) ?? item.versions[0]

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {item.versions.map(version => {
          const isActive = selectedLang === version.lang
          return (
            <button
              key={version.lang}
              type="button"
              onClick={() => setSelectedLang(version.lang)}
              className={`rounded-md border px-2.5 py-1 text-xs font-semibold transition-colors ${
                isActive
                  ? 'border-dourado/40 bg-dourado/15 text-dourado'
                  : 'border-fundo-borda bg-fundo-card text-texto-terciario hover:border-dourado/30 hover:text-texto'
              }`}
            >
              {version.lang}
            </button>
          )
        })}
      </div>

      <div className="rounded-md border border-fundo-borda bg-fundo-card px-3 py-3">
        <p className="whitespace-pre-line font-garamond text-lg leading-relaxed text-texto">
          {selectedVersion?.text}
        </p>
      </div>

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
  )
}

export default function OracoesView({
  groups,
  source,
  sourceUrl,
  latestModified,
  isFallback,
}: OracoesViewProps) {
  const [activeCode, setActiveCode] = useState<string | null>(null)
  const [activePrayerId, setActivePrayerId] = useState<string | null>(null)
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

  return (
    <>
      {!activeGroup && (
        <>
          <section className="mb-5 border-y border-fundo-borda py-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
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
              <div className="grid grid-cols-2 gap-2 text-right">
                <div className="rounded-md border border-fundo-borda bg-fundo-card px-3 py-2">
                  <p className="font-mono text-sm font-semibold text-texto">{totalPrayers}</p>
                  <p className="text-xs text-texto-terciario">orações</p>
                </div>
                <div className="rounded-md border border-fundo-borda bg-fundo-card px-3 py-2">
                  <p className="font-mono text-sm font-semibold text-texto">{totalVersions}</p>
                  <p className="text-xs text-texto-terciario">versões</p>
                </div>
              </div>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {languageStats.map(stat => (
                <span key={stat.lang} className="rounded-md border border-fundo-borda bg-fundo px-2.5 py-1 text-xs text-texto-terciario">
                  {stat.lang}: <span className="text-dourado">{stat.count}</span>
                </span>
              ))}
            </div>
          </section>

          <nav className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {groups.map(group => (
              <button
                key={group.code}
                type="button"
                onClick={() => {
                  setActiveCode(group.code)
                  setActivePrayerId(null)
                }}
                className="rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2 text-left text-sm text-texto-secundario transition-colors hover:border-dourado/30 hover:text-texto"
              >
                <span className="flex items-center justify-between gap-3">
                  <span className="truncate">{group.title}</span>
                  <span className="shrink-0 rounded-full bg-fundo px-2 py-0.5 font-mono text-xs text-dourado">
                    {group.items.length}
                  </span>
                </span>
                <span className="mt-0.5 block truncate text-xs text-texto-terciario">
                  {group.description}
                </span>
              </button>
            ))}
          </nav>
        </>
      )}

      {activeGroup && !activePrayer && (
        <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
          <div className="mb-3 flex items-start justify-between gap-3 border-b border-fundo-borda pb-3">
            <div>
              <BackButton
                onClick={() => {
                  setActiveCode(null)
                  setActivePrayerId(null)
                }}
              >
                Voltar para categorias
              </BackButton>
              <p className="font-garamond text-xl font-medium text-texto">
                {activeGroup.title}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
                {activeGroup.description}
              </p>
            </div>
            <div className="shrink-0 text-right">
              <span className="rounded bg-fundo px-2 py-1 font-mono text-xs text-dourado">
                {activeGroup.code}
              </span>
              <p className="mt-1 text-xs text-texto-terciario">
                {activeGroup.items.length} textos
              </p>
            </div>
          </div>

          <div className="space-y-2">
            {activeGroup.items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => setActivePrayerId(item.id)}
                className="flex w-full items-center justify-between rounded-md border border-fundo-borda bg-fundo px-3 py-2 text-left transition-colors hover:border-dourado/30 hover:bg-vinho-escuro/15"
              >
                <span className="font-garamond text-base font-medium text-texto">
                  {item.title}
                </span>
                <span className="ml-3 shrink-0 text-xs text-texto-terciario">
                  {item.versions.map(version => version.lang).join(' / ')}
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      {activeGroup && activePrayer && (
        <section className="rounded-lg border border-fundo-borda bg-fundo-card p-4">
          <div className="mb-3 border-b border-fundo-borda pb-3">
            <BackButton onClick={() => setActivePrayerId(null)}>
              Voltar para {activeGroup.title}
            </BackButton>
            <p className="font-garamond text-2xl font-medium text-texto">
              {activePrayer.title}
            </p>
            <p className="mt-1 text-sm text-texto-secundario">
              {activeGroup.title}
            </p>
          </div>
          <PrayerDetail item={activePrayer} />
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
