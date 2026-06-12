import { useCallback, useEffect, useState } from 'react'
import {
  ActivityIndicator,
  Platform,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native'
import {
  listBooks,
  listAuthorsCatalog,
  type Book,
  type AuthorCatalogEntry,
  type PatristicTradition,
  type DocumentType,
} from '../lib/api'
import { formatLanguage } from '../lib/language'
import { groupByCentury, getAuthorDeathYear } from '../lib/century'

// ── Helpers ───────────────────────────────────────────────────────────────────

const COLLECTION_LABEL: Record<string, string> = {
  PT: 'Paulus', PL: 'Migne PL', PG: 'Migne PG', PO: 'Patrologia Orientalis',
}

const COLLECTION_COLOR: Record<string, string> = {
  PG: '#7c3aed', PL: '#1d4ed8', PT: '#0f766e', PO: '#b45309',
}

function editionSummary(books: Book[]): string {
  const labels = [...new Set(
    books.map(b => b.edition_label || COLLECTION_LABEL[b.collection ?? ''] || b.collection || '')
      .filter(Boolean)
  )]
  return labels.length > 0 ? labels.join(' · ') : 'Patrística'
}

function groupByWork(books: Book[]): { title: string; books: Book[] }[] {
  const map: Record<string, Book[]> = {}
  for (const book of books) {
    const title = book.canonical_title ?? book.title
    if (!map[title]) map[title] = []
    map[title].push(book)
  }
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b, 'pt'))
    .map(([title, bks]) => ({ title, books: bks }))
}

function languageParts(language: string | null): string[] {
  return (language ?? '')
    .toLowerCase()
    .replace(/\s+e\s+/g, '+')
    .split(/[+/;,|]/)
    .map(part => part.trim())
    .filter(Boolean)
}

function patristicTraditionsFor(book: Book): PatristicTradition[] {
  const parts = languageParts(book.language)
  const isBilingualGreekPortuguese = parts.includes('grc') && parts.includes('pt')
  const isDidaque = [book.collection, book.title, book.canonical_title]
    .filter(Boolean)
    .join(' ')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .includes('didaque')

  if (isDidaque && isBilingualGreekPortuguese) return ['grega', 'portuguesa']
  return [(book.patristic_tradition ?? 'latina') as PatristicTradition]
}

function normalizeKey(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
}

function publisherLabelFor(book: Book): string {
  const label = (book.edition_label || book.source_label || '').trim()
  const normalized = label
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
  if (normalized.includes('paulus')) return 'Paulus'
  if (normalized.includes('familia')) return 'Editora Família'
  if (label) return label
  return 'Outras editoras'
}

// ── Library data organizer ────────────────────────────────────────────────────

type DocumentsLib = {
  byPope: { pope: string; latestYear: number | null; totalCount: number; types: Partial<Record<DocumentType, Book[]>> }[]
  nonPapal: Partial<Record<DocumentType, Book[]>>
}

type LibraryData = {
  patristica: Record<PatristicTradition, Book[]>
  documentos: DocumentsLib
}

const NON_PAPAL_TYPES: DocumentType[] = [
  'concilio',
  'catecismo',
  'catequese',
  'liturgia',
  'doutrina_social',
  'direito_canonico',
  'teologia',
  'linguas_biblicas',
  'literatura_crista',
]

