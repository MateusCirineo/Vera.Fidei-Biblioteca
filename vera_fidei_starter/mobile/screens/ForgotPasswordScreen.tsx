import { useState } from 'react'
import { ActivityIndicator, Text, TextInput, TouchableOpacity } from 'react-native'

import { requestPasswordReset } from '../lib/api'
import AuthShell, { authStyles } from './AuthShell'

export default function ForgotPasswordScreen({ navigation }: { navigation: any }) {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function submit() {
    if (!email.trim()) {
      setError('Informe seu e-mail.')
      return
    }
    setLoading(true)
    setError('')
    setMessage('')
    try {
      await requestPasswordReset(email.trim().toLowerCase())
      setMessage('Se houver uma conta com esse e-mail, você receberá as instruções de recuperação.')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Não foi possível solicitar a recuperação.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell title="Recuperar senha" subtitle="Enviaremos um link seguro para o e-mail cadastrado.">
      <Text style={authStyles.label}>E-mail</Text>
      <TextInput
        autoCapitalize="none"
        autoComplete="email"
        inputMode="email"
        keyboardType="email-address"
        style={authStyles.input}
        value={email}
        onChangeText={setEmail}
        onSubmitEditing={() => void submit()}
      />
      {error ? <Text style={authStyles.error}>{error}</Text> : null}
      {message ? <Text style={authStyles.success}>{message}</Text> : null}
      <TouchableOpacity style={[authStyles.button, loading && authStyles.buttonDisabled]} disabled={loading} onPress={() => void submit()}>
        {loading ? <ActivityIndicator color="#fff" /> : null}
        <Text style={authStyles.buttonText}>{loading ? 'Enviando…' : 'Enviar link'}</Text>
      </TouchableOpacity>
      <TouchableOpacity style={authStyles.link} onPress={() => navigation.goBack()}>
        <Text style={authStyles.linkText}>Voltar ao login</Text>
      </TouchableOpacity>
    </AuthShell>
  )
}
