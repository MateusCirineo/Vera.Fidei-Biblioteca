import { useCallback, useEffect, useRef, useState } from 'react'
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'

import { useAuth } from '../auth/AuthContext'
import { ApiError, getBook, type Book } from '../lib/api'
import { formatLanguage } from '../lib/language'
import { canOpenLibraryPdf } from '../lib/plan'
import { colors } from '../lib/theme'

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metaItem}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={styles.metaValue}>{value}</Text>
    </View>
  )
}

export default function BookDetailScreen({ route, navigation }: { route: any; navigation: any }) {
  const bookId = Number(route.params?.bookId)
  const { user } = useAuth()
  const [book, setBook] = useState<Book | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const requestRef = useRef<AbortController | null>(null)

  const load = useCallback(async () => {
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError('')
    try {
      const nextBook = await getBook(bookId, controller.signal)
      if (requestRef.current === controller) setBook(nextBook)
    } catch (reason) {
      if (
        requestRef.current === controller
        && !(reason instanceof ApiError && reason.code === 'ABORTED')
      ) {
        setError(reason instanceof Error ? reason.message : 'Não foi possível carregar a obra.')
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null
        setLoading(false)
      }
    }
  }, [bookId])

  useEffect(() => {
    const timer = setTimeout(() => void load(), 0)
    return () => {
      clearTimeout(timer)
      const request = requestRef.current
      requestRef.current = null
      request?.abort()
    }
  }, [load])

  function openFile(fileId: number, page: number) {
    if (!canOpenLibraryPdf(user?.plan)) {
      Alert.alert(
        'PDF completo no Apologeta',
        'Os metadados e a localização continuam acessíveis. A leitura do PDF digitalizado exige o plano Apologeta.',
        [
          { text: 'Agora não', style: 'cancel' },
          { text: 'Ver planos', onPress: () => navigation.navigate('ContaWeb', { destination: 'plans' }) },
        ],
      )
      return
    }
    navigation.navigate('LeitorPdf', { fileId, page })
  }

  if (loading && !book) {
    return <View style={styles.center}><ActivityIndicator size="large" color={colors.gold} /></View>
  }

  if (error || !book) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error || 'Obra não encontrada.'}</Text>
        <TouchableOpacity style={styles.button} onPress={() => void load()}><Text style={styles.buttonText}>Tentar novamente</Text></TouchableOpacity>
        <TouchableOpacity style={styles.button} onPress={() => navigation.goBack()}><Text style={styles.buttonText}>Voltar</Text></TouchableOpacity>
      </View>
    )
  }

  const title = book.canonical_title || book.title
  const author = book.canonical_author || book.author

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <TouchableOpacity onPress={() => navigation.goBack()}><Text style={styles.back}>‹ Voltar à biblioteca</Text></TouchableOpacity>
      <View style={styles.titleBlock}>
        <View style={styles.badges}>
          {book.collection ? <Text style={styles.collection}>{book.collection}</Text> : null}
          {book.is_primary_source ? <Text style={styles.primary}>Fonte primária</Text> : null}
        </View>
        <Text style={styles.title}>{title}</Text>
        {author ? <Text style={styles.author}>{author}</Text> : null}
      </View>

      <View style={styles.metaGrid}>
        {book.edition_label ? <Meta label="Edição" value={book.edition_label} /> : null}
        {book.language ? <Meta label="Idioma" value={formatLanguage(book.language)} /> : null}
        {book.source_label ? <Meta label="Fonte" value={book.source_label} /> : null}
        {book.document_year ? <Meta label="Ano" value={String(book.document_year)} /> : null}
        {typeof book.chunk_count === 'number' ? <Meta label="Trechos indexados" value={book.chunk_count.toLocaleString('pt-BR')} /> : null}
      </View>

      <Text style={styles.sectionTitle}>Arquivos e edições</Text>
      {book.files?.length ? book.files.map(file => (
        <View key={file.id} style={styles.fileCard}>
          <Text style={styles.fileName}>{file.original_filename}</Text>
          <View style={styles.fileMeta}>
            {file.volume_number ? <Text style={styles.small}>Vol. {file.volume_number}</Text> : null}
            {file.editor ? <Text style={styles.small}>Ed. {file.editor}</Text> : null}
            {file.translator ? <Text style={styles.small}>Trad. {file.translator}</Text> : null}
            {file.start_page && file.start_page > 1 ? <Text style={styles.small}>Início na p. {file.start_page}</Text> : null}
          </View>
          <TouchableOpacity style={styles.pdfButton} onPress={() => openFile(file.id, file.start_page ?? 1)}>
            <Text style={styles.pdfButtonText}>{canOpenLibraryPdf(user?.plan) ? 'Abrir PDF' : 'PDF no plano Apologeta'}</Text>
          </TouchableOpacity>
        </View>
      )) : (
        <View style={styles.empty}><Text style={styles.emptyText}>Nenhum arquivo PDF está vinculado a esta obra.</Text></View>
      )}

      <Text style={styles.note}>
        O visualizador abre no domínio oficial do Vera Fidei e respeita sua sessão e seu plano. Nenhuma credencial é colocada no endereço do PDF.
      </Text>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 16, paddingBottom: 44, gap: 14 },
  center: { flex: 1, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center', gap: 10, padding: 22 },
  error: { color: '#fecaca', textAlign: 'center' },
  button: { borderWidth: 1, borderColor: '#6b5721', borderRadius: 7, paddingHorizontal: 15, paddingVertical: 9 },
  buttonText: { color: colors.gold, fontWeight: '800' },
  back: { color: colors.gold, fontWeight: '800', paddingVertical: 4 },
  titleBlock: { gap: 6 },
  badges: { flexDirection: 'row', gap: 8, alignItems: 'center' },
  collection: { color: colors.gold, borderWidth: 1, borderColor: '#6b5721', borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2, fontSize: 10, fontWeight: '900' },
  primary: { color: '#6ee7b7', fontSize: 11, fontWeight: '800' },
  title: { color: colors.text, fontSize: 24, fontWeight: '900', lineHeight: 31 },
  author: { color: colors.gold, fontSize: 15 },
  metaGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 13 },
  metaItem: { minWidth: '44%', flexGrow: 1, flexBasis: 130 },
  metaLabel: { color: colors.tertiary, fontSize: 10, fontWeight: '800', textTransform: 'uppercase' },
  metaValue: { color: colors.text, fontSize: 13, marginTop: 3 },
  sectionTitle: { color: colors.text, fontSize: 18, fontWeight: '900', marginTop: 4 },
  fileCard: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 13, gap: 8 },
  fileName: { color: colors.text, fontWeight: '800', lineHeight: 19 },
  fileMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  small: { color: colors.tertiary, fontSize: 11 },
  pdfButton: { alignSelf: 'flex-start', borderWidth: 1, borderColor: '#6b5721', borderRadius: 7, paddingHorizontal: 12, paddingVertical: 8 },
  pdfButtonText: { color: colors.gold, fontWeight: '900', fontSize: 12 },
  empty: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 18 },
  emptyText: { color: colors.muted, textAlign: 'center' },
  note: { color: colors.tertiary, fontSize: 11, lineHeight: 17, textAlign: 'center' },
})
