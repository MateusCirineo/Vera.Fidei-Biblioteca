import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

const GOLD = '#c9a84c'
const INK = '#2f241d'
const PAPER = '#fbf7ef'
const WINE = '#6f1d32'
const BLUE = '#183c5c'

const related = [
  { title: 'Catecismo', subtitle: 'virtudes, oração e santidade' },
  { title: 'Patrística', subtitle: 'modelos antigos de vida cristã' },
  { title: 'Liturgia', subtitle: 'memória celebrada na Igreja' },
]

export default function SantosScreen() {
  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.headerCard}>
        <View style={styles.dateBlock}>
          <Text style={styles.day}>26</Text>
          <Text style={styles.month}>MAI</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={styles.kicker}>Santo do dia</Text>
          <Text style={styles.title}>São Filipe Néri</Text>
          <Text style={styles.subtitle}>presbítero, apóstolo de Roma e mestre da alegria cristã</Text>
        </View>
      </View>

      <View style={styles.portrait}>
        <View style={styles.halo}>
          <Ionicons name="person-outline" size={54} color={GOLD} />
        </View>
        <Text style={styles.portraitCaption}>Memória litúrgica</Text>
      </View>

      <View style={styles.article}>
        <Text style={styles.articleTitle}>Vida e espiritualidade</Text>
        <Text style={styles.paragraph}>
          São Filipe Néri é recordado pela caridade alegre, pela vida de oração e pela capacidade de formar almas sem dureza. Sua santidade mostra que a fidelidade à Igreja pode ser profunda, bela e cheia de humanidade.
        </Text>
        <Text style={styles.paragraph}>
          No Vera Fidei, a tela dos santos deve ir além da biografia: cada santo pode ser ligado às fontes da biblioteca, às virtudes do Catecismo, à liturgia do dia e a trilhas de estudo.
        </Text>
      </View>

      <View style={styles.quoteCard}>
        <Ionicons name="chatbox-ellipses-outline" size={19} color={WINE} />
        <Text style={styles.quote}>
          “Alegrai-vos no Senhor”: a santidade diária precisa caber no coração e na rotina.
        </Text>
      </View>

      <Text style={styles.sectionTitle}>Aprofundar no Vera Fidei</Text>
      <View style={styles.relatedGrid}>
        {related.map(item => (
          <TouchableOpacity key={item.title} style={styles.relatedCard}>
            <Text style={styles.relatedTitle}>{item.title}</Text>
            <Text style={styles.relatedSubtitle}>{item.subtitle}</Text>
            <Ionicons name="arrow-forward-outline" size={16} color={BLUE} />
          </TouchableOpacity>
        ))}
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: PAPER },
  container: { padding: 16, paddingBottom: 40, gap: 14 },
  headerCard: {
    flexDirection: 'row',
    gap: 14,
    backgroundColor: '#fffaf2',
    borderWidth: 1,
    borderColor: '#eadcc2',
    borderRadius: 8,
    padding: 16,
  },
  dateBlock: { alignItems: 'center', minWidth: 54 },
  day: { fontSize: 34, color: WINE, fontWeight: '800', lineHeight: 36 },
  month: { fontSize: 12, color: '#8c7b65', fontWeight: '700', letterSpacing: 1 },
  kicker: { fontSize: 11, color: GOLD, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.8 },
  title: { fontSize: 23, color: INK, fontWeight: '800', marginTop: 2 },
  subtitle: { fontSize: 13, color: '#6f5b42', lineHeight: 18, marginTop: 3 },
  portrait: {
    minHeight: 180,
    backgroundColor: '#203c55',
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  halo: { width: 96, height: 96, borderRadius: 48, borderWidth: 1, borderColor: GOLD, alignItems: 'center', justifyContent: 'center', backgroundColor: '#ffffff10' },
  portraitCaption: { color: '#f4ead3', fontSize: 13, fontWeight: '700' },
  article: { backgroundColor: '#fff', borderRadius: 8, borderWidth: 1, borderColor: '#eadcc2', padding: 16, gap: 8 },
  articleTitle: { fontSize: 15, color: INK, fontWeight: '800' },
  paragraph: { fontSize: 14, color: '#4c3c31', lineHeight: 22 },
  quoteCard: { flexDirection: 'row', gap: 10, backgroundColor: '#fff1f4', borderWidth: 1, borderColor: '#e8c8d0', borderRadius: 8, padding: 14 },
  quote: { flex: 1, color: WINE, fontSize: 14, lineHeight: 21, fontStyle: 'italic' },
  sectionTitle: { fontSize: 16, color: BLUE, fontWeight: '800' },
  relatedGrid: { gap: 8 },
  relatedCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: '#fff', borderRadius: 8, borderWidth: 1, borderColor: '#d8e3ea', padding: 12 },
  relatedTitle: { width: 92, color: BLUE, fontSize: 14, fontWeight: '800' },
  relatedSubtitle: { flex: 1, color: '#61788a', fontSize: 12, lineHeight: 17 },
})
