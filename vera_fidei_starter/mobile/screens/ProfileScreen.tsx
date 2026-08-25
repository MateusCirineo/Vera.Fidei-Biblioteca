import { useState } from 'react'
import { File, Paths } from 'expo-file-system'
import * as Sharing from 'expo-sharing'
import {
  ActivityIndicator,
  Alert,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native'

import { useAuth } from '../auth/AuthContext'
import {
  ApiError,
  deletePersonalAccount,
  exportPersonalData,
  resendEmailVerification,
} from '../lib/api'
import { allowsAccountWeb } from '../lib/distribution-policy'
import { planLabel } from '../lib/plan'
import { DISTRIBUTION_MODE } from '../lib/runtime-config'
import { colors } from '../lib/theme'

export default function ProfileScreen({ navigation }: { navigation: any }) {
  const { user, logout, refreshUser } = useAuth()
  const [busy, setBusy] = useState<'refresh' | 'verify' | 'export' | 'delete' | 'logout' | null>(null)
  const [showDelete, setShowDelete] = useState(false)
  const [deletePassword, setDeletePassword] = useState('')
  const [deleteConfirmation, setDeleteConfirmation] = useState('')

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

  const accountWebEnabled = allowsAccountWeb(DISTRIBUTION_MODE, 'profile')

  async function exportData() {
    await run('export', async () => {
      const data = await exportPersonalData()
      const stamp = new Date().toISOString().slice(0, 10)
      const file = new File(Paths.cache, `vera-fidei-meus-dados-${stamp}.json`)
      try {
        file.write(`${JSON.stringify(data, null, 2)}\n`)
        if (!(await Sharing.isAvailableAsync())) {
          throw new Error('O compartilhamento de arquivos não está disponível neste aparelho.')
        }
        await Sharing.shareAsync(file.uri, {
          dialogTitle: 'Exportar meus dados do Vera Fidei',
          mimeType: 'application/json',
          UTI: 'public.json',
        })
      } finally {
        if (file.exists) file.delete()
      }
    })
  }

  async function deleteAccount() {
    await run('delete', async () => {
      try {
        const message = await deletePersonalAccount(deletePassword, deleteConfirmation)
        await logout()
        Alert.alert('Conta excluída', message)
      } catch (reason) {
        if (
          DISTRIBUTION_MODE === 'reader'
          && reason instanceof ApiError
          && reason.status === 409
        ) {
          throw new Error('A conta só pode ser excluída quando não houver uma assinatura ativa vinculada a ela.')
        }
        throw reason
      }
    })
  }

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

      {accountWebEnabled ? (
        <>
          <TouchableOpacity style={styles.button} onPress={() => navigation.navigate('ContaWeb', { destination: 'profile' })}>
            <Text style={styles.buttonText}>Gerenciar conta e assinatura</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.button} onPress={() => navigation.navigate('ContaWeb', { destination: 'plans' })}>
            <Text style={styles.buttonText}>Ver planos</Text>
          </TouchableOpacity>
        </>
      ) : null}
      <View style={styles.privacyCard}>
        <Text style={styles.privacyTitle}>Privacidade e dados</Text>
        <Text style={styles.privacyText}>
          Exporte uma cópia dos dados associados à sua conta ou solicite a exclusão permanente.
        </Text>
        <TouchableOpacity
          style={styles.button}
          disabled={busy !== null}
          onPress={() => void exportData()}
        >
          {busy === 'export' ? <ActivityIndicator color={colors.gold} /> : null}
          <Text style={styles.buttonText}>Exportar meus dados</Text>
        </TouchableOpacity>
        {!user.is_owner && !showDelete ? (
          <TouchableOpacity
            style={[styles.button, styles.deleteButton]}
            disabled={busy !== null}
            onPress={() => setShowDelete(true)}
          >
            <Text style={styles.deleteText}>Excluir minha conta</Text>
          </TouchableOpacity>
        ) : null}
        {user.is_owner ? (
          <Text style={styles.privacyText}>A conta proprietária é protegida contra exclusão acidental.</Text>
        ) : null}
        {showDelete && !user.is_owner ? (
          <View style={styles.deletePanel}>
            <Text style={styles.deleteTitle}>Exclusão permanente</Text>
            <Text style={styles.privacyText}>
              Esta ação remove seu perfil e os dados pessoais vinculados. Ela não pode ser desfeita.
            </Text>
            <TextInput
              accessibilityLabel="Senha atual para excluir a conta"
              autoCapitalize="none"
              autoComplete="current-password"
              placeholder="Senha atual"
              placeholderTextColor={colors.tertiary}
              secureTextEntry
              style={styles.input}
              value={deletePassword}
              onChangeText={setDeletePassword}
            />
            <TextInput
              accessibilityLabel="Confirmação para excluir a conta"
              autoCapitalize="characters"
              autoComplete="off"
              placeholder="Digite EXCLUIR"
              placeholderTextColor={colors.tertiary}
              style={styles.input}
              value={deleteConfirmation}
              onChangeText={setDeleteConfirmation}
            />
            <TouchableOpacity
              style={[styles.button, styles.deleteButton]}
              disabled={
                busy !== null
                || deletePassword.length < 8
                || deleteConfirmation.trim().toUpperCase() !== 'EXCLUIR'
              }
              onPress={() => void deleteAccount()}
            >
              {busy === 'delete' ? <ActivityIndicator color="#fecaca" /> : null}
              <Text style={styles.deleteText}>Excluir definitivamente</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.button}
              disabled={busy !== null}
              onPress={() => {
                setShowDelete(false)
                setDeletePassword('')
                setDeleteConfirmation('')
              }}
            >
              <Text style={styles.buttonText}>Cancelar</Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </View>
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
        Sua sessão fica protegida pelo armazenamento seguro do aparelho. Nenhuma credencial é colocada no endereço dos PDFs.
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
  privacyCard: { gap: 10, marginTop: 4, padding: 13, backgroundColor: colors.card, borderWidth: 1, borderColor: colors.border, borderRadius: 10 },
  privacyTitle: { color: colors.text, fontSize: 17, fontWeight: '900' },
  privacyText: { color: colors.muted, fontSize: 12, lineHeight: 18 },
  input: { minHeight: 46, color: colors.text, backgroundColor: colors.background, borderWidth: 1, borderColor: colors.border, borderRadius: 8, paddingHorizontal: 12 },
  deletePanel: { gap: 10, marginTop: 2 },
  deleteTitle: { color: '#fecaca', fontWeight: '900' },
  deleteButton: { borderColor: '#7f1d1d' },
  deleteText: { color: '#fecaca', fontWeight: '800' },
  logout: { borderColor: '#7f1d1d', marginTop: 5 },
  logoutText: { color: '#fecaca' },
  securityNote: { color: colors.tertiary, fontSize: 12, lineHeight: 18, marginTop: 8, textAlign: 'center' },
})
