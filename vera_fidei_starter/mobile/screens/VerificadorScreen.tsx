import { useState } from 'react'
import {
  ActivityIndicator,
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'
import { verifyCitation, type VerifyResponse, type StatusCode } from '../lib/api'
import { formatLanguage } from '../lib/language'

const STATUS_COLOR: Record<StatusCode, string> = {
  CONFIRMADA_EXATA:       '#16a34a',
  CORRESPONDENCIA_FORTE:  '#ca8a04',
  ATRIBUICAO_DUVIDOSA:    '#ea580c',
  TRADUCAO_FIEL:          '#0891b2',
  TRADUCAO_IMPRECISA:     '#d97706',
  PARAFRASE_PLAUSIVEL:    '#7c3aed',
  NAO_ENCONTRADA:         '#dc2626',
}

function ReferenceCard({ result }: { result: VerifyResponse }) {
  const ref = result.reference
  if (!ref) return null

  const isPrimary = ref.is_primary_source
  const locationParts: string[] = []
  if (ref.collection) {
    let loc = ref.collection
    if (ref.volume) loc += ` vol. ${ref.volume}`
    locationParts.push(loc)
  }
  if (ref.column_start) locationParts.push(`col. ${ref.column_start}`)
  if (ref.chapter_or_section) locationParts.push(ref.chapter_or_section)
  if (ref.pdf_page) locationParts.push(`p. ${ref.pdf_page}`)

  return (
    <View style={[styles.refCard, isPrimary ? styles.refCardPrimary : styles.refCardSecondary]}>
      <View style={styles.refHeader}>
        <View style={[styles.refBadge, isPrimary ? styles.refBadgePrimary : styles.refBadgeSecondary]}>
          <Text style={[styles.refBadgeText, isPrimary ? styles.refBadgeTextPrimary : styles.refBadgeTextSecondary]}>
            {isPrimary ? 'Fonte Primária' : 'Tradução'}
          </Text>
        </View>
        {ref.language && (
          <Text style={styles.refLang}>{formatLanguage(ref.language)}</Text>
        )}
      </View>

      {(ref.edition_label || locationParts.length > 0) && (
        <View style={{ gap: 2 }}>
          {ref.edition_label && (
            <Text style={styles.refEdition}>
              {ref.edition_label}
              {ref.source_label ? (
                <Text style={styles.refSource}> · {ref.source_label}</Text>
              ) : null}
            </Text>
          )}
          {locationParts.length > 0 && (
            <Text style={styles.refLocation}>{locationParts.join(' · ')}</Text>
          )}
        </View>
      )}

      <View style={styles.refMetaRow}>
        <Text style={styles.refMeta}>
          Editor: <Text style={styles.refMetaVal}>{ref.editor ?? '—'}</Text>
        </Text>
        <Text style={styles.refMeta}>
          Tradutor: <Text style={styles.refMetaVal}>{ref.translator ?? '—'}</Text>
        </Text>
      </View>
    </View>
  )
}

export default function VerificadorScreen() {
  const [quote, setQuote] = useState('')
  const [author, setAuthor] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<VerifyResponse | null>(null)

  async function handleVerify() {
    if (!quote.trim() || !author.trim()) {
      Alert.alert('Preencha a citação e o autor.')
      return
    }
    setLoading(true)
    setResult(null)
    try {
      const res = await verifyCitation({ quote: quote.trim(), attributed_to: author.trim() })
      setResult(res)
    } catch (e: any) {
      Alert.alert('Erro', e.message ?? 'Falha na verificação.')
    } finally {
      setLoading(false)
    }
  }

  const statusColor = result
    ? (STATUS_COLOR[result.status_code] ?? '#6b7280')
    : '#6b7280'

  const notFound = result?.status_code === 'NAO_ENCONTRADA'

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">

        <Text style={styles.label}>Citação</Text>
        <TextInput
          style={[styles.input, styles.inputMulti]}
          placeholder="Cole aqui a citação..."
          placeholderTextColor="#9ca3af"
          multiline
          numberOfLines={4}
          value={quote}
          onChangeText={setQuote}
        />

        <Text style={styles.label}>Atribuída a</Text>
        <TextInput
          style={styles.input}
          placeholder="Ex: Santo Agostinho"
          placeholderTextColor="#9ca3af"
          value={author}
          onChangeText={setAuthor}
          returnKeyType="done"
          onSubmitEditing={handleVerify}
        />

        <TouchableOpacity style={styles.btn} onPress={handleVerify} disabled={loading}>
          {loading
            ? <><ActivityIndicator color="#fff" /><Text style={[styles.btnText, { marginLeft: 8 }]}>Verificando...</Text></>
            : <Text style={styles.btnText}>Verificar Citação</Text>}
        </TouchableOpacity>

        {loading && (
          <Text style={styles.hint}>A busca semântica pode levar alguns segundos.</Text>
        )}

        {result && (
          <View style={styles.card}>

            <Text style={[styles.statusLabel, { color: statusColor }]}>{result.label}</Text>
            <Text style={styles.confidence}>Confiança: {result.confidence}</Text>

            {!notFound && (result.author || result.work) && (
              <View style={{ marginTop: 4 }}>
                {result.author && <Text style={styles.workAuthor}>{result.author}</Text>}
                {result.work && <Text style={styles.workTitle}>{result.work}</Text>}
              </View>
            )}

            {!notFound && <ReferenceCard result={result} />}

            {!notFound && result.translation_fidelity && result.translation_fidelity !== 'nao_encontrada' && (
              <View style={[
                styles.fidelityBadge,
                result.translation_fidelity === 'fiel' ? styles.fidelityFiel : styles.fidelityImprecisa,
              ]}>
                <Text style={[
                  styles.fidelityText,
                  result.translation_fidelity === 'fiel' ? styles.fidelityFielText : styles.fidelityImprecisaText,
                ]}>
                  {result.translation_fidelity === 'fiel' ? '✓ Tradução fiel' : '⚠ Tradução imprecisa'}
                </Text>
              </View>
            )}

            {!notFound && result.matched_excerpt && (
              <View style={styles.textBlock}>
                <Text style={styles.textBlockLabel}>
                  Texto original ({formatLanguage(result.original_language) || 'latim'})
                </Text>
                {result.context_before ? (
                  <Text style={styles.contextText} numberOfLines={3}>{result.context_before}</Text>
                ) : null}
                <View style={styles.excerpt}>
                  <Text style={styles.excerptText}>"{result.matched_excerpt}"</Text>
                </View>
                {result.context_after ? (
                  <Text style={styles.contextText} numberOfLines={3}>{result.context_after}</Text>
                ) : null}
              </View>
            )}

            {!notFound && result.matched_translation && (
              <View style={styles.textBlock}>
                <Text style={styles.textBlockLabel}>
                  Tradução de referência ({formatLanguage(result.translation_language) || 'português'})
                  {(result.translator ?? result.translation_edition)
                    ? ` — ${result.translator ?? result.translation_edition}`
                    : ''}
                </Text>
                <View style={styles.excerptSecondary}>
                  <Text style={styles.excerptSecondaryText}>{result.matched_translation}</Text>
                </View>
              </View>
            )}

            {result.explanation && (
              <View style={styles.explanationBlock}>
                <Text style={styles.sectionTitle}>Análise</Text>
                <Text style={styles.explanation}>{result.explanation}</Text>
              </View>
            )}
          </View>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const GOLD = '#c9a84c'
const DARK_BLUE = '#1e3a5f'

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#f9fafb' },
  container: { padding: 20, paddingBottom: 48 },
  label: { fontSize: 13, fontWeight: '600', color: '#374151', marginBottom: 6 },
  input: {
    backgroundColor: '#fff',
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 10,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 15,
    color: '#111827',
    marginBottom: 16,
  },
  inputMulti: { height: 100, textAlignVertical: 'top' },
  btn: {
    backgroundColor: DARK_BLUE,
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'center',
    marginBottom: 8,
  },
  btnText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  hint: { fontSize: 12, color: '#9ca3af', textAlign: 'center', marginBottom: 20 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
    borderWidth: 1,
    borderColor: '#e5e7eb',
    gap: 12,
    marginTop: 16,
  },
  statusLabel: { fontSize: 18, fontWeight: '700' },
  confidence: { fontSize: 13, color: '#6b7280' },
  workAuthor: { fontSize: 15, fontWeight: '600', color: '#111827' },
  workTitle: { fontSize: 13, fontStyle: 'italic', color: '#6b7280', marginTop: 2 },
  // Reference card
  refCard: { borderWidth: 1, borderRadius: 10, padding: 12, gap: 8 },
  refCardPrimary: { borderColor: GOLD + '66', backgroundColor: '#fefce833' },
  refCardSecondary: { borderColor: '#e5e7eb', backgroundColor: '#f9fafb' },
  refHeader: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  refBadge: { borderRadius: 20, paddingHorizontal: 10, paddingVertical: 3 },
  refBadgePrimary: { backgroundColor: GOLD + '33' },
  refBadgeSecondary: { backgroundColor: '#1d4ed822' },
  refBadgeText: { fontSize: 11, fontWeight: '700' },
  refBadgeTextPrimary: { color: GOLD },
  refBadgeTextSecondary: { color: '#1d4ed8' },
  refLang: { fontSize: 12, color: '#6b7280' },
  refEdition: { fontSize: 13, color: '#111827', fontWeight: '500' },
  refSource: { color: '#6b7280', fontWeight: '400' },
  refLocation: { fontSize: 13, color: '#6b7280' },
  refMetaRow: { flexDirection: 'row', gap: 16 },
  refMeta: { fontSize: 11, color: '#9ca3af' },
  refMetaVal: { color: '#6b7280' },
  // Fidelity
  fidelityBadge: { alignSelf: 'flex-start', borderRadius: 20, paddingHorizontal: 10, paddingVertical: 4 },
  fidelityFiel: { backgroundColor: '#16a34a22' },
  fidelityImprecisa: { backgroundColor: '#d9770622' },
  fidelityText: { fontSize: 12, fontWeight: '700' },
  fidelityFielText: { color: '#16a34a' },
  fidelityImprecisaText: { color: '#d97706' },
  // Text blocks
  textBlock: { backgroundColor: '#f9fafb', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, padding: 12, gap: 6 },
  textBlockLabel: { fontSize: 10, fontWeight: '700', color: '#9ca3af', textTransform: 'uppercase', letterSpacing: 0.8 },
  contextText: { fontSize: 12, color: '#9ca3af', lineHeight: 18 },
  excerpt: { borderLeftWidth: 2, borderLeftColor: GOLD, paddingLeft: 10 },
  excerptText: { fontSize: 14, color: '#374151', fontStyle: 'italic', lineHeight: 22 },
  excerptSecondary: { borderLeftWidth: 2, borderLeftColor: GOLD + '88', paddingLeft: 10 },
  excerptSecondaryText: { fontSize: 14, color: '#4b5563', lineHeight: 22 },
  // Explanation
  explanationBlock: { backgroundColor: '#f9fafb', borderWidth: 1, borderColor: '#e5e7eb', borderRadius: 10, padding: 12 },
  sectionTitle: { fontSize: 11, fontWeight: '700', color: DARK_BLUE, marginBottom: 6, textTransform: 'uppercase', letterSpacing: 0.8 },
  explanation: { fontSize: 14, color: '#374151', lineHeight: 22 },
})
