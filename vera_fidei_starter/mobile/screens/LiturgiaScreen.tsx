import { useMemo, useState } from 'react'
import { Share, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

type LiturgiaTab = 'primeira' | 'salmo' | 'evangelho'

const GOLD = '#c9a84c'
const INK = '#2f241d'
const BLUE = '#183c5c'
const WINE = '#6f1d32'
const PAPER = '#fbf7ef'

const tabs: { id: LiturgiaTab; label: string }[] = [
  { id: 'primeira', label: '1ª Leitura' },
  { id: 'salmo', label: 'Salmo' },
  { id: 'evangelho', label: 'Evangelho' },
]

const liturgia = {
  memoria: 'São Filipe Néri, presbítero | Memória',
  tempo: 'Tempo Pascal',
  cor: 'Branca',
  referencia: 'Liturgia do dia',
  secoes: {
    primeira: {
      titulo: 'Primeira Leitura',
      referencia: 'Atos dos Apóstolos',
      conteudo: [
        'A Palavra conduz a Igreja nascente em missão, formando uma comunidade que escuta, discerne e anuncia com coragem.',
        'A leitura do dia deve ser contemplada sem pressa: primeiro pela escuta literal, depois pela pergunta espiritual, e por fim pela aplicação concreta na vida.',
      ],
    },
    salmo: {
      titulo: 'Salmo Responsorial',
      referencia: 'Resposta orante da assembleia',
      conteudo: [
        'O salmo transforma a leitura em oração. A resposta breve ajuda a guardar uma frase no coração durante o dia.',
        'Use este espaço para rezar lentamente, alternando silêncio e repetição, como no uso litúrgico.',
      ],
    },
    evangelho: {
      titulo: 'Evangelho',
      referencia: 'Aclamação e proclamação',
      conteudo: [
        'O Evangelho é o centro da meditação diária. O Vera Fidei organiza a leitura para que o texto não fique isolado, mas ligado à Tradição, aos Padres e ao Magistério.',
        'Depois da proclamação, procure uma palavra, um gesto de Cristo e uma decisão concreta para o dia.',
      ],
    },
  },
}

function formatDate(date: Date) {
  const months = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']
  return `${String(date.getDate()).padStart(2, '0')} ${months[date.getMonth()]} ${date.getFullYear()}`
}

function ActionButton({
  icon,
  label,
  onPress,
}: {
  icon: keyof typeof Ionicons.glyphMap
  label: string
  onPress: () => void
}) {
  return (
    <TouchableOpacity style={styles.actionButton} onPress={onPress} accessibilityLabel={label}>
      <Ionicons name={icon} size={18} color={INK} />
    </TouchableOpacity>
  )
}

export default function LiturgiaScreen() {
  const [active, setActive] = useState<LiturgiaTab>('primeira')
  const [fontScale, setFontScale] = useState(1)
  const today = useMemo(() => new Date(), [])
  const section = liturgia.secoes[active]

  async function shareSection() {
    await Share.share({
      message: `${section.titulo} - ${section.referencia}\n\n${section.conteudo.join('\n\n')}`,
    })
  }

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.hero}>
        <View style={styles.heroTop}>
          <View>
            <Text style={styles.kicker}>Vera.Fidei Liturgia</Text>
            <Text style={styles.heroTitle}>{formatDate(today)}</Text>
          </View>
          <View style={styles.colorBadge}>
            <Text style={styles.colorLabel}>cor litúrgica</Text>
            <Text style={styles.colorValue}>{liturgia.cor}</Text>
          </View>
        </View>
        <Text style={styles.memoria}>{liturgia.memoria}</Text>
        <View style={styles.heroMeta}>
          <View style={styles.metaPill}>
            <Ionicons name="calendar-outline" size={14} color={GOLD} />
            <Text style={styles.metaText}>{liturgia.tempo}</Text>
          </View>
          <View style={styles.metaPill}>
            <Ionicons name="book-outline" size={14} color={GOLD} />
            <Text style={styles.metaText}>{liturgia.referencia}</Text>
          </View>
        </View>
      </View>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.tabs}>
        {tabs.map(tab => {
          const selected = active === tab.id
          return (
            <TouchableOpacity
              key={tab.id}
              style={[styles.tab, selected && styles.tabActive]}
              onPress={() => setActive(tab.id)}
            >
              <Text style={[styles.tabText, selected && styles.tabTextActive]}>{tab.label}</Text>
            </TouchableOpacity>
          )
        })}
      </ScrollView>

      <View style={styles.toolbar}>
        <ActionButton icon="play-circle-outline" label="Reproduzir áudio" onPress={() => {}} />
        <ActionButton icon="remove-outline" label="Diminuir texto" onPress={() => setFontScale(v => Math.max(0.9, v - 0.08))} />
        <ActionButton icon="add-outline" label="Aumentar texto" onPress={() => setFontScale(v => Math.min(1.25, v + 0.08))} />
        <ActionButton icon="copy-outline" label="Copiar trecho" onPress={shareSection} />
        <ActionButton icon="share-social-outline" label="Compartilhar" onPress={shareSection} />
      </View>

      <View style={styles.readingCard}>
        <Text style={styles.readingLabel}>{section.titulo}</Text>
        <Text style={styles.reference}>{section.referencia}</Text>
        {section.conteudo.map((paragraph, index) => (
          <Text key={index} style={[styles.paragraph, { fontSize: 15 * fontScale, lineHeight: 24 * fontScale }]}>
            {paragraph}
          </Text>
        ))}
      </View>

      <View style={styles.superiorCard}>
        <View style={styles.superiorIcon}>
          <Ionicons name="shield-checkmark-outline" size={20} color={BLUE} />
        </View>
        <View style={{ flex: 1 }}>
        <Text style={styles.superiorTitle}>Leitura com fontes</Text>
        <Text style={styles.superiorText}>
            A melhoria do Vera Fidei não é copiar outro app: é ligar a leitura espiritual à biblioteca, às fontes primárias, ao Catecismo e ao verificador de citações.
        </Text>
        </View>
      </View>

      <View style={styles.quickGrid}>
        <View style={styles.quickCard}>
          <Ionicons name="library-outline" size={19} color={WINE} />
          <Text style={styles.quickTitle}>Fontes ligadas</Text>
          <Text style={styles.quickText}>Patrística, catecismo e documentos.</Text>
        </View>
        <View style={styles.quickCard}>
          <Ionicons name="notifications-outline" size={19} color={WINE} />
          <Text style={styles.quickTitle}>Rotina de oração</Text>
          <Text style={styles.quickText}>Alertas e sequência diária.</Text>
        </View>
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: PAPER },
  container: { padding: 16, paddingBottom: 36, gap: 14 },
  hero: {
    backgroundColor: '#fffaf2',
    borderWidth: 1,
    borderColor: '#e7d7b2',
    borderRadius: 8,
    padding: 16,
    gap: 12,
  },
  heroTop: { flexDirection: 'row', justifyContent: 'space-between', gap: 12 },
  kicker: { fontSize: 11, fontWeight: '700', color: GOLD, textTransform: 'uppercase', letterSpacing: 0.8 },
  heroTitle: { fontSize: 30, fontWeight: '800', color: INK, marginTop: 2 },
  colorBadge: { alignItems: 'flex-end', justifyContent: 'center' },
  colorLabel: { fontSize: 10, color: '#8c7b65' },
  colorValue: { fontSize: 13, fontWeight: '700', color: INK },
  memoria: { fontSize: 17, lineHeight: 23, fontWeight: '700', color: INK },
  heroMeta: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  metaPill: { flexDirection: 'row', alignItems: 'center', gap: 5, backgroundColor: '#f3ead7', borderRadius: 999, paddingHorizontal: 9, paddingVertical: 5 },
  metaText: { fontSize: 11, color: '#6f5b42', fontWeight: '600' },
  tabs: { gap: 8, paddingRight: 8 },
  tab: { borderBottomWidth: 2, borderBottomColor: 'transparent', paddingHorizontal: 10, paddingVertical: 9 },
  tabActive: { borderBottomColor: WINE },
  tabText: { fontSize: 13, color: '#8c7b65', fontWeight: '600' },
  tabTextActive: { color: INK },
  toolbar: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  actionButton: { width: 36, height: 36, borderRadius: 18, backgroundColor: '#efe2ca', alignItems: 'center', justifyContent: 'center' },
  readingCard: {
    backgroundColor: '#fff',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#eadcc2',
    padding: 16,
    gap: 8,
  },
  readingLabel: { fontSize: 12, textTransform: 'uppercase', letterSpacing: 0.8, color: GOLD, fontWeight: '800' },
  reference: { fontSize: 14, color: INK, fontWeight: '700', marginBottom: 4 },
  paragraph: { color: '#3e3128' },
  superiorCard: {
    flexDirection: 'row',
    gap: 12,
    backgroundColor: '#eef5f8',
    borderWidth: 1,
    borderColor: '#cbdde6',
    borderRadius: 8,
    padding: 14,
  },
  superiorIcon: { width: 38, height: 38, borderRadius: 19, backgroundColor: '#d7e9f0', alignItems: 'center', justifyContent: 'center' },
  superiorTitle: { fontSize: 14, fontWeight: '800', color: BLUE },
  superiorText: { fontSize: 13, color: '#496171', lineHeight: 19, marginTop: 3 },
  quickGrid: { flexDirection: 'row', gap: 10 },
  quickCard: { flex: 1, backgroundColor: '#fff', borderRadius: 8, borderWidth: 1, borderColor: '#eadcc2', padding: 12, gap: 5 },
  quickTitle: { fontSize: 13, fontWeight: '800', color: INK },
  quickText: { fontSize: 12, color: '#7a6a58', lineHeight: 17 },
})
