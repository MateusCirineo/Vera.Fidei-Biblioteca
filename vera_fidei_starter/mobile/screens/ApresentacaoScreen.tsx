import { Image, Linking, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'

const SOCIAL = [
  { label: 'TikTok', value: '@mattcirineo, o católico', href: 'https://www.tiktok.com/@mattcirineo.catolico' },
  { label: 'Instagram', value: '@vera.fidei', href: 'https://www.instagram.com/vera.fidei' },
  { label: 'YouTube', value: '@mattcirineo', href: 'https://www.youtube.com/@mattcirineo' },
]

const FEATURES = ['Fontes primárias', 'Tradição católica', 'Verificação de citações']

const DAILY_PATHS = [
  {
    title: 'Lectio com fontes',
    desc: 'Leia, anote e aprofunde com Padres da Igreja, Catecismo e documentos.',
  },
  {
    title: 'Oração e estudo',
    desc: 'Use a nova aba Orações como rotina espiritual ligada ao acervo.',
  },
  {
    title: 'Santo do dia',
    desc: 'Acompanhe biografia, virtude principal e caminhos de aprofundamento.',
  },
]

const HOW_IT_WORKS = [
  {
    title: 'Busca lexical',
    desc: 'Encontra correspondências exatas ou próximas respeitando as características do latim, do grego patrístico e de outras línguas presentes nas coleções PL, PG e PO.',
  },
  {
    title: 'Busca semântica',
    desc: 'Identifica passagens equivalentes em significado, mesmo com traduções, variações editoriais ou diferenças entre edições patrísticas e documentos do Magistério.',
  },
  {
    title: 'Classificação determinística',
    desc: 'A análise é feita por critérios objetivos, garantindo consistência, rastreabilidade e fidelidade às fontes — sem interpretações subjetivas.',
  },
  {
    title: 'Proveniência completa',
    desc: 'Cada resultado apresenta coleção, volume, coluna, edição, idioma e permite acesso direto ao trecho no documento original.',
  },
]

const ACERVO = [
  { code: 'PL', label: 'Patrologia Latina', desc: 'textos em latim dos Padres da Igreja' },
  { code: 'PG', label: 'Patrologia Grega', desc: 'textos patrísticos em grego' },
  { code: 'PO', label: 'Patrologia Orientalis', desc: 'textos orientais em línguas antigas' },
  { code: 'CONC', label: 'Concílios', desc: 'documentos conciliares ecumênicos e regionais' },
  { code: 'MAG', label: 'Magistério', desc: 'encíclicas, bulas papais e documentos oficiais' },
]

export default function ApresentacaoScreen() {
  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>

      {/* Cover card */}
      <View style={styles.cover}>
        <View style={styles.coverTop}>
          <Image
            source={require('../assets/logo.png')}
            style={styles.logo}
            resizeMode="contain"
          />
          <Text style={styles.coverBy}>MattCirineo</Text>
          <Text style={styles.coverTitle}>Vera.Fidei</Text>
          <Text style={styles.coverSub}>
            Biblioteca Católica Digital com Fontes Primárias e Verificação de Citações
          </Text>
        </View>

        <View style={styles.coverBody}>
          <View style={styles.blockquote}>
            <Text style={styles.blockquoteText}>Eucharistia via mea ad Caelum est</Text>
          </View>

          <View style={styles.socialGrid}>
            {SOCIAL.map(s => (
              <TouchableOpacity key={s.label} style={styles.socialCard} onPress={() => Linking.openURL(s.href)}>
                <Text style={styles.socialLabel}>{s.label}</Text>
                <Text style={styles.socialValue}>{s.value}</Text>
              </TouchableOpacity>
            ))}
          </View>

          <View style={styles.featureRow}>
            {FEATURES.map(f => (
              <View key={f} style={styles.featureBadge}>
                <Text style={styles.featureText}>{f}</Text>
              </View>
            ))}
          </View>
        </View>
      </View>

      <View style={styles.pathSection}>
        <Text style={styles.pathTitle}>Novos caminhos de uso</Text>
        <Text style={styles.pathIntro}>
          O Vera.Fidei agora ganha uma camada diária sem perder sua identidade: oração, santos e estudo conectados às fontes.
        </Text>
        <View style={styles.pathGrid}>
          {DAILY_PATHS.map(path => (
            <View key={path.title} style={styles.pathCard}>
              <Text style={styles.pathCardTitle}>{path.title}</Text>
              <Text style={styles.pathCardDesc}>{path.desc}</Text>
            </View>
          ))}
        </View>
      </View>

      {/* Intro */}
      <Text style={styles.intro}>
        Uma biblioteca católica digital pensada para quem busca estudar, compreender e defender a fé com base em fontes autênticas.
      </Text>
      <Text style={styles.intro}>
        O Vera.Fidei reúne, em um único ambiente, obras patrísticas, documentos do Magistério e coleções clássicas da tradição da Igreja, organizadas de forma clara, acessível e fiel às edições originais.
      </Text>
      <Text style={styles.intro}>
        Integra um mecanismo de verificação de citações que confronta textos atribuídos aos Padres da Igreja com os documentos originais, auxiliando na identificação de erros, distorções ou citações fora de contexto.
      </Text>

      <View style={styles.divider} />

      {/* O que é */}
      <Text style={styles.h2}>O que é o Vera.Fidei</Text>
      <Text style={styles.body}>
        O Vera.Fidei é uma biblioteca digital católica com foco na preservação, organização e acesso às fontes primárias da tradição da Igreja.
      </Text>
      <Text style={styles.body}>
        Seu acervo é composto por obras clássicas como a Patrologia Latina (PL), a Patrologia Grega (PG) e a Patrologia Orientalis (PO), além de documentos do Magistério, concílios ecumênicos e regionais, bulas papais, encíclicas e outros textos fundamentais da tradição católica.
      </Text>

      <View style={styles.divider} />

      {/* Como funciona */}
      <Text style={styles.h2}>Como funciona</Text>
      {HOW_IT_WORKS.map(({ title, desc }) => (
        <View key={title} style={styles.howCard}>
          <View style={styles.howDot} />
          <View style={styles.howContent}>
            <Text style={styles.howTitle}>{title}</Text>
            <Text style={styles.howDesc}>{desc}</Text>
          </View>
        </View>
      ))}

      <View style={styles.divider} />

      {/* O problema */}
      <Text style={styles.h2}>O problema que resolve</Text>
      <View style={styles.problemBox}>
        <Text style={styles.problemMain}>
          A circulação de citações incorretas, incompletas ou inexistentes é cada vez mais comum, especialmente em conteúdos digitais e materiais produzidos por inteligências artificiais.
        </Text>
        <Text style={styles.problemSub}>
          O Vera.Fidei responde a esse problema oferecendo um meio confiável de verificação, permitindo confrontar qualquer citação com o texto original e identificar sua autenticidade, localização e contexto.
        </Text>
      </View>
      <Text style={styles.body}>
        O sistema prioriza sempre a fonte primária — o texto original na língua em que foi escrito — utilizando traduções apenas como apoio.
      </Text>

      <View style={styles.divider} />

      {/* Acervo */}
      <Text style={styles.h2}>Acervo</Text>
      <View style={styles.acervoGrid}>
        {ACERVO.map(({ code, label, desc }) => (
          <View key={code} style={styles.acervoCard}>
            <Text style={styles.acervoCode}>{code}</Text>
            <Text style={styles.acervoLabel}>{label}</Text>
            <Text style={styles.acervoDesc}>{desc}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.body}>
        Cada obra pode conter múltiplas edições, traduções e arquivos digitais, sempre vinculados entre si, permitindo consulta precisa e acesso direto ao trecho correspondente dentro do documento original.
      </Text>

    </ScrollView>
  )
}

const GOLD = '#c9a84c'
const WINE = '#5c1a2a'
const BG = '#111111'
const CARD = '#1a1a1a'
const BORDER = '#2a2a2a'
const TEXT = '#f5f0e8'
const MUTED = '#b8b0a0'
const TERTIARY = '#706860'

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  container: { padding: 16, paddingBottom: 48, gap: 12 },

  // Cover
  cover: { borderRadius: 12, borderWidth: 1, borderColor: '#d4af3740', overflow: 'hidden', backgroundColor: '#1a1a2e' },
  coverTop: { backgroundColor: '#2a0a1555', paddingVertical: 24, paddingHorizontal: 16, alignItems: 'center', borderBottomWidth: 1, borderBottomColor: '#d4af3730' },
  logo: { width: 180, height: 100, marginBottom: 8 },
  coverBy: { fontSize: 14, color: GOLD, fontStyle: 'italic' },
  coverTitle: { fontSize: 40, fontWeight: '700', color: '#f5f0e8', letterSpacing: 1 },
  coverSub: { fontSize: 15, fontStyle: 'italic', color: '#d4af37bb', textAlign: 'center', marginTop: 4, lineHeight: 22 },
  coverBody: { padding: 16, gap: 12 },
  blockquote: { borderLeftWidth: 2, borderLeftColor: GOLD, paddingLeft: 12 },
  blockquoteText: { fontSize: 17, fontStyle: 'italic', color: '#f5f0e8', lineHeight: 24 },
  socialGrid: { flexDirection: 'row', gap: 8 },
  socialCard: { flex: 1, borderWidth: 1, borderColor: '#ffffff20', backgroundColor: '#ffffff0a', borderRadius: 8, padding: 8 },
  socialLabel: { fontSize: 10, color: '#9ca3af' },
  socialValue: { fontSize: 12, fontWeight: '600', color: '#e5e7eb', marginTop: 2 },
  featureRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  featureBadge: { borderWidth: 1, borderColor: '#d4af3730', backgroundColor: '#d4af3710', borderRadius: 6, paddingHorizontal: 10, paddingVertical: 5 },
  featureText: { fontSize: 11, fontWeight: '600', color: GOLD },

  pathSection: { backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, borderRadius: 10, padding: 14, gap: 10 },
  pathTitle: { fontSize: 18, fontWeight: '700', color: TEXT },
  pathIntro: { fontSize: 13, color: MUTED, lineHeight: 19 },
  pathGrid: { gap: 8 },
  pathCard: { borderWidth: 1, borderColor: '#d4af3730', backgroundColor: '#d4af3710', borderRadius: 8, padding: 12 },
  pathCardTitle: { fontSize: 14, fontWeight: '700', color: TEXT },
  pathCardDesc: { fontSize: 12, color: MUTED, lineHeight: 18, marginTop: 3 },

  // Typography
  intro: { fontSize: 14, color: MUTED, lineHeight: 22 },
  divider: { height: 1, backgroundColor: BORDER, marginVertical: 8 },
  h2: { fontSize: 22, fontWeight: '700', color: TEXT, marginBottom: 4 },
  body: { fontSize: 14, color: MUTED, lineHeight: 22 },

  // How it works
  howCard: { flexDirection: 'row', gap: 12, backgroundColor: CARD, borderRadius: 10, padding: 14, borderWidth: 1, borderColor: BORDER },
  howDot: { width: 6, height: 6, borderRadius: 3, backgroundColor: GOLD, marginTop: 6, flexShrink: 0 },
  howContent: { flex: 1 },
  howTitle: { fontSize: 14, fontWeight: '600', color: TEXT, marginBottom: 2 },
  howDesc: { fontSize: 13, color: MUTED, lineHeight: 20 },

  // Problem box
  problemBox: { backgroundColor: WINE + '15', borderWidth: 1, borderColor: WINE + '40', borderRadius: 10, padding: 14, gap: 8 },
  problemMain: { fontSize: 14, fontWeight: '600', color: TEXT, lineHeight: 20 },
  problemSub: { fontSize: 13, color: MUTED, lineHeight: 20 },

  // Acervo
  acervoGrid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  acervoCard: { width: '47%', backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, borderRadius: 10, padding: 12 },
  acervoCode: { fontSize: 11, fontWeight: '700', color: GOLD, fontFamily: 'monospace', marginBottom: 2 },
  acervoLabel: { fontSize: 13, fontWeight: '600', color: TEXT },
  acervoDesc: { fontSize: 11, color: TERTIARY, marginTop: 2, lineHeight: 16 },
})
