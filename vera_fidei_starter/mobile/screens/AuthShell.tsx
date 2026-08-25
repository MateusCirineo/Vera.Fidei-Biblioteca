import type { PropsWithChildren } from 'react'
import {
  Image,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native'

import { colors } from '../lib/theme'

type Props = PropsWithChildren<{
  title: string
  subtitle: string
}>

export default function AuthShell({ title, subtitle, children }: Props) {
  return (
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <View style={styles.brand}>
          <Image source={require('../assets/logo.png')} style={styles.logo} resizeMode="contain" />
          <Text style={styles.brandName}>Vera.Fidei</Text>
          <Text style={styles.brandSubtitle}>Biblioteca Católica Digital</Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.subtitle}>{subtitle}</Text>
          {children}
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  )
}

export const authStyles = StyleSheet.create({
  label: { color: colors.muted, fontSize: 13, fontWeight: '700', marginTop: 14, marginBottom: 6 },
  input: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: 9,
    backgroundColor: colors.background,
    color: colors.text,
    paddingHorizontal: 13,
    fontSize: 15,
  },
  button: {
    minHeight: 48,
    marginTop: 18,
    borderRadius: 9,
    backgroundColor: colors.wine,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
    gap: 8,
  },
  buttonDisabled: { opacity: 0.65 },
  buttonText: { color: '#fff', fontSize: 15, fontWeight: '800' },
  link: { paddingVertical: 10, alignItems: 'center' },
  linkText: { color: colors.gold, fontSize: 13, fontWeight: '700' },
  error: { color: '#fecaca', backgroundColor: '#7f1d1d55', borderRadius: 7, padding: 10, marginTop: 12 },
  success: { color: '#bbf7d0', backgroundColor: '#14532d55', borderRadius: 7, padding: 10, marginTop: 12, lineHeight: 19 },
})

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { flexGrow: 1, justifyContent: 'center', padding: 22, paddingVertical: 44 },
  brand: { alignItems: 'center', marginBottom: 20 },
  logo: { width: 82, height: 82 },
  brandName: { color: colors.text, fontSize: 29, fontWeight: '800' },
  brandSubtitle: { color: colors.gold, fontSize: 12, fontWeight: '700', marginTop: 2 },
  card: { backgroundColor: colors.card, borderColor: colors.border, borderWidth: 1, borderRadius: 12, padding: 18 },
  title: { color: colors.text, fontSize: 23, fontWeight: '800' },
  subtitle: { color: colors.muted, lineHeight: 20, marginTop: 5 },
})
