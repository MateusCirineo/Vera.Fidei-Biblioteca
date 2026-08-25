import { useState } from 'react'
import { ActivityIndicator, Text, TextInput, TouchableOpacity } from 'react-native'

import { useAuth } from '../auth/AuthContext'
import AuthShell, { authStyles } from './AuthShell'

export default function LoginScreen({ navigation }: { navigation: any }) {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit() {
    if (!email.trim() || !password) {
      setError('Informe seu e-mail e sua senha.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await login(email, password)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível entrar.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title="Entrar" subtitle="Acesse sua biblioteca, pesquisas e verificações.">
      <Text style={authStyles.label}>E-mail</Text>
      <TextInput
        accessibilityLabel="E-mail"
        autoCapitalize="none"
        autoComplete="email"
        inputMode="email"
        keyboardType="email-address"
        style={authStyles.input}
        value={email}
        onChangeText={setEmail}
        returnKeyType="next"
      />
      <Text style={authStyles.label}>Senha</Text>
      <TextInput
        accessibilityLabel="Senha"
        autoCapitalize="none"
        autoComplete="current-password"
        secureTextEntry
        style={authStyles.input}
        value={password}
        onChangeText={setPassword}
        returnKeyType="done"
        onSubmitEditing={() => void submit()}
      />
      {error ? <Text style={authStyles.error}>{error}</Text> : null}
      <TouchableOpacity
        accessibilityRole="button"
        style={[authStyles.button, loading && authStyles.buttonDisabled]}
        disabled={loading}
        onPress={() => void submit()}
      >
        {loading ? <ActivityIndicator color="#fff" /> : null}
        <Text style={authStyles.buttonText}>{loading ? 'Entrando…' : 'Entrar'}</Text>
      </TouchableOpacity>
      <TouchableOpacity style={authStyles.link} onPress={() => navigation.navigate('RecuperarSenha')}>
        <Text style={authStyles.linkText}>Esqueci minha senha</Text>
      </TouchableOpacity>
      <TouchableOpacity style={authStyles.link} onPress={() => navigation.navigate('CriarConta')}>
        <Text style={authStyles.linkText}>Criar uma conta gratuita</Text>
      </TouchableOpacity>
    </AuthShell>
  )
}
