import { useState } from 'react'
import { ActivityIndicator, Alert, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native'

import { useAuth } from '../auth/AuthContext'
import { resendEmailVerification } from '../lib/api'
import { planLabel } from '../lib/plan'
import { colors } from '../lib/theme'

export default function ProfileScreen({ navigation }: { navigation: any }) {
  const { user, logout, refreshUser } = useAuth()
  const [busy, setBusy] = useState<'refresh' | 'verify' | 'logout' | null>(null)

  async function run(kind: typeof busy, operation: () => Promise<void>) {
    setBusy(kind)
    try {
      await operation()
    } catch (reason) {
      Alert.alert('Não foi possível concluir', reason instanceof Error ? reason.message : 'Tente novamente.')
    } finally {
      setBusy(null)
    }
  }

  if (!user) return null

  return (
    <ScrollView style={styles.root} contentContainerStyle={styles.container}>
      <View style={styles.hero}>
        <View style={styles.avatar}><Text style={styles.avatarText}>{user.name.slice(0, 1).toUpperCase()}</Text></View>
        <View style={styles.heroText}>
          <Text style={styles.name}>{user.name}</Text>
          <Text style={styles.email}>{user.email}</Text>
        </View>
      </View>

      <View style={styles.card}>
        <View style={styles.row}>
          <Text style={styles.label}>Plano</Text>
          <Text style={styles.value}>{planLabel(user.plan)}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.label}>E-mail</Text>
          <Text style={[styles.value, user.email_verified ? styles.ok : styles.pending]}>
            {user.email_verified ? 'Verificado' : 'Aguardando confirmação'}
          </Text>
        </View>
        {user.billing_status ? (
          <View style={styles.row}>
            <Text style={styles.label}>Assinatura</Text>
            <Text style={styles.value}>{user.billing_status}</Text>
          </View>
        ) : null}
      </View>

      {!user.email_verified ? (
        <TouchableOpacity
          style={styles.button}
          disabled={busy !== null}
          onPress={() => void run('verify', async () => {
            const message = await resendEmailVerification()
            Alert.alert('Verificação de e-mail', message)
          })}
        >
          {busy === 'verify' ? <ActivityIndicator color={colors.gold} /> : null}
          <Text style={styles.buttonText}>Reenviar confirmação</Text>
        </TouchableOpacity>
      ) : null}

      <TouchableOpacity style={styles.button} onPress={() => navigation.navigate('ContaWeb', { destination: 'profile' })}>
        <Text style={styles.buttonText}>Privacidade, dados e assinatura</Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.button} onPress={() => navigation.navigate('ContaWeb', { destination: 'plans' })}>
        <Text style={styles.buttonText}>Ver planos</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={styles.button}
        disabled={busy !== null}
        onPress={() => void run('refresh', refreshUser)}
      >
        {busy === 'refresh' ? <ActivityIndicator color={colors.gold} /> : null}
        <Text style={styles.buttonText}>Atualizar meus dados</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.button, styles.logout]}
        disabled={busy !== null}
        onPress={() => void run('logout', logout)}
      >
        {busy === 'logout' ? <ActivityIndicator color="#fecaca" /> : null}
        <Text style={[styles.buttonText, styles.logoutText]}>Sair deste aparelho</Text>
      </TouchableOpacity>
      <Text style={styles.securityNote}>
        Sua sessão fica protegida pelo armazenamento seguro do aparelho. PDFs e dados de assinatura abrem dentro do app, sem colocar o token na URL.
      </Text>
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { padding: 16, paddingBottom: 44, gap: 10 },
  hero: { flexDirection: 'row', alignItems: 'center', gap: 13, marginBottom: 6 },
  avatar: { width: 52, height: 52, borderRadius: 26, backgroundColor: colors.goldSoft, borderWidth: 1, borderColor: colors.gold, alignItems: 'center', justifyContent: 'center' },
  avatarText: { color: colors.gold, fontWeight: '900', fontSize: 22 },
  heroText: { flex: 1 },
  name: { color: colors.text, fontSize: 20, fontWeight: '800' },
  email: { color: colors.muted, marginTop: 2 },
  card: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10, paddingHorizontal: 14 },
  row: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
  label: { color: colors.muted },
  value: { color: colors.text, fontWeight: '700', textAlign: 'right', flexShrink: 1 },
  ok: { color: '#86efac' },
  pending: { color: '#fde68a' },
  button: { minHeight: 48, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, borderRadius: 9, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.card },
  buttonText: { color: colors.gold, fontWeight: '800' },
  logout: { borderColor: '#7f1d1d', marginTop: 5 },
  logoutText: { color: '#fecaca' },
  securityNote: { color: colors.tertiary, fontSize: 12, lineHeight: 18, marginTop: 8, textAlign: 'center' },
})
