import { useEffect, useState } from 'react'
import {
  ActivityIndicator,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native'
import { getBook, type Book } from '../lib/api'
import { formatLanguage } from '../lib/language'

const COLLECTION_LABEL: Record<string, string> = {
  PT: 'Paulus', PL: 'Migne PL', PG: 'Migne PG', PO: 'Patrologia Orientalis',
}

function MetaItem({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.metaItem}>
      <Text style={styles.metaLabel}>{label}</Text>
      <Text style={styles.metaValue}>{value}</Text>
    </View>
  )
}

export default function BookDetailScreen({ route, navigation }: { route: any; navigation: any }) {
  const { bookId } = route.params as { bookId: number }
  const [book, setBook] = useState<Book | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    getBook(bookId)
      .then(setBook)
      .catch(e => setError(e.message ?? 'Erro ao carregar obra'))
      .finally(() => setLoading(false))
  }, [bookId])

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#1e3a5f" />
      </View>
    )
  }

  if (error || !book) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>{error || 'Obra não encontrada.'}</Text>
        <TouchableOpacity style={styles.backBtn} onPress={() => navigation.goBack()}>
          <Text style={styles.backBtnText}>Voltar</Text>
        </TouchableOpacity>
      </View>
    )
  }

  const collectionDisplay = book.edition_label
    || COLLECTION_LABEL[book.collection ?? '']
    || book.collection
    || null

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>

      {/* Voltar */}
      <TouchableOpacity style={styles.backLink} onPress={() => navigation.goBack()}>
        <Text style={styles.backLinkText}>‹ Voltar à Biblioteca</Text>
      </TouchableOpacity>

      {/* Título + autor */}
      <View style={styles.titleBlock}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>{book.title}</Text>
          {book.is_primary_source && (
            <View style={styles.primaryBadge}>
              <Text style={styles.primaryBadgeText}>Fonte Primária</Text>
            </View>
          )}
        </View>
        {book.author && <Text style={styles.author}>{book.author}</Text>}
      </View>

      {/* Metadados */}
      <View style={styles.metaGrid}>
        {collectionDisplay && <MetaItem label="Coleção" value={collectionDisplay} />}
        {book.language && <MetaItem label="Idioma" value={formatLanguage(book.language)} />}
        {book.pope && <MetaItem label="Papa" value={book.pope} />}
        {book.document_year && <MetaItem label="Ano" value={String(book.document_year)} />}
        {book.source_label && <MetaItem label="Fonte" value={book.source_label} />}
        {book.chunk_count !== undefined && (
          <MetaItem label="Trechos indexados" value={String(book.chunk_count)} />
        )}
      </View>

      {/* Arquivos / Edições */}
      {book.files && book.files.length > 0 && (
        <View style={styles.filesSection}>
          <Text style={styles.filesTitle}>Arquivos / Edições</Text>
          <View style={{ gap: 8 }}>
            {book.files.map(file => (
              <View key={file.id} style={styles.fileCard}>
                <Text style={styles.fileName} numberOfLines={2}>{file.original_filename}</Text>
                <View style={styles.fileMeta}>
                  {file.volume_number && (
                    <Text style={styles.fileMetaItem}>Vol. {file.volume_number}</Text>
                  )}
                  {file.editor && (
                    <Text style={styles.fileMetaItem}>Ed. {file.editor}</Text>
                  )}
                  {file.translator && (
                    <Text style={styles.fileMetaItem}>Trad. {file.translator}</Text>
                  )}
                  <Text style={styles.fileMetaItem}>
                    {new Date(file.created_at).toLocaleDateString('pt-BR')}
                  </Text>
                </View>
              </View>
            ))}
          </View>
        </View>
      )}

      {(!book.files || book.files.length === 0) && (
        <View style={styles.noFiles}>
          <Text style={styles.noFilesText}>
            {book.source_label === 'Vatican.va'
              ? 'Documento disponível em Vatican.va — conteúdo indexado para busca e verificação.'
              : 'Nenhum arquivo PDF vinculado ainda.'}
          </Text>
        </View>
      )}

    </ScrollView>
  )
}

const GOLD = '#c9a84c'
const DARK_BLUE = '#1e3a5f'

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f9fafb' },
  container: { padding: 20, paddingBottom: 48, gap: 16 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24 },
  errorText: { fontSize: 14, color: '#dc2626', textAlign: 'center' },
  backBtn: { backgroundColor: DARK_BLUE, borderRadius: 8, paddingHorizontal: 20, paddingVertical: 10, marginTop: 8 },
  backBtnText: { color: '#fff', fontWeight: '600' },

  backLink: { paddingVertical: 4 },
  backLinkText: { fontSize: 14, color: DARK_BLUE, fontWeight: '600' },

  titleBlock: { gap: 6 },
  titleRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', gap: 8 },
  title: { fontSize: 22, fontWeight: '700', color: '#111827', lineHeight: 30, flexShrink: 1 },
  primaryBadge: { marginTop: 4, backgroundColor: GOLD + '22', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 3 },
  primaryBadgeText: { fontSize: 11, fontWeight: '700', color: GOLD },
  author: { fontSize: 15, color: '#6b7280' },

  metaGrid: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  metaItem: { width: '46%' },
  metaLabel: { fontSize: 10, fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.8, marginBottom: 2 },
  metaValue: { fontSize: 13, color: '#111827', fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace' } as any,

  filesSection: { gap: 10 },
  filesTitle: { fontSize: 18, fontWeight: '700', color: DARK_BLUE },
  fileCard: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
    padding: 14,
    gap: 6,
  },
  fileName: { fontSize: 13, color: '#111827', fontWeight: '500' },
  fileMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  fileMetaItem: { fontSize: 12, color: '#9ca3af' },

  noFiles: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#e5e7eb',
    borderRadius: 10,
    padding: 20,
    alignItems: 'center',
  },
  noFilesText: { fontSize: 13, color: '#9ca3af', textAlign: 'center', lineHeight: 20 },
})
