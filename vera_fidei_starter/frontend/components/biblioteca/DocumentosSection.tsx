'use client'

import { useState } from 'react'
import type { Book, DocumentType, DocumentosLibrary } from '@/lib/types'
import BookCard from './BookCard'
import ConciliosSection from './ConciliosSection'

type TopTab =
  | 'papas'
  | 'concilio'
  | 'catecismo'
  | 'catequese'
  | 'liturgia'
  | 'doutrina_social'
  | 'direito_canonico'
  | 'teologia'
  | 'linguas_biblicas'
  | 'literatura_crista'

type SubTab = {
  id: string
  label: string
  match: (book: Book) => boolean
}

const PAPAL_DOC_TYPES: { id: DocumentType; label: string; tabLabel: string }[] = [
  { id: 'enciclica', label: 'Encíclicas', tabLabel: 'Encíclicas' },
  { id: 'bula', label: 'Bulas Papais', tabLabel: 'Bulas' },
  { id: 'constituicao_apostolica', label: 'Constituições Apostólicas', tabLabel: 'Const. Apostólicas' },
  { id: 'carta_apostolica', label: 'Cartas Apostólicas', tabLabel: 'Cartas Ap.' },
  { id: 'motu_proprio', label: 'Motu Proprio', tabLabel: 'Motu Proprio' },
  { id: 'exortacao_apostolica', label: 'Exortações Apostólicas', tabLabel: 'Exort. Ap.' },
  { id: 'outro', label: 'Outros', tabLabel: 'Outros' },
]

const TOP_TABS: { id: TopTab; label: string; description: string }[] = [
  { id: 'catecismo', label: 'Catecismo', description: 'Catecismos, compêndios e sínteses doutrinais' },
  { id: 'catequese', label: 'Catequese', description: 'Cursos, iniciação cristã e formação' },
  { id: 'concilio', label: 'Concílios', description: 'Concílios ecumênicos, regionais e sínodos' },
  { id: 'direito_canonico', label: 'Direito Canônico', description: 'Códigos, normas e legislação eclesial' },
  { id: 'doutrina_social', label: 'Doutrina Social', description: 'Documentos sociais e compêndios' },
  { id: 'linguas_biblicas', label: 'Línguas Bíblicas', description: 'Grego, hebraico, latim e apoio linguístico' },
  { id: 'literatura_crista', label: 'Literatura Cristã', description: 'Poesia, obras devocionais e textos cristãos' },
  { id: 'liturgia', label: 'Liturgia', description: 'Missais, rituais, cerimoniais e normas' },
  { id: 'papas', label: 'Papas', description: 'Encíclicas, bulas e documentos pontifícios' },
  { id: 'teologia', label: 'Teologia', description: 'Mariologia, demonologia e estudos teológicos' },
]

const DOCUMENT_TABS: TopTab[] = [
  'catecismo',
  'catequese',
  'liturgia',
  'doutrina_social',
  'direito_canonico',
  'teologia',
  'linguas_biblicas',
  'literatura_crista',
]

