import { useMemo, useState } from 'react'
import { Modal, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

import { colors } from '../lib/theme'

type Prayer = {
  id: string
  category: 'fundamentais' | 'marianas' | 'eucaristicas' | 'proteção'
  title: string
  text: string
}

const prayers: Prayer[] = [
  {
    id: 'pai-nosso', category: 'fundamentais', title: 'Pai-Nosso',
    text: 'Pai nosso que estais nos céus, santificado seja o vosso nome; venha a nós o vosso reino; seja feita a vossa vontade, assim na terra como no céu. O pão nosso de cada dia nos dai hoje; perdoai-nos as nossas ofensas, assim como nós perdoamos a quem nos tem ofendido; e não nos deixeis cair em tentação, mas livrai-nos do mal. Amém.',
  },
  {
    id: 'gloria', category: 'fundamentais', title: 'Glória ao Pai',
    text: 'Glória ao Pai, ao Filho e ao Espírito Santo. Como era no princípio, agora e sempre. Amém.',
  },
  {
    id: 'ave-maria', category: 'marianas', title: 'Ave-Maria',
    text: 'Ave Maria, cheia de graça, o Senhor é convosco. Bendita sois vós entre as mulheres e bendito é o fruto do vosso ventre, Jesus. Santa Maria, Mãe de Deus, rogai por nós, pecadores, agora e na hora da nossa morte. Amém.',
  },
  {
    id: 'salve-rainha', category: 'marianas', title: 'Salve Rainha',
    text: 'Salve, Rainha, Mãe de misericórdia, vida, doçura e esperança nossa, salve! A vós bradamos, os degredados filhos de Eva; a vós suspiramos, gemendo e chorando neste vale de lágrimas. Eia, pois, advogada nossa, esses vossos olhos misericordiosos a nós volvei; e depois deste desterro mostrai-nos Jesus, bendito fruto do vosso ventre. Ó clemente, ó piedosa, ó doce sempre Virgem Maria. Rogai por nós, santa Mãe de Deus, para que sejamos dignos das promessas de Cristo. Amém.',
  },
  {
    id: 'alma-cristo', category: 'eucaristicas', title: 'Alma de Cristo',
    text: 'Alma de Cristo, santificai-me. Corpo de Cristo, salvai-me. Sangue de Cristo, inebriai-me. Água do lado de Cristo, lavai-me. Paixão de Cristo, confortai-me. Ó bom Jesus, ouvi-me. Dentro das vossas chagas, escondei-me. Não permitais que eu me separe de vós. Do espírito maligno, defendei-me. Na hora da minha morte, chamai-me e mandai-me ir para vós, para que com os vossos santos vos louve por todos os séculos dos séculos. Amém.',
  },
  {
    id: 'sao-miguel', category: 'proteção', title: 'São Miguel Arcanjo',
    text: 'São Miguel Arcanjo, defendei-nos no combate; sede nosso refúgio contra as maldades e ciladas do demônio. Ordene-lhe Deus, instantemente o pedimos; e vós, Príncipe da Milícia Celeste, pela virtude divina, precipitai no inferno a Satanás e aos outros espíritos malignos que andam pelo mundo para perder as almas. Amém.',
  },
]

const categories = [
  { id: 'todas', label: 'Todas' },
  { id: 'fundamentais', label: 'Fundamentais' },
  { id: 'marianas', label: 'Marianas' },
  { id: 'eucaristicas', label: 'Eucarísticas' },
  { id: 'proteção', label: 'Proteção' },
] as const

export default function OracoesScreen() {
  const [category, setCategory] = useState<(typeof categories)[number]['id']>('todas')
  const [selected, setSelected] = useState<Prayer | null>(null)
  const visible = useMemo(() => category === 'todas' ? prayers : prayers.filter(prayer => prayer.category === category), [category])

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.container}>
        <View style={styles.intro}>
          <Text style={styles.kicker}>Espiritualidade diária</Text>
          <Text style={styles.title}>Orações</Text>
          <Text style={styles.introText}>Orações tradicionais, cada uma com um único registro e texto completo.</Text>
        </View>

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.chips}>
          {categories.map(item => (
            <TouchableOpacity key={item.id} style={[styles.chip, category === item.id && styles.chipActive]} onPress={() => setCategory(item.id)}>
              <Text style={[styles.chipText, category === item.id && styles.chipTextActive]}>{item.label}</Text>
            </TouchableOpacity>
          ))}
        </ScrollView>

        <View style={styles.list}>
          {visible.map((prayer, index) => (
            <TouchableOpacity key={prayer.id} accessibilityRole="button" style={styles.prayerItem} onPress={() => setSelected(prayer)}>
              <Text style={styles.index}>{String(index + 1).padStart(2, '0')}</Text>
              <Text style={styles.prayerTitle}>{prayer.title}</Text>
              <Ionicons name="chevron-forward-outline" size={18} color={colors.gold} />
            </TouchableOpacity>
          ))}
        </View>
      </ScrollView>

      <Modal visible={Boolean(selected)} animationType="slide" transparent onRequestClose={() => setSelected(null)}>
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <View style={styles.modalHeader}>
              <Text style={styles.modalTitle}>{selected?.title}</Text>
              <TouchableOpacity accessibilityLabel="Fechar oração" onPress={() => setSelected(null)}>
                <Ionicons name="close-outline" size={28} color={colors.gold} />
              </TouchableOpacity>
            </View>
            <ScrollView contentContainerStyle={styles.prayerContent}>
              <Text selectable style={styles.prayerText}>{selected?.text}</Text>
            </ScrollView>
            <TouchableOpacity style={styles.closeButton} onPress={() => setSelected(null)}><Text style={styles.closeText}>Concluir</Text></TouchableOpacity>
          </View>
        </View>
      </Modal>
    </View>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 15, paddingBottom: 42, gap: 12 },
  intro: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 14 },
  kicker: { color: colors.gold, fontWeight: '900', fontSize: 11, textTransform: 'uppercase', letterSpacing: 0.7 },
  title: { color: colors.text, fontSize: 27, fontWeight: '900', marginTop: 3 },
  introText: { color: colors.muted, lineHeight: 19, marginTop: 5 },
  chips: { gap: 7, paddingRight: 10 },
  chip: { borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card, borderRadius: 7, paddingHorizontal: 10, paddingVertical: 8 },
  chipActive: { borderColor: '#6b5721', backgroundColor: colors.goldSoft },
  chipText: { color: colors.muted, fontWeight: '700', fontSize: 12 },
  chipTextActive: { color: colors.gold },
  list: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, overflow: 'hidden' },
  prayerItem: { minHeight: 54, flexDirection: 'row', alignItems: 'center', gap: 11, paddingHorizontal: 13, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  index: { color: colors.gold, fontSize: 11, fontWeight: '900' },
  prayerTitle: { flex: 1, color: colors.text, fontWeight: '800' },
  modalBackdrop: { flex: 1, backgroundColor: '#000000aa', justifyContent: 'flex-end' },
  modalCard: { maxHeight: '86%', minHeight: '56%', backgroundColor: colors.card, borderTopLeftRadius: 18, borderTopRightRadius: 18, borderWidth: 1, borderColor: colors.border, padding: 17 },
  modalHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, paddingBottom: 12, borderBottomWidth: 1, borderBottomColor: colors.border },
  modalTitle: { flex: 1, color: colors.text, fontSize: 21, fontWeight: '900' },
  prayerContent: { paddingVertical: 20 },
  prayerText: { color: colors.text, fontSize: 18, lineHeight: 29 },
  closeButton: { minHeight: 46, backgroundColor: colors.wine, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  closeText: { color: '#fff', fontWeight: '900' },
})
