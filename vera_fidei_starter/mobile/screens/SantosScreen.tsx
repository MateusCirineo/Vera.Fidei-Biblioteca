import { useMemo, useState } from 'react'
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

import { colors } from '../lib/theme'

type Saint = {
  id: string
  day: number
  month: number
  name: string
  subtitle: string
  summary: string
  searches: string[]
}

const saints: Saint[] = [
  {
    id: 'agostinho', day: 28, month: 8, name: 'Santo Agostinho', subtitle: 'bispo de Hipona e Doutor da Igreja',
    summary: 'Sua obra une busca da verdade, conversão, graça, vida da Igreja e leitura profunda das Escrituras.',
    searches: ['Santo Agostinho', 'graça', 'Cidade de Deus'],
  },
  {
    id: 'ambrosio', day: 7, month: 12, name: 'Santo Ambrósio', subtitle: 'bispo de Milão e Doutor da Igreja',
    summary: 'Pastor, pregador e escritor latino, teve papel decisivo na formação cristã de Agostinho e na defesa da fé nicena.',
    searches: ['Santo Ambrósio', 'sacramentos', 'De Mysteriis'],
  },
  {
    id: 'irineu', day: 28, month: 6, name: 'Santo Irineu de Lião', subtitle: 'bispo, mártir e Doutor da Igreja',
    summary: 'Testemunha da tradição apostólica, combateu as heresias e expôs a unidade da criação, da redenção e da Igreja.',
    searches: ['Santo Irineu de Lião', 'Contra as Heresias', 'tradição apostólica'],
  },
  {
    id: 'filipeneri', day: 26, month: 5, name: 'São Filipe Néri', subtitle: 'presbítero e apóstolo de Roma',
    summary: 'Recordado pela caridade alegre, pela vida de oração e pela formação espiritual marcada por humildade e proximidade.',
    searches: ['São Filipe Néri', 'alegria cristã', 'oração'],
  },
]

const monthNames = ['JAN', 'FEV', 'MAR', 'ABR', 'MAI', 'JUN', 'JUL', 'AGO', 'SET', 'OUT', 'NOV', 'DEZ']

export default function SantosScreen({ navigation }: { navigation: any }) {
  const today = useMemo(() => new Date(), [])
  const initial = saints.find(item => item.day === today.getDate() && item.month === today.getMonth() + 1) ?? saints[0]
  const [selectedId, setSelectedId] = useState(initial.id)
  const saint = saints.find(item => item.id === selectedId) ?? initial
  const isToday = saint.day === today.getDate() && saint.month === today.getMonth() + 1

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.selector}>
        <Text style={styles.kicker}>Memórias e fontes</Text>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          {saints.map(item => (
            <TouchableOpacity key={item.id} style={[styles.chip, selectedId === item.id && styles.chipActive]} onPress={() => setSelectedId(item.id)}>
              <Text style={[styles.chipText, selectedId === item.id && styles.chipTextActive]}>{item.name}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>
      </View>

      <View style={styles.headerCard}>
        <View style={styles.dateBlock}>
          <Text style={styles.day}>{saint.day}</Text>
          <Text style={styles.month}>{monthNames[saint.month - 1]}</Text>
        </View>
        <View style={styles.headerText}>
          <Text style={styles.kicker}>{isToday ? 'Memória de hoje' : 'Memória litúrgica'}</Text>
          <Text style={styles.title}>{saint.name}</Text>
          <Text style={styles.subtitle}>{saint.subtitle}</Text>
        </View>
      </View>

      <View style={styles.portrait}>
        <View style={styles.halo}><Ionicons name="person-outline" size={52} color={colors.gold} /></View>
        <Text style={styles.portraitCaption}>Biografia resumida</Text>
      </View>

      <View style={styles.article}>
        <Text style={styles.articleTitle}>Vida e espiritualidade</Text>
        <Text style={styles.paragraph}>{saint.summary}</Text>
        <Text style={styles.disclaimer}>
          Use os atalhos abaixo para localizar passagens no acervo. A pesquisa mostra apenas o que estiver efetivamente indexado e identifica a situação da fonte.
        </Text>
      </View>

      <Text style={styles.sectionTitle}>Pesquisar no Vera Fidei</Text>
      {saint.searches.map(term => (
        <TouchableOpacity key={term} style={styles.relatedCard} onPress={() => navigation.navigate('Pesquisa', { initialQuery: term })}>
          <Ionicons name="search-outline" size={18} color={colors.gold} />
          <Text style={styles.relatedTitle}>{term}</Text>
          <Ionicons name="arrow-forward-outline" size={16} color={colors.gold} />
        </TouchableOpacity>
      ))}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 15, paddingBottom: 42, gap: 12 },
  selector: { gap: 8 },
  kicker: { color: colors.gold, fontSize: 11, fontWeight: '900', textTransform: 'uppercase', letterSpacing: 0.7 },
  chips: { gap: 7, paddingRight: 10 },
  chip: { borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, borderRadius: 7, paddingHorizontal: 10, paddingVertical: 8 },
  chipActive: { borderColor: '#6b5721', backgroundColor: colors.goldSoft },
  chipText: { color: colors.muted, fontWeight: '700', fontSize: 12 },
  chipTextActive: { color: colors.gold },
  headerCard: { flexDirection: 'row', gap: 13, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 14 },
  dateBlock: { alignItems: 'center', minWidth: 54 },
  day: { color: colors.gold, fontSize: 34, fontWeight: '900', lineHeight: 37 },
  month: { color: colors.muted, fontSize: 11, fontWeight: '800' },
  headerText: { flex: 1 },
  title: { color: colors.text, fontSize: 22, fontWeight: '900', marginTop: 3 },
  subtitle: { color: colors.muted, lineHeight: 18, marginTop: 3 },
  portrait: { minHeight: 170, backgroundColor: '#203c55', borderRadius: 10, alignItems: 'center', justifyContent: 'center', gap: 10 },
  halo: { width: 94, height: 94, borderRadius: 47, borderWidth: 1, borderColor: colors.gold, alignItems: 'center', justifyContent: 'center' },
  portraitCaption: { color: '#f4ead3', fontWeight: '700' },
  article: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 14, gap: 8 },
  articleTitle: { color: colors.text, fontSize: 16, fontWeight: '900' },
  paragraph: { color: colors.muted, fontSize: 14, lineHeight: 21 },
  disclaimer: { color: colors.tertiary, fontSize: 12, lineHeight: 18 },
  sectionTitle: { color: colors.text, fontSize: 17, fontWeight: '900', marginTop: 3 },
  relatedCard: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 8, padding: 12 },
  relatedTitle: { flex: 1, color: colors.text, fontWeight: '800' },
})