function bookText(book: Book): string {
  return [
    book.title,
    book.author,
    book.canonical_author,
    book.canonical_title,
    book.collection,
    book.edition_label,
    book.source_label,
    book.document_status,
  ]
    .filter(Boolean)
    .join(' ')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

const includesAny = (...terms: string[]) => (book: Book) => {
  const text = bookText(book)
  return terms.some(term => text.includes(term))
}

const SUB_TABS: Partial<Record<TopTab, SubTab[]>> = {
  catecismo: [
    { id: 'catecismos', label: 'Catecismos', match: includesAny('catecismo', 'compendio', 'cic', 'youcat') },
  ],
  catequese: [
    { id: 'iniciacao_crista', label: 'Iniciação Cristã', match: includesAny('iniciacao crista', 'cateq-ic', 'eucaristia') },
    { id: 'cursos', label: 'Cursos', match: includesAny('curso', 'catequese') },
  ],
  liturgia: [
    { id: 'missais', label: 'Missais', match: includesAny('missal') },
    { id: 'rituais', label: 'Rituais', match: includesAny('ritual', 'exorcismo', 'lit-exor', 'lit-rit') },
    { id: 'cerimoniais', label: 'Cerimoniais', match: includesAny('cerimonial', 'bencao', 'bencoes', 'lit-cer') },
    { id: 'normas', label: 'Normas', match: includesAny('indulgencia', 'manual') },
  ],
  direito_canonico: [
    { id: 'codigos', label: 'Códigos', match: includesAny('codigo', 'cdc') },
  ],
  teologia: [
    { id: 'tomismo', label: 'Tomismo', match: includesAny('tomas de aquino', 'tomás de aquino', 'aquino', 'summa', 'suma teologica', 'tomismo') },
    { id: 'mariologia', label: 'Mariologia', match: includesAny('maria', 'mariologia', 'teo-mari') },
    { id: 'demonologia', label: 'Demonologia', match: includesAny('demon', 'demonographia', 'teo-demon') },
  ],
  linguas_biblicas: [
    { id: 'grego', label: 'Grego', match: includesAny('grego', 'koine', 'grc') },
    { id: 'hebraico', label: 'Hebraico', match: includesAny('hebraico', 'heb') },
    { id: 'latim', label: 'Latim', match: includesAny('latim', 'lat') },
  ],
  literatura_crista: [
    { id: 'padres_apostolicos', label: 'Padres Apostólicos', match: includesAny('didaque', 'apostolos', 'apostolicos') },
    { id: 'poesia', label: 'Poesia', match: includesAny('psychomachia', 'poesia') },
  ],
}

const FALLBACK_SUBTAB_LABEL: Partial<Record<TopTab, string>> = {
  catecismo: 'Outros catecismos',
  catequese: 'Outras formações',
  liturgia: 'Outros textos litúrgicos',
  direito_canonico: 'Outros documentos',
  teologia: 'Outros estudos',
  linguas_biblicas: 'Outros materiais',
  literatura_crista: 'Outras obras',
}

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

  const [activeTab, setActiveTab] = useState<TopTab | null>(null)
  const [activePope, setActivePope] = useState<string | null>(null)
  const [activeType, setActiveType] = useState<DocumentType>('enciclica')
  const [activeSubTabs, setActiveSubTabs] = useState<Partial<Record<TopTab, string>>>({})

  const papalCount = byPope.reduce((sum, entry) => sum + entry.totalCount, 0)
  function tabCount(id: TopTab): number {
    if (id === 'papas') return papalCount
    return (nonPapal[id as DocumentType]?.length ?? 0)
  }

  const activePopeEntry = byPope.find(entry => entry.pope === activePope)
  const availablePopeTypes = PAPAL_DOC_TYPES.filter(
    type => (activePopeEntry?.types[type.id]?.length ?? 0) > 0
  )
  const resolvedActiveType = availablePopeTypes.some(type => type.id === activeType)
    ? activeType
    : availablePopeTypes[0]?.id ?? activeType
  const activeTypeBooks = activePopeEntry?.types[resolvedActiveType] ?? []
  const activeTabMeta = activeTab ? TOP_TABS.find(tab => tab.id === activeTab) ?? null : null
  const activeTabTotal = activeTab ? tabCount(activeTab) : 0

  function renderDocumentTab(tab: TopTab) {
    const books = nonPapal[tab as DocumentType] ?? []
    const label = TOP_TABS.find(t => t.id === tab)?.label ?? tab
    if (books.length === 0) return <EmptyTab label={label} />

    const configuredSubTabs = SUB_TABS[tab] ?? []
    const availableSubTabs = configuredSubTabs
      .map(subTab => ({ ...subTab, count: books.filter(subTab.match).length }))
      .filter(subTab => subTab.count > 0)
    const unmatchedBooks = books.filter(book => !configuredSubTabs.some(subTab => subTab.match(book)))
    if (configuredSubTabs.length > 0 && unmatchedBooks.length > 0) {
      availableSubTabs.push({
        id: 'outros',
        label: FALLBACK_SUBTAB_LABEL[tab] ?? 'Outras obras',
        match: book => !configuredSubTabs.some(subTab => subTab.match(book)),
        count: unmatchedBooks.length,
      })
    }
    const selectedSubTab = activeSubTabs[tab]
    const resolvedSubTab = availableSubTabs.some(subTab => subTab.id === selectedSubTab)
      ? selectedSubTab
      : availableSubTabs[0]?.id
    const activeMatcher = availableSubTabs.find(subTab => subTab.id === resolvedSubTab)?.match
    const filteredBooks = (activeMatcher ? books.filter(activeMatcher) : books)
      .slice()
      .sort((a, b) => a.title.localeCompare(b.title, 'pt'))
    const showSubTabs = availableSubTabs.length > 0

    return (
      <div className="space-y-4">
        {showSubTabs && (
          <div className="flex flex-wrap gap-2 border-b border-fundo-borda pb-3">
            {availableSubTabs.map(subTab => {
              const isActive = resolvedSubTab === subTab.id
              return (
                <button
                  key={subTab.id}
                  onClick={() => setActiveSubTabs(prev => ({ ...prev, [tab]: subTab.id }))}
                  className={`rounded-lg border px-3 py-2 text-xs font-medium transition-colors ${
                    isActive
                      ? 'border-dourado/40 bg-dourado/10 text-dourado'
                      : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
                  }`}
                >
                  {subTab.label}
                  <span className={`ml-1.5 rounded-full px-1.5 py-0.5 text-xs ${
                    isActive ? 'bg-dourado/20 text-dourado' : 'bg-fundo text-texto-terciario'
                  }`}>
                    {subTab.count}
                  </span>
                </button>
              )
            })}
          </div>
        )}
        <div className="space-y-3">
          {filteredBooks.map(book => <BookCard key={book.id} book={book} />)}
        </div>
      </div>
    )
  }

  if (!activeTab) {
    return (
      <section className="space-y-4">
        <div className="border-b border-fundo-borda pb-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
            Índice documental
          </p>
          <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
            Documentos da Igreja
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
            Escolha uma área para abrir uma tela própria com seus conteúdos.
          </p>
        </div>

        <nav className="space-y-2">
          {TOP_TABS.map(tab => {
            const count = tabCount(tab.id)
            const isEmpty = count === 0
            return (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveTab(tab.id)
                  setActivePope(null)
                }}
                aria-label={tab.label}
                className={`flex w-full items-center justify-between gap-3 rounded-lg border px-4 py-3 text-left transition-colors ${
                  isEmpty
                    ? 'border-fundo-borda/50 bg-fundo-card/50 hover:border-dourado/20'
                    : 'border-fundo-borda bg-fundo-card hover:border-dourado/30 hover:bg-vinho-escuro/10'
                }`}
              >
                <span className="min-w-0">
                  <span className={`block text-sm font-semibold ${isEmpty ? 'text-texto-terciario' : 'text-texto'}`}>
                    {tab.label}
                  </span>
                  <span className="mt-0.5 block text-xs leading-snug text-texto-terciario">
                    {tab.description}
                  </span>
                </span>
                <span aria-hidden="true" className="shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
                  {count}
                </span>
              </button>
            )
          })}
        </nav>
      </section>
    )
  }

  return (
    <section className="min-w-0 space-y-4">
      <div className="border-b border-fundo-borda pb-3">
        <button
          type="button"
          onClick={() => {
            setActiveTab(null)
            setActivePope(null)
          }}
          className="mb-2 inline-flex items-center gap-1 text-xs text-texto-terciario transition-colors hover:text-dourado"
        >
          <span aria-hidden="true">‹</span>
          Documentos da Igreja
        </button>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
              Documentos da Igreja
            </p>
            <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
              {activeTabMeta?.label}
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
              {activeTabMeta?.description}
            </p>
          </div>
          <span className="shrink-0 rounded-full bg-dourado/15 px-2.5 py-1 text-xs font-medium text-dourado">
            {activeTabTotal}
          </span>
        </div>
      </div>

      {activeTab === 'papas' && (
        byPope.length === 0 ? <EmptyTab label="Papas" /> : (
          <>
            {!activePope && (
              <div className="space-y-2">
                {byPope.map(entry => (
                  <button
                    key={entry.pope}
                    onClick={() => setActivePope(entry.pope)}
                    className="flex w-full items-center justify-between rounded-lg border border-fundo-borda bg-fundo-card px-4 py-3 text-left transition-colors hover:border-dourado/30 hover:bg-vinho-escuro/10"
                  >
                    <span className="text-sm font-semibold text-texto">
                      {entry.pope}
                    </span>
                    <span className="ml-3 shrink-0 rounded-full bg-fundo px-2 py-0.5 text-xs text-dourado">
                      {entry.totalCount}
                    </span>
                  </button>
                ))}
              </div>
            )}

            {activePopeEntry && availablePopeTypes.length > 0 && (
              <div className="space-y-3">
                <button
                  type="button"
                  onClick={() => setActivePope(null)}
                  className="inline-flex items-center gap-1 text-xs text-texto-terciario transition-colors hover:text-dourado"
                >
                  <span aria-hidden="true">‹</span>
                  Papas
                </button>
                <div className="rounded-lg border border-fundo-borda bg-fundo-card/60 p-3">
                  <div className="mb-3 flex items-start justify-between gap-3 border-b border-fundo-borda pb-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
                        Documentos pontifícios
                      </p>
                      <h3 className="mt-1 font-garamond text-xl font-medium text-texto">
                        {activePopeEntry.pope}
                      </h3>
                    </div>
                    <span className="shrink-0 rounded-full bg-dourado/15 px-2.5 py-1 text-xs font-medium text-dourado">
                      {activePopeEntry.totalCount}
                    </span>
                  </div>
                  {availablePopeTypes.length > 1 && (
                    <div className="mb-3 flex flex-wrap gap-2">
                      {availablePopeTypes.map(type => {
                        const count = activePopeEntry.types[type.id]?.length ?? 0
                        const isTypeActive = resolvedActiveType === type.id
                        return (
                          <button
                            key={type.id}
                            onClick={() => setActiveType(type.id)}
                            className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors ${
                              isTypeActive
                                ? 'border-dourado/40 bg-dourado/10 text-dourado'
                                : 'border-fundo-borda bg-fundo-card text-texto-secundario hover:border-dourado/20'
                            }`}
                          >
                            {type.tabLabel}
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
                  <p className="mb-3 text-xs font-medium uppercase tracking-wider text-texto-terciario">
                    {PAPAL_DOC_TYPES.find(type => type.id === resolvedActiveType)?.label}
                  </p>
                  <div className="space-y-3">
                    {activeTypeBooks.map(book => <BookCard key={book.id} book={book} />)}
                  </div>
                </div>
              </div>
            )}
          </>
        )
      )}

      {activeTab === 'concilio' && (
        <ConciliosSection books={nonPapal['concilio'] ?? []} />
      )}

      {DOCUMENT_TABS.includes(activeTab) && renderDocumentTab(activeTab)}
    </section>
  )
}
