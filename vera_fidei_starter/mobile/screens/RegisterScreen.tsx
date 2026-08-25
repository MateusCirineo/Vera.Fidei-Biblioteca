import { useState } from 'react'
import { ActivityIndicator, Text, TextInput, TouchableOpacity } from 'react-native'

import { useAuth } from '../auth/AuthContext'
import { DISTRIBUTION_MODE } from '../lib/runtime-config'
import AuthShell, { authStyles } from './AuthShell'

export default function RegisterScreen({ navigation }: { navigation: any }) {
  const { register } = useAuth()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function submit() {
    if (name.trim().length < 2 || !email.trim()) {
      setError('Informe seu nome e um e-mail válido.')
      return
    }
    if (password.length < 8) {
      setError('A senha precisa ter pelo menos 8 caracteres.')
      return
    }
    if (password !== confirmation) {
      setError('As senhas não coincidem.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await register(name, email, password)
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível criar a conta.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Criar conta"
      subtitle={DISTRIBUTION_MODE === 'reader'
        ? 'Crie sua conta gratuita para acessar o Vera Fidei.'
        : 'Comece no plano Fiel e evolua quando precisar.'}
    >
      <Text style={authStyles.label}>Nome</Text>
      <TextInput autoComplete="name" style={authStyles.input} value={name} onChangeText={setName} />
      <Text style={authStyles.label}>E-mail</Text>
      <TextInput
        autoCapitalize="none"
        autoComplete="email"
        inputMode="email"
        keyboardType="email-address"
        style={authStyles.input}
        value={email}
        onChangeText={setEmail}
      />
      <Text style={authStyles.label}>Senha</Text>
      <TextInput autoComplete="new-password" secureTextEntry style={authStyles.input} value={password} onChangeText={setPassword} />
      <Text style={authStyles.label}>Repita a senha</Text>
      <TextInput secureTextEntry style={authStyles.input} value={confirmation} onChangeText={setConfirmation} onSubmitEditing={() => void submit()} />
      {error ? <Text style={authStyles.error}>{error}</Text> : null}
      <TouchableOpacity style={[authStyles.button, loading && authStyles.buttonDisabled]} disabled={loading} onPress={() => void submit()}>
        {loading ? <ActivityIndicator color="#fff" /> : null}
        <Text style={authStyles.buttonText}>{loading ? 'Criando…' : 'Criar conta'}</Text>
      </TouchableOpacity>
      <TouchableOpacity style={authStyles.link} onPress={() => navigation.goBack()}>
        <Text style={authStyles.linkText}>Já tenho conta</Text>
      </TouchableOpacity>
    </AuthShell>
  )
}
