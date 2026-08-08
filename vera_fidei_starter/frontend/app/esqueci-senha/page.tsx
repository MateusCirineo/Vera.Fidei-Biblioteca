'use client'

import { useState } from 'react'
import Link from 'next/link'
import AuthShell from '@/components/auth/AuthShell'
import { forgotPassword } from '@/lib/auth'

export default function EsqueciSenhaPage() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await forgotPassword(email)
      setSent(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao enviar o e-mail')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Esqueceu a senha?"
      subtitle="Digite seu e-mail e enviaremos um link para redefinir sua senha."
      footer={
        <p className="text-center text-xs text-texto-terciario">
          Lembrou a senha?{' '}
          <Link href="/login" className="text-dourado hover:underline">
            Entrar
          </Link>
        </p>
      }
    >
      {sent ? (
        <div className="rounded-lg border border-dourado/30 bg-dourado/8 px-4 py-5 text-center">
          <p className="text-sm font-medium text-dourado">E-mail enviado</p>
          <p className="mt-2 text-xs leading-relaxed text-texto-secundario">
            Se esse endereço estiver cadastrado, você receberá um link em breve.
            Verifique também a caixa de spam.
          </p>
          <Link
            href="/login"
            className="mt-4 inline-block text-xs text-dourado hover:underline"
          >
            Voltar ao login
          </Link>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="mb-1 block text-xs text-texto-secundario">E-mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
              placeholder="seu@email.com"
              className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
            />
          </div>

          {error && <p className="text-xs text-vermelho">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-dourado py-2.5 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro disabled:opacity-50"
          >
            {loading ? 'Enviando...' : 'Enviar link de redefinição'}
          </button>
        </form>
      )}
    </AuthShell>
  )
}
