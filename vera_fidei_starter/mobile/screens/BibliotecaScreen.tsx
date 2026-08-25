import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  ActivityIndicator,
  FlatList,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'

import { ApiError, listBooks, type Book, type PatristicTradition } from '../lib/api'
import { formatLanguage } from '../lib/language'
import { colors } from '../lib/theme'

type Section = 'patristica' | 'padres' | 'documentos'
type TraditionFilter = 'todas' | PatristicTradition

const sections: { id: Section; label: string }[] = [
  { id: 'patristica', label: 'Biblioteca Patrística' },
  { id: 'padres', label: 'Obras dos Padres' },
  { id: 'documentos', label: 'Documentos da Igreja' },
]

const traditions: { id: TraditionFilter; label: string }[] = [
  { id: 'todas', label: 'Todas' },
  { id: 'grega', label: 'Patrística Grega' },
  { id: 'oriental', label: 'Patrística Oriental' },
  { id: 'latina', label: 'Patrística Latina' },
  { id: 'portuguesa', label: 'Português / traduções' },
]

function normalized(value: string | null | undefined): string {
  return (value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

function belongsToSection(book: Book, section: Section): boolean {
  if (section === 'documentos') return book.library_section === 'documentos'
  if (section === 'patristica') return book.library_section === 'patristica' || Boolean(book.patristic_tradition)
  return Boolean(book.canonical_author || book.author) && book.library_section !== 'documentos'
}

function displayTitle(book: Book): string {
  return book.canonical_title || book.title
}

export default function BibliotecaScreen({ navigation }: { navigation: any }) {
  const [books, setBooks] = useState<Book[]>([])
  const [section, setSection] = useState<Section>('patristica')
  const [tradition, setTradition] = useState<TraditionFilter>('todas')
  const [filter, setFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const requestRef = useRef<AbortController | null>(null)

  const load = useCallback(async (refresh = false) => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    if (refresh) setRefreshing(true)
    else setLoading(true)
    setError('')
    try {
      const nextBooks = await listBooks(controller.signal)
      if (requestRef.current === controller) setBooks(nextBooks)
    } catch (reason) {
      if (
        requestRef.current === controller
        && !(reason instanceof ApiError && reason.code === 'ABORTED')
      ) {
        setError(reason instanceof Error ? reason.message : 'Não foi possível carregar o acervo.')
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null
        setLoading(false)
        setRefreshing(false)
      }
    }
  }, [])

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0)
    return () => {
      clearTimeout(timer)
      const request = requestRef.current
      requestRef.current = null
      request?.abort()
    }
  }, [load])

  const visibleBooks = useMemo(() => {
    const needle = normalized(filter.trim())
    return books
      .filter(book => belongsToSection(book, section))
      .filter(book => section !== 'patristica' || tradition === 'todas' || book.patristic_tradition === tradition)
      .filter(book => !needle || normalized([
        displayTitle(book),
        book.author,
        book.canonical_author,
        book.collection,
        book.edition_label,
        book.source_label,
      ].filter(Boolean).join(' ')).includes(needle))
      .sort((left, right) => {
        const authorCompare = normalized(left.canonical_author || left.author).localeCompare(normalized(right.canonical_author || right.author), 'pt-BR')
        return authorCompare || displayTitle(left).localeCompare(displayTitle(right), 'pt-BR')
      })
  }, [books, filter, section, tradition])

  const sectionCounts = useMemo(() => Object.fromEntries(
    sections.map(item => [item.id, books.filter(book => belongsToSection(book, item.id)).length]),
  ) as Record<Section, number>, [books])

  const header = (
    <View style={styles.header}>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
        {sections.map(item => (
          <TouchableOpacity
            key={item.id}
            style={[styles.chip, section === item.id && styles.chipActive]}
            onPress={() => {
              setSection(item.id)
              if (item.id !== 'patristica') setTradition('todas')
            }}
          >
            <Text style={[styles.chipText, section === item.id && styles.chipTextActive]}>{item.label}</Text>
            <Text style={styles.chipCount}>{sectionCounts[item.id] ?? 0}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {section === 'patristica' ? (
        <View style={styles.traditionPanel}>
          <Text style={styles.kicker}>Tradições e edições</Text>
          <Text style={styles.help}>
            PG, PL e PO permanecem nesta Biblioteca Patrística, junto das traduções vinculadas.
          </Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
            {traditions.map(item => (
              <TouchableOpacity
                key={item.id}
                style={[styles.smallChip, tradition === item.id && styles.smallChipActive]}
                onPress={() => setTradition(item.id)}
              >
                <Text style={[styles.smallChipText, tradition === item.id && styles.chipTextActive]}>{item.label}</Text>
              </TouchableOpacity>
            ))}
          </ScrollView>
        </View>
      ) : null}

      <TextInput
        accessibilityLabel="Filtrar biblioteca"
        clearButtonMode="while-editing"
        placeholder="Filtrar por obra, autor, coleção ou edição"
        placeholderTextColor={colors.tertiary}
        style={styles.input}
        value={filter}
        onChangeText={setFilter}
      />
      <Text style={styles.resultCount}>{visibleBooks.length} {visibleBooks.length === 1 ? 'obra' : 'obras'}</Text>
      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity onPress={() => void load()}><Text style={styles.retry}>Tentar novamente</Text></TouchableOpacity>
        </View>
      ) : null}
    </View>
  )

  if (loading && books.length === 0) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.gold} />
        <Text style={styles.help}>Carregando o catálogo…</Text>
      </View>
    )
  }

  return (
    <FlatList
      style={styles.root}
      contentContainerStyle={styles.container}
      data={visibleBooks}
      keyExtractor={item => String(item.id)}
      ListHeaderComponent={header}
      initialNumToRender={10}
      maxToRenderPerBatch={10}
      updateCellsBatchingPeriod={40}
      windowSize={7}
      removeClippedSubviews
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} tintColor={colors.gold} />}
      ListEmptyComponent={!error ? <View style={styles.empty}><Text style={styles.help}>Nenhuma obra corresponde a este filtro.</Text></View> : null}
      renderItem={({ item }) => (
        <TouchableOpacity
          accessibilityRole="button"
          style={styles.card}
          onPress={() => navigation.navigate('BookDetail', { bookId: item.id })}
        >
          <View style={styles.cardTop}>
            {item.collection ? <Text style={styles.collection}>{item.collection}</Text> : null}
            {item.is_primary_source ? <Text style={styles.primary}>Fonte primária</Text> : null}
          </View>
          <Text style={styles.title} numberOfLines={3}>{displayTitle(item)}</Text>
          {item.canonical_author || item.author ? (
            <Text style={styles.author}>{item.canonical_author || item.author}</Text>
          ) : null}
          <View style={styles.metaRow}>
            {item.edition_label ? <Text style={styles.meta}>{item.edition_label}</Text> : null}
            {item.language ? <Text style={styles.meta}>{formatLanguage(item.language)}</Text> : null}
            {typeof item.chunk_count === 'number' ? <Text style={styles.meta}>{item.chunk_count.toLocaleString('pt-BR')} trechos</Text> : null}
          </View>
        </TouchableOpacity>
      )}
    />
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 14, paddingBottom: 40 },
  center: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', gap: 12 },
  header: { gap: 11, marginBottom: 10 },
  chips: { gap: 7, paddingRight: 12 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 7, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, borderRadius: 8, paddingHorizontal: 11, paddingVertical: 9 },
  chipActive: { borderColor: '#6b5721', backgroundColor: colors.goldSoft },
  chipText: { color: colors.muted, fontSize: 12, fontWeight: '700' },
  chipTextActive: { color: colors.gold },
  chipCount: { color: colors.tertiary, fontSize: 10, backgroundColor: colors.background, borderRadius: 10, paddingHorizontal: 5, paddingVertical: 1 },
  traditionPanel: { gap: 8, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 12 },
  kicker: { color: colors.gold, textTransform: 'uppercase', fontWeight: '900', fontSize: 11, letterSpacing: 0.7 },
  help: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  smallChip: { borderWidth: 1, borderColor: colors.border, borderRadius: 7, paddingHorizontal: 10, paddingVertical: 7 },
  smallChipActive: { borderColor: '#6b5721', backgroundColor: colors.goldSoft },
  smallChipText: { color: colors.muted, fontSize: 11, fontWeight: '700' },
  input: { minHeight: 46, borderWidth: 1, borderColor: colors.border, borderRadius: 8, backgroundColor: colors.card, color: colors.text, paddingHorizontal: 12 },
  resultCount: { color: colors.tertiary, fontSize: 12 },
  errorBox: { backgroundColor: '#7f1d1d44', borderWidth: 1, borderColor: '#991b1b', borderRadius: 8, padding: 12, gap: 6 },
  errorText: { color: '#fecaca' },
  retry: { color: colors.gold, fontWeight: '800' },
  card: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 13, gap: 5, marginBottom: 9 },
  cardTop: { flexDirection: 'row', flexWrap: 'wrap', gap: 7 },
  collection: { color: colors.gold, borderWidth: 1, borderColor: '#6b5721', borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, fontWeight: '900', fontSize: 10 },
  primary: { color: '#6ee7b7', fontSize: 10, fontWeight: '800' },
  title: { color: colors.text, fontSize: 15, fontWeight: '800', lineHeight: 20 },
  author: { color: colors.gold, fontSize: 13 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  meta: { color: colors.tertiary, fontSize: 11 },
  empty: { alignItems: 'center', padding: 28 },
})
