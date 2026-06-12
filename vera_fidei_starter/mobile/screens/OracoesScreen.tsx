import { useState } from 'react'
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

type PrayerCategory = {
  id: string
  title: string
  subtitle: string
  icon: keyof typeof Ionicons.glyphMap
  prayers: string[]
}

const categories: PrayerCategory[] = [
  {
    id: 'marianas',
    title: 'Orações Marianas',
    subtitle: 'Rosário, Angelus e devoções de Nossa Senhora',
    icon: 'rose-outline',
    prayers: ['Angelus', 'Regina Caeli', 'Salve Rainha', 'Consagração a Nossa Senhora'],
  },
  {
    id: 'diarias',
    title: 'Roteiro de Orações Diárias',
    subtitle: 'Manhã, tarde, noite e exame de consciência',
    icon: 'time-outline',
    prayers: ['Oferecimento do dia', 'Oração da manhã', 'Exame de consciência', 'Oração da noite'],
  },
  {
    id: 'eucaristicas',
    title: 'Orações Eucarísticas',
    subtitle: 'Adoração, comunhão espiritual e ação de graças',
    icon: 'sparkles-outline',
    prayers: ['Comunhão espiritual', 'Ação de graças', 'Visita ao Santíssimo', 'Alma de Cristo'],
  },
  {
    id: 'santos',
    title: 'Orações aos Santos',
    subtitle: 'Intercessão e ladainhas tradicionais',
    icon: 'person-outline',
    prayers: ['São José', 'São Miguel Arcanjo', 'Santo Agostinho', 'Santo Tomás de Aquino'],
  },
  {
    id: 'liturgicas',
    title: 'Sequências Litúrgicas',
    subtitle: 'Orações e hinos ligados ao ano litúrgico',
    icon: 'calendar-outline',
    prayers: ['Veni Creator Spiritus', 'Victimae Paschali', 'Stabat Mater', 'Dies Irae'],
  },
  {
    id: 'doutores',
    title: 'Orando com os Doutores da Igreja',
    subtitle: 'Pontes entre oração, patrística e doutrina',
    icon: 'library-outline',
    prayers: ['Com Santo Agostinho', 'Com São Jerônimo', 'Com São Gregório Magno', 'Com Santa Teresa de Ávila'],
  },
]

const GOLD = '#c9a84c'
const BG = '#111111'
const CARD = '#1a1a1a'
const BORDER = '#2a2a2a'
const TEXT = '#f5f0e8'
const MUTED = '#b8b0a0'
const TERTIARY = '#706860'
const WINE = '#3d1010'

export default function OracoesScreen() {
  const [active, setActive] = useState(categories[0].id)
  const category = categories.find(item => item.id === active) ?? categories[0]

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.intro}>
        <Text style={styles.introKicker}>Espiritualidade diária</Text>
        <Text style={styles.introTitle}>Orações</Text>
        <Text style={styles.introText}>
          Um roteiro prático para rezar, estudar e ligar cada devoção às fontes do acervo Vera Fidei.
        </Text>
      </View>

      <View style={styles.list}>
        {categories.map(item => {
          const selected = item.id === active
          return (
            <TouchableOpacity
              key={item.id}
              style={[styles.categoryRow, selected && styles.categoryRowActive]}
              onPress={() => setActive(item.id)}
            >
              <View style={[styles.iconBox, selected && styles.iconBoxActive]}>
                <Ionicons name={item.icon} size={18} color={selected ? GOLD : MUTED} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={[styles.categoryTitle, selected && styles.categoryTitleActive]}>{item.title}</Text>
                <Text style={styles.categorySubtitle}>{item.subtitle}</Text>
              </View>
              <Ionicons name="chevron-forward-outline" size={18} color={selected ? GOLD : TERTIARY} />
            </TouchableOpacity>
          )
        })}
      </View>

      <View style={styles.detailCard}>
        <View style={styles.detailHeader}>
          <Ionicons name={category.icon} size={22} color={GOLD} />
          <View style={{ flex: 1 }}>
            <Text style={styles.detailTitle}>{category.title}</Text>
            <Text style={styles.detailSubtitle}>{category.subtitle}</Text>
          </View>
        </View>
        <View style={styles.prayerList}>
          {category.prayers.map((prayer, index) => (
            <TouchableOpacity key={prayer} style={styles.prayerItem}>
              <Text style={styles.prayerIndex}>{String(index + 1).padStart(2, '0')}</Text>
              <Text style={styles.prayerName}>{prayer}</Text>
              <Ionicons name="bookmarks-outline" size={17} color={GOLD} />
            </TouchableOpacity>
          ))}
        </View>
      </View>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: BG },
  container: { padding: 16, paddingBottom: 40, gap: 14 },
  intro: { backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, borderRadius: 8, padding: 16 },
  introKicker: { fontSize: 11, fontWeight: '800', color: GOLD, textTransform: 'uppercase', letterSpacing: 0.8 },
  introTitle: { fontSize: 28, fontWeight: '800', color: TEXT, marginTop: 3 },
  introText: { fontSize: 14, color: MUTED, lineHeight: 20, marginTop: 5 },
  list: { backgroundColor: CARD, borderWidth: 1, borderColor: BORDER, borderRadius: 8, overflow: 'hidden' },
  categoryRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingHorizontal: 12,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: BORDER,
  },
  categoryRowActive: { backgroundColor: WINE },
  iconBox: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#111111', alignItems: 'center', justifyContent: 'center' },
  iconBoxActive: { backgroundColor: '#2a1f12' },
  categoryTitle: { fontSize: 14, fontWeight: '700', color: TEXT },
  categoryTitleActive: { color: GOLD },
  categorySubtitle: { fontSize: 12, color: MUTED, marginTop: 2, lineHeight: 16 },
  detailCard: { backgroundColor: CARD, borderRadius: 8, borderWidth: 1, borderColor: BORDER, padding: 14, gap: 12 },
  detailHeader: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  detailTitle: { fontSize: 16, color: TEXT, fontWeight: '800' },
  detailSubtitle: { fontSize: 12, color: MUTED, marginTop: 2 },
  prayerList: { gap: 7 },
  prayerItem: { flexDirection: 'row', alignItems: 'center', gap: 10, borderWidth: 1, borderColor: BORDER, borderRadius: 8, paddingHorizontal: 10, paddingVertical: 10, backgroundColor: BG },
  prayerIndex: { fontSize: 11, fontWeight: '800', color: GOLD, fontVariant: ['tabular-nums'] },
  prayerName: { flex: 1, fontSize: 14, color: TEXT, fontWeight: '600' },
})
