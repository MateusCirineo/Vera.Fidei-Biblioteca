import { StyleSheet, Text, TouchableOpacity, View } from 'react-native'
import { Ionicons } from '@expo/vector-icons'

import { useAuth } from '../auth/AuthContext'
import { planLabel } from '../lib/plan'
import { colors } from '../lib/theme'

const items: { route: string; title: string; subtitle: string; icon: keyof typeof Ionicons.glyphMap }[] = [
  { route: 'Santos', title: 'Santos', subtitle: 'Memórias e pesquisa no acervo', icon: 'star-outline' },
  { route: 'Orações', title: 'Orações', subtitle: 'Orações tradicionais completas', icon: 'rose-outline' },
  { route: 'Perfil', title: 'Meu perfil', subtitle: 'Conta, plano, privacidade e sessão', icon: 'person-circle-outline' },
]

export default function MoreScreen({ navigation }: { navigation: any }) {
  const { user } = useAuth()
  return (
    <View style={styles.root}>
      <View style={styles.account}>
        <Text style={styles.name}>{user?.name}</Text>
        <Text style={styles.plan}>Plano {planLabel(user?.plan)}</Text>
      </View>
      {items.map(item => (
        <TouchableOpacity key={item.route} style={styles.item} onPress={() => navigation.navigate(item.route)}>
          <View style={styles.icon}><Ionicons name={item.icon} size={22} color={colors.gold} /></View>
          <View style={styles.itemText}>
            <Text style={styles.title}>{item.title}</Text>
            <Text style={styles.subtitle}>{item.subtitle}</Text>
          </View>
          <Ionicons name="chevron-forward-outline" size={19} color={colors.tertiary} />
        </TouchableOpacity>
      ))}
    </View>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background, padding: 15, gap: 9 },
  account: { backgroundColor: colors.goldSoft, borderWidth: 1, borderColor: '#6b5721', borderRadius: 10, padding: 14, marginBottom: 4 },
  name: { color: colors.text, fontSize: 18, fontWeight: '900' },
  plan: { color: colors.gold, marginTop: 3, fontWeight: '700' },
  item: { minHeight: 68, flexDirection: 'row', alignItems: 'center', gap: 11, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, padding: 12 },
  icon: { width: 40, height: 40, borderRadius: 20, backgroundColor: colors.background, alignItems: 'center', justifyContent: 'center' },
  itemText: { flex: 1 },
  title: { color: colors.text, fontWeight: '900' },
  subtitle: { color: colors.muted, fontSize: 12, marginTop: 3 },
})
