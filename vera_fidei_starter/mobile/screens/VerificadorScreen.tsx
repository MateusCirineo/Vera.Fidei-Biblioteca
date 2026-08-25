import { useEffect, useRef, useState } from 'react'
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

import { useAuth } from '../auth/AuthContext'
import { ApiError, verifyCitation, type StatusCode, type VerifyResponse } from '../lib/api'
import { formatLanguage } from '../lib/language'
import { canOpenLibraryPdf } from '../lib/plan'
import { colors } from '../lib/theme'

const statusColors: Record<StatusCode, string> = {
  CONFIRMADA_EXATA: '#22c55e',
  CORRESPONDENCIA_FORTE: '#eab308',
  ATRIBUICAO_DUVIDOSA: '#f97316',
  TRADUCAO_FIEL: '#06b6d4',
  TRADUCAO_IMPRECISA: '#f59e0b',
  PARAFRASE_PLAUSIVEL: '#a78bfa',
  NAO_ENCONTRADA: '#ef4444',
}

function Evidence({ title, text }: { title: string; text: string | null | undefined }) {
  if (!text) return null
  return (
    <View style={styles.evidence}>
      <Text style={styles.evidenceTitle}>{title}</Text>
      <Text selectable style={styles.evidenceText}>{text}</Text>
    </View>
  )
}