function organizeLibrary(books: Book[]): LibraryData {
  const patristica: Record<PatristicTradition, Book[]> = {
    grega: [], oriental: [], latina: [], portuguesa: [],
  }
  const popeMap: Record<string, Book[]> = {}
  const nonPapalMap: Partial<Record<DocumentType, Book[]>> = {}

  for (const book of books) {
    if (book.library_section === 'documentos') {
      const dt = (book.document_type ?? 'outro') as DocumentType
      if (!NON_PAPAL_TYPES.includes(dt) && book.pope) {
        if (!popeMap[book.pope]) popeMap[book.pope] = []
        popeMap[book.pope].push(book)
      } else {
        if (!nonPapalMap[dt]) nonPapalMap[dt] = []
        nonPapalMap[dt]!.push(book)
      }
    } else {
      for (const trad of patristicTraditionsFor(book)) {
        patristica[trad].push(book)
      }
    }
  }

  const byPope = Object.entries(popeMap).map(([pope, popeBooks]) => {
    const types: Partial<Record<DocumentType, Book[]>> = {}
    for (const book of popeBooks) {
      const dt = (book.document_type ?? 'outro') as DocumentType
      if (!types[dt]) types[dt] = []
      types[dt]!.push(book)
    }
    const years = popeBooks.map(b => b.document_year).filter(Boolean) as number[]
    return { pope, latestYear: years.length ? Math.max(...years) : null, totalCount: popeBooks.length, types }
  })
  byPope.sort((a, b) => {
    if (a.pope === 'Outros') return 1
    if (b.pope === 'Outros') return -1
    return (b.latestYear ?? 0) - (a.latestYear ?? 0)
  })

  return { patristica, documentos: { byPope, nonPapal: nonPapalMap } }
}

// ── Mini-components ───────────────────────────────────────────────────────────

function TabBar({ tabs, active, onPress }: {
  tabs: { id: string; label: string; count?: number }[]
  active: string
  onPress: (id: string) => void
}) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabScroll} contentContainerStyle={styles.tabContent}>
      {tabs.map(tab => (
        <TouchableOpacity
          key={tab.id}
          style={[styles.tabBtn, active === tab.id && styles.tabBtnActive]}
          onPress={() => onPress(tab.id)}
        >
          <Text style={[styles.tabLabel, active === tab.id && styles.tabLabelActive]}>
            {tab.label}
          </Text>
          {tab.count !== undefined && (
            <View style={[styles.tabCount, active === tab.id && styles.tabCountActive]}>
              <Text style={[styles.tabCountText, active === tab.id && styles.tabCountTextActive]}>
                {tab.count}
              </Text>
            </View>
          )}
        </TouchableOpacity>
      ))}
    </ScrollView>
  )
}

function CollectionBadge({ collection }: { collection: string | null }) {
  const col = collection ?? ''
  const color = COLLECTION_COLOR[col] ?? '#6b7280'
  return (
    <View style={[styles.badge, { backgroundColor: color + '22', borderColor: color + '55' }]}>
      <Text style={[styles.badgeText, { color }]}>{(COLLECTION_LABEL[col] ?? col) || '—'}</Text>
    </View>
  )
}

