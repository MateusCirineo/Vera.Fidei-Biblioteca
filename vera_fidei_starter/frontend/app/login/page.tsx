'use client'

import { useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { login } from '@/lib/auth'

export default function LoginPage() {
  const router = useRouter()
  const params = useSearchParams()
  const redirect = params.get('redirect') ?? '/verificador'

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(email, password)
      router.push(redirect)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao entrar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="font-eb-garamond text-3xl text-dourado text-center mb-2">Vera.Fidei</h1>
        <p className="text-texto-terciario text-sm text-center mb-8">Entre na sua conta</p>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label className="text-xs text-texto-secundario mb-1 block">E-mail</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-fundo-card border border-fundo-borda rounded-lg px-3 py-2 text-sm text-texto focus:outline-none focus:border-dourado"
            />
          </div>
          <div>
            <label className="text-xs text-texto-secundario mb-1 block">Senha</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full bg-fundo-card border border-fundo-borda rounded-lg px-3 py-2 text-sm text-texto focus:outline-none focus:border-dourado"
            />
          </div>

          {error && <p className="text-xs text-vermelho">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="bg-dourado text-fundo font-medium text-sm rounded-lg py-2.5 hover:bg-dourado/90 transition-colors disabled:opacity-50"
          >
            {loading ? 'Entrando…' : 'Entrar'}
          </button>
        </form>

        <p className="text-center text-xs text-texto-terciario mt-6">
          Não tem conta?{' '}
          <Link href="/cadastro" className="text-dourado hover:underline">
            Cadastre-se
          </Link>
        </p>
      </div>
    </div>
  )
}