export default function VerificadorScreen({ navigation }: { navigation: any }) {
  const { user } = useAuth()
  const [quote, setQuote] = useState('')
  const [author, setAuthor] = useState('')
  const [language, setLanguage] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<VerifyResponse | null>(null)
  const requestRef = useRef<AbortController | null>(null)

  useEffect(() => () => {
    const request = requestRef.current
    requestRef.current = null
    request?.abort()
  }, [])

  async function submit() {
    if (quote.trim().length < 10 || author.trim().length < 2) {
      setError('Informe a citação completa e o autor atribuído.')
      return
    }
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    setError('')
    setResult(null)
    try {
      const nextResult = await verifyCitation({
        quote: quote.trim(),
        attributed_to: author.trim(),
        language: language.trim() || null,
      }, controller.signal)
      if (requestRef.current === controller) setResult(nextResult)
    } catch (reason) {
      if (
        requestRef.current === controller
        && !(reason instanceof ApiError && reason.code === 'ABORTED')
      ) {
        setError(reason instanceof Error ? reason.message : 'A verificação falhou.')
      }
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null
        setLoading(false)
      }
    }
  }

  function openReference() {
    const fileId = result?.reference?.pdf_file_id
    if (!fileId) return
    if (!canOpenLibraryPdf(user?.plan)) {
      Alert.alert(
        'PDF completo no Apologeta',
        'A referência textual disponível no seu plano continua visível. O PDF digitalizado exige o plano Apologeta.',
        [
          { text: 'Agora não', style: 'cancel' },
          { text: 'Ver planos', onPress: () => navigation.navigate('ContaWeb', { destination: 'plans' }) },
        ],
      )
      return
    }
    navigation.navigate('LeitorPdf', { fileId, page: result?.reference?.pdf_page ?? 1 })
  }

  const reference = result?.reference
  const location = reference ? [
    reference.collection,
    reference.volume ? `vol. ${reference.volume}` : null,
    reference.column_start ? `col. ${reference.column_start}${reference.column_end && reference.column_end !== reference.column_start ? `–${reference.column_end}` : ''}` : null,
    reference.chapter_or_section,
    reference.pdf_page ? `p. ${reference.pdf_page}` : null,
  ].filter(Boolean).join(' · ') : ''
  const translationFidelity = result?.translation_fidelity === 'fiel'
    ? 'Tradução fiel'
    : result?.translation_fidelity === 'imprecisa'
      ? 'Tradução imprecisa'
      : null

  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <View style={styles.intro}>
          <Text style={styles.title}>Verificação de citação</Text>
          <Text style={styles.help}>Confronte o texto atribuído e o autor com o acervo indexado.</Text>
        </View>

        <Text style={styles.label}>Citação a verificar</Text>
        <TextInput
          accessibilityLabel="Citação a verificar"
          multiline
          numberOfLines={7}
          placeholder="Cole aqui o texto completo…"
          placeholderTextColor={colors.tertiary}
          style={[styles.input, styles.quoteInput]}
          textAlignVertical="top"
          value={quote}
          onChangeText={setQuote}
        />
        <Text style={styles.label}>Atribuída a</Text>
        <TextInput
          accessibilityLabel="Autor atribuído"
          placeholder="Ex.: Santo Irineu de Lião"
          placeholderTextColor={colors.tertiary}
          style={styles.input}
          value={author}
          onChangeText={setAuthor}
        />
        <Text style={styles.label}>Idioma (opcional)</Text>
        <TextInput
          accessibilityLabel="Idioma opcional"
          placeholder="Ex.: Latim"
          placeholderTextColor={colors.tertiary}
          style={styles.input}
          value={language}
          onChangeText={setLanguage}
          onSubmitEditing={() => void submit()}
        />
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <TouchableOpacity style={[styles.verifyButton, loading && styles.disabled]} disabled={loading} onPress={() => void submit()}>
          {loading ? <ActivityIndicator color="#fff" /> : null}
          <Text style={styles.verifyText}>{loading ? 'Verificando…' : 'Verificar citação'}</Text>
        </TouchableOpacity>
        {loading ? <Text style={styles.wait}>A confrontação pode levar alguns segundos. Você pode cancelar saindo desta tela.</Text> : null}

        {result ? (
          <View style={styles.resultCard}>
            <View style={styles.statusRow}>
              <Text style={[styles.status, { color: statusColors[result.status_code] }]}>{result.label}</Text>
              <Text style={styles.confidence}>Confiança: {result.confidence}</Text>
            </View>
            {result.author ? <Text style={styles.resultAuthor}>{result.author}</Text> : null}
            {result.work ? <Text style={styles.resultWork}>{result.work}</Text> : null}

            {reference ? (
              <View style={styles.reference}>
                <Text style={styles.referenceType}>{reference.is_primary_source ? 'Fonte primária' : 'Edição / tradução'}</Text>
                {reference.edition_label ? <Text style={styles.referenceEdition}>{reference.edition_label}</Text> : null}
                {location ? <Text style={styles.referenceLocation}>{location}</Text> : null}
                {reference.source_label ? <Text style={styles.referenceMeta}>Fonte: {reference.source_label}</Text> : null}
                {reference.language ? <Text style={styles.referenceMeta}>{formatLanguage(reference.language)}</Text> : null}
                {result.original_language ? <Text style={styles.referenceMeta}>Idioma original: {formatLanguage(result.original_language)}</Text> : null}
                {result.source_version ? <Text style={styles.referenceMeta}>Versão da fonte: {result.source_version}</Text> : null}
                {reference.editor ? <Text style={styles.referenceMeta}>Editor: {reference.editor}</Text> : null}
                {reference.translator ? <Text style={styles.referenceMeta}>Tradutor: {reference.translator}</Text> : null}
                {reference.pdf_file_id ? (
                  <TouchableOpacity style={styles.pdfButton} onPress={openReference}>
                    <Text style={styles.pdfText}>{canOpenLibraryPdf(user?.plan) ? 'Conferir no PDF' : 'PDF no plano Apologeta'}</Text>
                  </TouchableOpacity>
                ) : null}
              </View>
            ) : null}

            <Evidence title="Trecho correspondente" text={result.matched_excerpt} />
            <Evidence title="Contexto anterior" text={result.context_before} />
            <Evidence title="Contexto posterior" text={result.context_after} />
            {translationFidelity ? (
              <Text style={[
                styles.translationFidelity,
                result.translation_fidelity === 'fiel' ? styles.translationFaithful : styles.translationImprecise,
              ]}>
                {translationFidelity}
              </Text>
            ) : null}
            <Evidence title="Tradução localizada" text={result.matched_translation} />
            <Evidence title="Análise" text={result.explanation} />

            {result.quota ? (
              <Text style={styles.quota}>
                Uso mensal: {result.quota.used}/{result.quota.limit ?? '∞'}
                {result.quota.remaining !== null ? ` · ${result.quota.remaining} restantes` : ''}
              </Text>
            ) : null}
          </View>
        ) : null}
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 15, paddingBottom: 44 },
  intro: { marginBottom: 13 },
  title: { color: colors.text, fontSize: 21, fontWeight: '900' },
  help: { color: colors.muted, marginTop: 4, lineHeight: 19 },
  label: { color: colors.muted, fontWeight: '700', marginTop: 11, marginBottom: 6 },
  input: { minHeight: 46, color: colors.text, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 8, paddingHorizontal: 12, paddingVertical: 10 },
  quoteInput: { minHeight: 142 },
  error: { color: '#fecaca', backgroundColor: '#7f1d1d44', borderRadius: 7, padding: 10, marginTop: 11 },
  verifyButton: { minHeight: 49, marginTop: 15, flexDirection: 'row', gap: 8, borderRadius: 8, backgroundColor: colors.wine, alignItems: 'center', justifyContent: 'center' },
  disabled: { opacity: 0.65 },
  verifyText: { color: '#fff', fontWeight: '900' },
  wait: { color: colors.tertiary, textAlign: 'center', fontSize: 11, lineHeight: 16, marginTop: 8 },
  resultCard: { marginTop: 18, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 14, gap: 10 },
  statusRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  status: { fontSize: 16, fontWeight: '900' },
  confidence: { color: colors.muted, fontSize: 12 },
  resultAuthor: { color: colors.gold, fontWeight: '900' },
  resultWork: { color: colors.muted, fontStyle: 'italic' },
  reference: { backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 11, gap: 4 },
  referenceType: { color: '#6ee7b7', textTransform: 'uppercase', fontWeight: '900', fontSize: 10 },
  referenceEdition: { color: colors.text, fontWeight: '800' },
  referenceLocation: { color: colors.gold, fontWeight: '700' },
  referenceMeta: { color: colors.tertiary, fontSize: 11 },
  pdfButton: { alignSelf: 'flex-start', borderWidth: 1, borderColor: '#6b5721', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 7, marginTop: 5 },
  pdfText: { color: colors.gold, fontSize: 12, fontWeight: '900' },
  evidence: { borderLeftWidth: 2, borderLeftColor: '#6b5721', paddingLeft: 10, gap: 4 },
  evidenceTitle: { color: colors.gold, fontSize: 11, fontWeight: '900', textTransform: 'uppercase' },
  evidenceText: { color: colors.text, fontSize: 14, lineHeight: 21 },
  translationFidelity: { alignSelf: 'flex-start', borderWidth: 1, borderRadius: 6, paddingHorizontal: 8, paddingVertical: 4, fontSize: 11, fontWeight: '900' },
  translationFaithful: { color: '#6ee7b7', borderColor: '#047857' },
  translationImprecise: { color: '#fde68a', borderColor: '#a16207' },
  quota: { color: colors.tertiary, fontSize: 11, textAlign: 'right', marginTop: 3 },
})