function BookRow({ book, onPress }: { book: Book; onPress?: () => void }) {
  const col = book.collection ?? ''
  const collectionLabel = COLLECTION_LABEL[col] ?? col
  return (
    <TouchableOpacity style={styles.bookRow} onPress={onPress} disabled={!onPress}>
      <View style={styles.bookRowLeft}>
        {book.is_primary_source && (
          <View style={styles.primaryBadge}>
            <Text style={styles.primaryBadgeText}>Primária</Text>
          </View>
        )}
        {collectionLabel ? (
          <Text style={[styles.bookRowCollection, { fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' }]}>
            {collectionLabel}
          </Text>
        ) : null}
        {book.language ? (
          <Text style={styles.bookRowLang}>{formatLanguage(book.language)}</Text>
        ) : null}
        {book.chunk_count !== undefined && book.chunk_count > 0 && (
          <Text style={styles.bookRowChunks}>{book.chunk_count} trechos indexados</Text>
        )}
      </View>
      {onPress && (
        <Text style={styles.chevron}>›</Text>
      )}
    </TouchableOpacity>
  )
}

// ── Seção Patrística ──────────────────────────────────────────────────────────

const TRADITIONS: { id: PatristicTradition; label: string; desc: string }[] = [
  { id: 'latina',    label: 'Patrística Latina',    desc: 'Fontes primárias latinas — PL e equivalentes' },
  { id: 'grega',     label: 'Patrística Grega',     desc: 'Fontes primárias em grego' },
  { id: 'oriental',  label: 'Patrística Oriental',  desc: 'Siríaco, copta, árabe e outras línguas orientais' },
  { id: 'portuguesa', label: 'em Português',        desc: 'Traduções, edições vernáculas e materiais de apoio' },
]

function PatristicaTab({
  patristica,
  onBookPress,
}: {
  patristica: Record<PatristicTradition, Book[]>
  onBookPress: (bookId: number) => void
}) {
  const [active, setActive] = useState<PatristicTradition>('latina')
  const [publisherTab, setPublisherTab] = useState('todos')
  const allBooks = patristica[active]
  const publisherTabs = active === 'portuguesa'
    ? [...new Map(allBooks.map(book => {
        const label = publisherLabelFor(book)
        return [normalizeKey(label), { id: normalizeKey(label), label }]
      })).values()]
      .sort((a, b) => {
        if (a.label === 'Paulus') return -1
        if (b.label === 'Paulus') return 1
        if (a.label === 'Outras editoras') return 1
        if (b.label === 'Outras editoras') return -1
        return a.label.localeCompare(b.label, 'pt')
      })
    : []
  const resolvedPublisherTab = publisherTab === 'todos' || publisherTabs.some(tab => tab.id === publisherTab)
    ? publisherTab
    : 'todos'
  const books = active === 'portuguesa' && resolvedPublisherTab !== 'todos'
    ? allBooks.filter(book => normalizeKey(publisherLabelFor(book)) === resolvedPublisherTab)
    : allBooks

  return (
    <View style={{ gap: 12 }}>
      <View style={{ gap: 6 }}>
        {TRADITIONS.map(t => {
          const count = patristica[t.id].length
          const isActive = active === t.id
          return (
            <TouchableOpacity
              key={t.id}
              style={[styles.traditionRow, isActive && styles.traditionRowActive]}
              onPress={() => {
                setActive(t.id)
                setPublisherTab('todos')
              }}
            >
              <View style={{ flex: 1 }}>
                <Text style={[styles.traditionLabel, isActive && styles.traditionLabelActive]}>{t.label}</Text>
                <Text style={styles.traditionDesc}>{t.desc}</Text>
              </View>
              <View style={[styles.traditionCount, isActive && styles.traditionCountActive]}>
                <Text style={[styles.traditionCountText, isActive && styles.traditionCountTextActive]}>{count}</Text>
              </View>
            </TouchableOpacity>
          )
        })}
      </View>

      <Text style={styles.sectionHeader}>{TRADITIONS.find(t => t.id === active)?.label}</Text>

      {publisherTabs.length > 1 && (
        <TabBar
          tabs={[
            { id: 'todos', label: 'Todas', count: allBooks.length },
            ...publisherTabs.map(tab => ({
              id: tab.id,
              label: tab.label,
              count: allBooks.filter(book => normalizeKey(publisherLabelFor(book)) === tab.id).length,
            })),
          ]}
          active={resolvedPublisherTab}
          onPress={setPublisherTab}
        />
      )}

      {books.length === 0 ? (
        <View style={styles.emptyBox}>
          <Text style={styles.emptyText}>Nenhuma obra catalogada nesta categoria ainda.</Text>
        </View>
      ) : (
        <View style={{ gap: 8 }}>
          {books.map(book => (
            <TouchableOpacity key={book.id} style={styles.bookCard} onPress={() => onBookPress(book.id)}>
              <View style={styles.bookCardHeader}>
                <CollectionBadge collection={book.collection} />
                {book.language && <Text style={styles.bookLang}>{formatLanguage(book.language)}</Text>}
              </View>
              <Text style={styles.bookTitle} numberOfLines={2}>{book.title}</Text>
              {book.author && <Text style={styles.bookAuthor} numberOfLines={1}>{book.author}</Text>}
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  )
}

// ── Seção Autores ─────────────────────────────────────────────────────────────

function AutoresTab({
  catalog,
  onBookPress,
}: {
  catalog: AuthorCatalogEntry[]
  onBookPress: (bookId: number) => void
}) {
  const [openAuthor, setOpenAuthor] = useState<string | null>(null)
  const [openWork, setOpenWork] = useState<string | null>(null)

  if (catalog.length === 0) {
    return (
      <View style={styles.emptyBox}>
        <Text style={styles.emptyText}>Catálogo indisponível.</Text>
      </View>
    )
  }

  const withBooks = catalog.filter(e => e.book_count > 0)
  const withoutBooks = catalog.filter(e => e.book_count === 0)
  const centuries = groupByCentury(withBooks, e => getAuthorDeathYear(e.name))

  function toggleAuthor(name: string) {
    setOpenAuthor(prev => prev === name ? null : name)
    setOpenWork(null)
  }
  function toggleWork(key: string) {
    setOpenWork(prev => prev === key ? null : key)
  }

  return (
    <View style={{ gap: 16 }}>
      <View style={styles.authorStats}>
        <Text style={styles.authorStatText}>
          <Text style={styles.authorStatHighlight}>{catalog.length}</Text> Padres conhecidos
          {'  ·  '}
          <Text style={styles.authorStatValue}>{withBooks.length}</Text> com obras catalogadas
        </Text>
      </View>

      {centuries.map(({ label, items }) => (
        <View key={label} style={{ gap: 6 }}>
          <Text style={styles.centuryLabel}>{label}</Text>
          {items.map(entry => {
            const isAuthorOpen = openAuthor === entry.name
            const works = groupByWork(entry.books)
            const deathYear = getAuthorDeathYear(entry.name)

            return (
              <View key={entry.name} style={styles.authorAccordion}>
                <TouchableOpacity style={styles.authorHeader} onPress={() => toggleAuthor(entry.name)}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.authorName}>
                      {entry.name}
                      {deathYear ? <Text style={styles.authorDeath}> † {deathYear}</Text> : null}
                    </Text>
                    <Text style={styles.authorMeta}>
                      {editionSummary(entry.books)} · {entry.book_count} {entry.book_count === 1 ? 'obra' : 'obras'} — {entry.chunk_count} trechos
                    </Text>
                  </View>
                  <Text style={[styles.chevron, isAuthorOpen && { transform: [{ rotate: '90deg' }] }]}>›</Text>
                </TouchableOpacity>

                {isAuthorOpen && (
                  <View style={styles.worksContainer}>
                    {works.map(({ title, books }) => {
                      const workKey = `${entry.name}::${title}`
                      const isWorkOpen = openWork === workKey
                      return (
                        <View key={title}>
                          <TouchableOpacity style={styles.workHeader} onPress={() => toggleWork(workKey)}>
                            <Text style={styles.workTitle} numberOfLines={2}>{title}</Text>
                            <View style={styles.workEditionCount}>
                              <Text style={styles.workEditionCountText}>
                                {books.length} {books.length === 1 ? 'edição' : 'edições'}
                              </Text>
                            </View>
                          </TouchableOpacity>
                          {isWorkOpen && (
                            <View style={styles.editionsContainer}>
                              {books.map(book => (
                                <BookRow
                                  key={book.id}
                                  book={book}
                                  onPress={() => onBookPress(book.id)}
                                />
                              ))}
                            </View>
                          )}
                        </View>
                      )
                    })}
                  </View>
                )}
              </View>
            )
          })}
        </View>
      ))}

      {withoutBooks.length > 0 && (
        <View style={{ gap: 6 }}>
          <Text style={styles.centuryLabel}>Sem obras catalogadas ({withoutBooks.length})</Text>
          {withoutBooks.map(entry => (
            <View key={entry.name} style={styles.authorEmpty}>
              <Text style={styles.authorEmptyName}>{entry.name}</Text>
              <Text style={styles.authorEmptyCollection}>{COLLECTION_LABEL[entry.collection] ?? entry.collection}</Text>
            </View>
          ))}
        </View>
      )}
    </View>
  )
}

// ── Seção Documentos ──────────────────────────────────────────────────────────

const PAPAL_DOC_TYPES: { id: DocumentType; label: string; tabLabel: string }[] = [
  { id: 'enciclica',               label: 'Encíclicas',                tabLabel: 'Encíclicas' },
  { id: 'bula',                    label: 'Bulas Papais',              tabLabel: 'Bulas' },
  { id: 'constituicao_apostolica', label: 'Constituições Apostólicas', tabLabel: 'Const. Ap.' },
  { id: 'carta_apostolica',        label: 'Cartas Apostólicas',        tabLabel: 'Cartas Ap.' },
  { id: 'motu_proprio',            label: 'Motu Proprio',              tabLabel: 'Motu Proprio' },
  { id: 'exortacao_apostolica',    label: 'Exortações Apostólicas',    tabLabel: 'Exort. Ap.' },
  { id: 'outro',                   label: 'Outros',                    tabLabel: 'Outros' },
]

const TOP_TABS_DOCS: { id: string; label: string }[] = [
  { id: 'papas',            label: 'Papas' },
  { id: 'concilio',         label: 'Concílios' },
  { id: 'catecismo',        label: 'Catecismo' },
  { id: 'catequese',        label: 'Catequese' },
  { id: 'liturgia',         label: 'Liturgia' },
  { id: 'doutrina_social',  label: 'Doutrina Social' },
  { id: 'direito_canonico', label: 'Dir. Canônico' },
  { id: 'teologia',         label: 'Teologia' },
  { id: 'linguas_biblicas', label: 'Línguas' },
  { id: 'literatura_crista', label: 'Literatura' },
]

function DocumentosTab({
  documentos,
  onBookPress,
}: {
  documentos: DocumentsLib
  onBookPress: (bookId: number) => void
}) {
  const { byPope, nonPapal } = documentos
  const [activeTab, setActiveTab] = useState('papas')
  const [activePope, setActivePope] = useState<string>(byPope[0]?.pope ?? '')
  const [activeType, setActiveType] = useState<DocumentType>('enciclica')

  function tabCount(id: string): number {
    if (id === 'papas') return byPope.reduce((s, e) => s + e.totalCount, 0)
    return (nonPapal[id as DocumentType]?.length ?? 0)
  }

  const activePopeEntry = byPope.find(e => e.pope === activePope)
  const availablePopeTypes = PAPAL_DOC_TYPES.filter(
    t => (activePopeEntry?.types[t.id]?.length ?? 0) > 0
  )
  const resolvedType = availablePopeTypes.some(t => t.id === activeType)
    ? activeType
    : availablePopeTypes[0]?.id ?? activeType
  const activeTypeBooks = activePopeEntry?.types[resolvedType] ?? []

  return (
    <View style={{ gap: 12 }}>
      {/* Tabs de nível superior */}
      <TabBar
        tabs={TOP_TABS_DOCS.map(t => ({ id: t.id, label: t.label, count: tabCount(t.id) }))}
        active={activeTab}
        onPress={setActiveTab}
      />

      {/* Papas */}
      {activeTab === 'papas' && (
        byPope.length === 0
          ? <View style={styles.emptyBox}><Text style={styles.emptyText}>Nenhum documento papal catalogado ainda.</Text></View>
          : <View style={{ gap: 10 }}>
              <View style={{ gap: 4 }}>
                {byPope.map(entry => {
                  const isActive = entry.pope === activePope
                  return (
                    <TouchableOpacity
                      key={entry.pope}
                      style={[styles.traditionRow, isActive && styles.traditionRowActive]}
                      onPress={() => setActivePope(entry.pope)}
                    >
                      <Text style={[styles.traditionLabel, isActive && styles.traditionLabelActive]}>
                        {entry.pope}
                      </Text>
                      <View style={[styles.traditionCount, isActive && styles.traditionCountActive]}>
                        <Text style={[styles.traditionCountText, isActive && styles.traditionCountTextActive]}>
                          {entry.totalCount}
                        </Text>
                      </View>
                    </TouchableOpacity>
                  )
                })}
              </View>

              {activePopeEntry && availablePopeTypes.length > 0 && (
                <View style={{ gap: 10 }}>
                  {availablePopeTypes.length > 1 && (
                    <TabBar
                      tabs={availablePopeTypes.map(t => ({
                        id: t.id,
                        label: t.tabLabel,
                        count: activePopeEntry.types[t.id]?.length ?? 0,
                      }))}
                      active={resolvedType}
                      onPress={id => setActiveType(id as DocumentType)}
                    />
                  )}
                  <Text style={styles.sectionHeader}>
                    {PAPAL_DOC_TYPES.find(t => t.id === resolvedType)?.label} — {activePopeEntry.pope}
                  </Text>
                  <View style={{ gap: 8 }}>
                    {activeTypeBooks.map(book => (
                      <TouchableOpacity key={book.id} style={styles.bookCard} onPress={() => onBookPress(book.id)}>
                        <Text style={styles.bookTitle} numberOfLines={2}>{book.canonical_title ?? book.title}</Text>
                        {book.document_year && <Text style={styles.bookAuthor}>{book.document_year}</Text>}
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>
              )}
            </View>
      )}

      {/* Concílios */}
      {activeTab === 'concilio' && (() => {
        const books = nonPapal['concilio'] ?? []
        if (books.length === 0) return <View style={styles.emptyBox}><Text style={styles.emptyText}>Nenhum concílio catalogado ainda.</Text></View>
        return (
          <View style={{ gap: 8 }}>
            <Text style={styles.sectionHeader}>Concílios Ecumênicos e Regionais</Text>
            {books.map(book => (
              <TouchableOpacity key={book.id} style={styles.bookCard} onPress={() => onBookPress(book.id)}>
                <Text style={styles.bookTitle} numberOfLines={2}>{book.canonical_title ?? book.title}</Text>
                {book.document_year && <Text style={styles.bookAuthor}>{book.document_year}</Text>}
              </TouchableOpacity>
            ))}
          </View>
        )
      })()}

      {/* Catecismo / Direito Canônico */}
      {activeTab !== 'papas' && activeTab !== 'concilio' && (() => {
        const books = nonPapal[activeTab as DocumentType] ?? []
        const label = TOP_TABS_DOCS.find(t => t.id === activeTab)!.label
        if (books.length === 0) return <View style={styles.emptyBox}><Text style={styles.emptyText}>Nenhum documento em {label} catalogado ainda.</Text></View>
        return (
          <View style={{ gap: 8 }}>
            <Text style={styles.sectionHeader}>{label}</Text>
            {books.map(book => (
              <TouchableOpacity key={book.id} style={styles.bookCard} onPress={() => onBookPress(book.id)}>
                <Text style={styles.bookTitle} numberOfLines={2}>{book.canonical_title ?? book.title}</Text>
              </TouchableOpacity>
            ))}
          </View>
        )
      })()}
    </View>
  )
}

// ── Tela principal ────────────────────────────────────────────────────────────

type Section = 'patristica' | 'autores' | 'documentos'

const SECTIONS: { id: Section; label: string }[] = [
  { id: 'patristica', label: 'Biblioteca Patrística' },
  { id: 'autores',    label: 'Obras dos Padres' },
  { id: 'documentos', label: 'Documentos da Igreja' },
]

export default function BibliotecaScreen({ navigation }: { navigation: any }) {
  const [catalog, setCatalog] = useState<AuthorCatalogEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [section, setSection] = useState<Section>('patristica')
  const [library, setLibrary] = useState<LibraryData>({
    patristica: { grega: [], oriental: [], latina: [], portuguesa: [] },
    documentos: { byPope: [], nonPapal: {} },
  })

  async function load(isRefresh = false) {
    if (isRefresh) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const [booksData, catalogData] = await Promise.all([listBooks(), listAuthorsCatalog()])
      setCatalog(catalogData)
      setLibrary(organizeLibrary(booksData))
    } catch (e: any) {
      setError(e.message ?? 'Erro ao carregar acervo')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => { load() }, [])

  const onRefresh = useCallback(() => load(true), [])

  function openBook(id: number) {
    navigation.navigate('BookDetail', { bookId: id })
  }

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1e3a5f" />
        <Text style={styles.loadingText}>Carregando acervo...</Text>
      </View>
    )
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => load()}>
          <Text style={styles.retryText}>Tentar novamente</Text>
        </TouchableOpacity>
      </View>
    )
  }

  return (
    <ScrollView
      style={styles.root}
      contentContainerStyle={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#1e3a5f" />}
    >
      {/* Seletor de seção */}
      <View style={styles.sectionSelector}>
        {SECTIONS.map(s => (
          <TouchableOpacity
            key={s.id}
            style={[styles.sectionBtn, section === s.id && styles.sectionBtnActive]}
            onPress={() => setSection(s.id)}
          >
            <Text style={[styles.sectionBtnText, section === s.id && styles.sectionBtnTextActive]}>
              {s.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {section === 'patristica' && (
        <PatristicaTab patristica={library.patristica} onBookPress={openBook} />
      )}
      {section === 'autores' && (
        <AutoresTab catalog={catalog} onBookPress={openBook} />
      )}
      {section === 'documentos' && (
        <DocumentosTab documentos={library.documentos} onBookPress={openBook} />
      )}
    </ScrollView>
  )
}

// ── Estilos ────────────────────────────────────────────────────────────────────

const GOLD = '#c9a84c'
const DARK_BLUE = '#1e3a5f'

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f9fafb' },
  container: { padding: 16, paddingBottom: 48, gap: 12 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12 },
  loadingText: { fontSize: 14, color: '#6b7280', marginTop: 8 },
  errorText: { fontSize: 14, color: '#dc2626', textAlign: 'center', paddingHorizontal: 24 },
  retryBtn: { backgroundColor: DARK_BLUE, borderRadius: 8, paddingHorizontal: 20, paddingVertical: 10 },
  retryText: { color: '#fff', fontWeight: '600' },

  // Section selector
  sectionSelector: {
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    padding: 4,
    gap: 4,
  },
  sectionBtn: {
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    alignItems: 'center',
  },
  sectionBtnActive: { backgroundColor: GOLD + '22' },
  sectionBtnText: { fontSize: 13, fontWeight: '500', color: '#6b7280' },
  sectionBtnTextActive: { color: GOLD, fontWeight: '700' },

  // Tab bar
  tabScroll: { marginBottom: 4 },
  tabContent: { gap: 6, paddingVertical: 2 },
  tabBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 6,
    backgroundColor: '#fff',
  },
  tabBtnActive: { borderColor: GOLD + '66', backgroundColor: GOLD + '18' },
  tabLabel: { fontSize: 12, fontWeight: '500', color: '#374151' },
  tabLabelActive: { color: GOLD },
  tabCount: { backgroundColor: '#f3f4f6', borderRadius: 10, paddingHorizontal: 5, paddingVertical: 1 },
  tabCountActive: { backgroundColor: GOLD + '33' },
  tabCountText: { fontSize: 10, color: '#6b7280' },
  tabCountTextActive: { color: GOLD },

  // Tradition/Pope rows
  traditionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 12,
  },
  traditionRowActive: { borderColor: GOLD + '66', backgroundColor: GOLD + '11' },
  traditionLabel: { fontSize: 14, fontWeight: '500', color: '#111827' },
  traditionLabelActive: { color: GOLD },
  traditionDesc: { fontSize: 11, color: '#9ca3af', marginTop: 2 },
  traditionCount: { marginLeft: 'auto', backgroundColor: '#f3f4f6', borderRadius: 12, paddingHorizontal: 8, paddingVertical: 2 },
  traditionCountActive: { backgroundColor: GOLD + '33' },
  traditionCountText: { fontSize: 11, color: '#6b7280' },
  traditionCountTextActive: { color: GOLD },

  // Book cards
  bookCard: {
    backgroundColor: '#fff',
    borderRadius: 10,
    padding: 12,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    gap: 4,
  },
  bookCardHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 2 },
  bookTitle: { fontSize: 14, fontWeight: '600', color: '#111827', lineHeight: 20 },
  bookAuthor: { fontSize: 12, color: '#6b7280' },
  bookLang: { fontSize: 11, color: '#9ca3af' },
  badge: { borderWidth: 1, borderRadius: 5, paddingHorizontal: 7, paddingVertical: 2 },
  badgeText: { fontSize: 10, fontWeight: '700' },

  // Book row (in accordion)
  bookRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 8,
    padding: 10,
    marginBottom: 4,
  },
  bookRowLeft: { flex: 1, gap: 2 },
  bookRowCollection: { fontSize: 11, color: '#6b7280' },
  bookRowLang: { fontSize: 11, color: '#9ca3af' },
  bookRowChunks: { fontSize: 11, color: '#9ca3af' },
  primaryBadge: { alignSelf: 'flex-start', backgroundColor: GOLD + '22', borderRadius: 10, paddingHorizontal: 7, paddingVertical: 2, marginBottom: 2 },
  primaryBadgeText: { fontSize: 10, fontWeight: '700', color: GOLD },
  chevron: { fontSize: 18, color: '#9ca3af', marginLeft: 8 },

  // Author accordion
  authorStats: { paddingVertical: 4 },
  authorStatText: { fontSize: 12, color: '#9ca3af' },
  authorStatHighlight: { color: GOLD, fontWeight: '600' },
  authorStatValue: { color: '#374151', fontWeight: '500' },
  centuryLabel: { fontSize: 11, fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.8, paddingBottom: 4, borderBottomWidth: 1, borderBottomColor: '#e5e7eb', marginBottom: 4 },
  authorAccordion: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, overflow: 'hidden' },
  authorHeader: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 14, paddingVertical: 12, backgroundColor: '#fff' },
  authorName: { fontSize: 14, fontWeight: '600', color: '#111827' },
  authorDeath: { fontSize: 13, fontWeight: '400', color: '#9ca3af' },
  authorMeta: { fontSize: 11, color: '#9ca3af', marginTop: 2 },
  worksContainer: { borderTopWidth: 1, borderTopColor: '#e5e7eb' },
  workHeader: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 16, paddingVertical: 10, backgroundColor: '#f9fafb', borderBottomWidth: 1, borderBottomColor: '#f3f4f6' },
  workTitle: { flex: 1, fontSize: 13, fontWeight: '500', color: '#374151' },
  workEditionCount: { backgroundColor: '#fff', borderRadius: 10, paddingHorizontal: 7, paddingVertical: 2, marginLeft: 8 },
  workEditionCountText: { fontSize: 10, color: '#9ca3af' },
  editionsContainer: { paddingHorizontal: 12, paddingVertical: 8 },
  authorEmpty: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', backgroundColor: '#f9fafb', borderWidth: 1, borderColor: '#f3f4f6', borderRadius: 8, paddingHorizontal: 14, paddingVertical: 10 },
  authorEmptyName: { fontSize: 13, color: '#9ca3af' },
  authorEmptyCollection: { fontSize: 11, color: '#d1d5db' },

  // Section header
  sectionHeader: { fontSize: 17, fontWeight: '700', color: DARK_BLUE },
  emptyBox: { backgroundColor: '#fff', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, padding: 24, alignItems: 'center' },
  emptyText: { fontSize: 13, color: '#9ca3af', textAlign: 'center' },
})
