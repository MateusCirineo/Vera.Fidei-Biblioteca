import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  FlatList,
  Platform,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'

import { useAuth } from '../auth/AuthContext'
import { ApiError, searchCorpus, type SearchResult } from '../lib/api'
import { plansRouteForMode, subscriptionGatePolicy } from '../lib/distribution-policy'
import { canOpenLibraryPdf } from '../lib/plan'
import { DISTRIBUTION_MODE } from '../lib/runtime-config'
import { colors } from '../lib/theme'

function resultKey(item: SearchResult): string {
  return String(item.chunk_id)
}

export default function SearchScreen({ route, navigation }: { route: any; navigation: any }) {
  const { user } = useAuth()
  const [query, setQuery] = useState('')
  const [submittedQuery, setSubmittedQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [nextCursor, setNextCursor] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [error, setError] = useState('')
  const [quotaBlocked, setQuotaBlocked] = useState(false)
  const [failedCursor, setFailedCursor] = useState<string | null>(null)
  const requestRef = useRef<AbortController | null>(null)
  const paginationCursorRef = useRef<string | null>(null)
  const consumedCursorsRef = useRef(new Set<string>())

  const runSearch = useCallback(async (term: string, cursor = '', append = false) => {
    const clean = term.trim()
    if (clean.length < 2) {
      setError('Digite ao menos 2 caracteres.')
      return
    }
    if (append) {
      if (
        !cursor
        || requestRef.current
        || paginationCursorRef.current === cursor
        || consumedCursorsRef.current.has(cursor)
      ) return
      paginationCursorRef.current = cursor
    } else {
      requestRef.current?.abort()
      paginationCursorRef.current = null
      consumedCursorsRef.current.clear()
    }
    const controller = new AbortController()
    requestRef.current = controller
    if (append) setLoadingMore(true)
    else setLoading(true)
    setError('')
    setQuotaBlocked(false)
    setFailedCursor(null)
    if (!append) {
      setSubmittedQuery(clean)
      setResults([])
      setNextCursor(null)
    }
    try {
      const response = await searchCorpus(clean, cursor, controller.signal)
      if (requestRef.current !== controller) return
      setResults(previous => {
        if (!append) return response.results
        const known = new Set(previous.map(item => item.chunk_id))
        return [...previous, ...response.results.filter(item => !known.has(item.chunk_id))]
      })
      if (append) consumedCursorsRef.current.add(cursor)
      const candidate = response.has_more ? response.next_cursor : null
      setNextCursor(candidate && !consumedCursorsRef.current.has(candidate) ? candidate : null)
    } catch (reason) {
      if (
        requestRef.current === controller
        && !(reason instanceof ApiError && reason.code === 'ABORTED')
      ) {
        const quotaReached = reason instanceof ApiError && reason.code === 'QUOTA_EXCEEDED'
        setQuotaBlocked(quotaReached)
        setError(
          quotaReached
            ? subscriptionGatePolicy(DISTRIBUTION_MODE, 'search').message
            : reason instanceof Error ? reason.message : 'A pesquisa falhou.',
        )
        setFailedCursor(append ? cursor : null)
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null
        if (append) {
          paginationCursorRef.current = null
          setLoadingMore(false)
        } else {
          setLoading(false)
        }
      }
    }
  }, [])

  useEffect(() => () => {
    const request = requestRef.current
    requestRef.current = null
    paginationCursorRef.current = null
    request?.abort()
  }, [])

  useEffect(() => {
    const initial = typeof route.params?.initialQuery === 'string' ? route.params.initialQuery.trim() : ''
    if (!initial) return
    const timer = setTimeout(() => {
      setQuery(initial)
      void runSearch(initial)
      navigation.setParams({ initialQuery: undefined })
    }, 0)
    return () => clearTimeout(timer)
  }, [navigation, route.params?.initialQuery, runSearch])

  function openResult(item: SearchResult) {
    if (!item.book_file_id) return
    if (!canOpenLibraryPdf(user?.plan)) {
      const gate = subscriptionGatePolicy(DISTRIBUTION_MODE, 'pdf')
      const plansRoute = plansRouteForMode(DISTRIBUTION_MODE, Platform.OS)
      Alert.alert(
        gate.title,
        gate.message,
        gate.showPlansAction && plansRoute
          ? [
            { text: 'Agora não', style: 'cancel' },
            {
              text: 'Ver planos',
              onPress: () => plansRoute === 'PlayPlans'
                ? navigation.navigate('PlayPlans')
                : navigation.navigate('ContaWeb', { destination: 'plans' }),
            },
          ]
          : [{ text: 'Entendi' }],
      )
      return
    }
    navigation.navigate('LeitorPdf', { fileId: item.book_file_id, page: item.pdf_page ?? 1 })
  }

  const header = (
    <View style={styles.header}>
      <Text style={styles.title}>Citações dos Padres e do acervo</Text>
      <Text style={styles.intro}>
        Pesquise palavra, frase ou tema. Resultados citáveis aparecem com obra, edição e página; OCR não conferido permanece somente como localização.
      </Text>
      <View style={styles.searchRow}>
        <TextInput
          accessibilityLabel="Texto da pesquisa"
          autoCapitalize="none"
          enterKeyHint="search"
          placeholder="Ex.: Eucaristia"
          placeholderTextColor={colors.tertiary}
          style={styles.input}
          value={query}
          onChangeText={setQuery}
          onSubmitEditing={() => void runSearch(query)}
        />
        <TouchableOpacity style={styles.searchButton} disabled={loading} onPress={() => void runSearch(query)}>
          {loading ? <ActivityIndicator color="#111" /> : <Text style={styles.searchButtonText}>Buscar</Text>}
        </TouchableOpacity>
      </View>
      {submittedQuery && !loading && !error ? (
        <Text style={styles.summary}>
          {results.length} {results.length === 1 ? 'passagem carregada' : 'passagens carregadas'} para “{submittedQuery}”
          {nextCursor ? ' · continue rolando para carregar mais' : ''}
        </Text>
      ) : null}
      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
          {quotaBlocked && plansRouteForMode(DISTRIBUTION_MODE, Platform.OS) ? (
            <TouchableOpacity onPress={() => {
              const plansRoute = plansRouteForMode(DISTRIBUTION_MODE, Platform.OS)
              if (plansRoute === 'PlayPlans') navigation.navigate('PlayPlans')
              else if (plansRoute === 'ContaWeb') navigation.navigate('ContaWeb', { destination: 'plans' })
            }}>
              <Text style={styles.retry}>Ver planos</Text>
            </TouchableOpacity>
          ) : null}
          {submittedQuery ? (
            <TouchableOpacity onPress={() => void runSearch(submittedQuery, failedCursor ?? '', Boolean(failedCursor))}>
              <Text style={styles.retry}>Tentar novamente</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : null}
    </View>
  )

  return (
    <FlatList
      style={styles.root}
      contentContainerStyle={styles.container}
      keyboardShouldPersistTaps="handled"
      data={results}
      keyExtractor={resultKey}
      ListHeaderComponent={header}
      initialNumToRender={8}
      maxToRenderPerBatch={8}
      windowSize={7}
      removeClippedSubviews
      onEndReachedThreshold={0.45}
      onEndReached={() => {
        if (
          nextCursor
          && !loadingMore
          && !loading
          && !error
          && !requestRef.current
          && !paginationCursorRef.current
          && !consumedCursorsRef.current.has(nextCursor)
        ) void runSearch(submittedQuery, nextCursor, true)
      }}
      ListEmptyComponent={submittedQuery && !loading && !error ? (
        <View style={styles.empty}><Text style={styles.emptyText}>Nenhuma passagem citável foi encontrada.</Text></View>
      ) : null}
      ListFooterComponent={loadingMore ? <ActivityIndicator style={styles.footer} color={colors.gold} /> : <View style={styles.footerSpace} />}
      renderItem={({ item }) => (
        <View style={styles.card}>
          <Text style={styles.author}>{item.chunk_author || item.author || 'Autor não informado'}</Text>
          <Text style={styles.work}>{item.work_title || item.edition_label || 'Obra não informada'}</Text>
          <View style={styles.metaRow}>
            {item.collection ? <Text style={styles.badge}>{item.collection}</Text> : null}
            {item.pdf_page ? <Text style={styles.meta}>p. {item.pdf_page}</Text> : null}
            {item.translator ? <Text style={styles.meta}>Trad. {item.translator}</Text> : null}
          </View>
          <Text selectable style={styles.excerpt}>{item.text}</Text>
          <Text style={styles.fidelity}>{item.source_fidelity_label}</Text>
          {item.source_warning ? <Text style={styles.warning}>{item.source_warning}</Text> : null}
          {item.book_file_id ? (
            <TouchableOpacity style={styles.pdfButton} onPress={() => openResult(item)}>
              <Text style={styles.pdfButtonText}>{canOpenLibraryPdf(user?.plan) ? 'Conferir no PDF' : 'Localização no PDF'}</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      )}
    />
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 14, paddingBottom: 36, gap: 10 },
  header: { gap: 10, marginBottom: 2 },
  title: { color: colors.gold, fontSize: 16, fontWeight: '900', textTransform: 'uppercase' },
  intro: { color: colors.muted, fontSize: 13, lineHeight: 19 },
  searchRow: { flexDirection: 'row', gap: 8 },
  input: { flex: 1, minHeight: 48, borderWidth: 1, borderColor: colors.border, borderRadius: 8, backgroundColor: '#202636', color: '#fff', paddingHorizontal: 12, fontSize: 15 },
  searchButton: { minWidth: 76, minHeight: 48, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.gold, borderRadius: 8, paddingHorizontal: 12 },
  searchButtonText: { color: '#16120b', fontWeight: '900' },
  summary: { color: colors.muted, fontSize: 13 },
  errorBox: { backgroundColor: '#7f1d1d44', borderColor: '#991b1b', borderWidth: 1, borderRadius: 8, padding: 12, gap: 6 },
  errorText: { color: '#fecaca', lineHeight: 19 },
  retry: { color: colors.gold, fontWeight: '800' },
  card: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 13, gap: 7, marginBottom: 10 },
  author: { color: colors.gold, fontWeight: '900', fontSize: 14 },
  work: { color: colors.muted, fontStyle: 'italic', fontSize: 13 },
  metaRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 7 },
  badge: { color: colors.gold, borderColor: '#6b5721', borderWidth: 1, borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, fontSize: 10, fontWeight: '800' },
  meta: { color: colors.tertiary, fontSize: 11 },
  excerpt: { color: colors.text, fontSize: 14, lineHeight: 21, borderLeftWidth: 2, borderLeftColor: '#6b5721', paddingLeft: 10 },
  fidelity: { color: '#6ee7b7', fontSize: 11, fontWeight: '700' },
  warning: { color: '#fde68a', backgroundColor: '#78350f44', borderRadius: 6, padding: 8, fontSize: 12, lineHeight: 17 },
  pdfButton: { alignSelf: 'flex-start', borderWidth: 1, borderColor: '#6b5721', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 7 },
  pdfButtonText: { color: colors.gold, fontWeight: '800', fontSize: 12 },
  empty: { padding: 28, alignItems: 'center' },
  emptyText: { color: colors.muted, textAlign: 'center' },
  footer: { padding: 18 },
  footerSpace: { height: 10 },
})
