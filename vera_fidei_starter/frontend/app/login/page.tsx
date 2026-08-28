'use client'

import { Suspense, useEffect, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import AuthShell from '@/components/auth/AuthShell'
import { getUser, login } from '@/lib/auth'

function safeRedirectPath(value: string | null) {
  if (!value || !value.startsWith('/') || value.startsWith('//')) {
    return '/perfil'
  }
  const pathname = value.split(/[?#]/, 1)[0].replace(/\/+$/, '') || '/'
  if (['/login', '/cadastro', '/esqueci-senha', '/redefinir-senha', '/verificar-email'].includes(pathname)) {
    return '/perfil'
  }
  return value
}

function LoginForm() {
  const params = useSearchParams()
  const redirect = safeRedirectPath(params.get('redirect'))

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let active = true
    getUser().then((user) => {
      if (active && user) window.location.replace(redirect)
    })
    return () => {
      active = false
    }
  }, [redirect])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setSuccess('')
    setLoading(true)
    try {
      await login(email, password)
      setSuccess('Conta confirmada. Abrindo seu perfil...')
      window.location.replace(redirect)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao entrar')
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="mb-1 block text-xs text-texto-secundario">E-mail</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoComplete="email"
          className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
        />
      </div>
      <div>
        <div className="mb-1 flex items-center justify-between">
          <label className="text-xs text-texto-secundario">Senha</label>
          <Link href="/esqueci-senha" className="text-[11px] text-dourado hover:underline">
            Esqueci minha senha
          </Link>
        </div>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="current-password"
          className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
        />
      </div>

      {error && <p className="text-xs text-vermelho">{error}</p>}
      {success && (
        <p role="status" className="text-xs text-dourado">
          {success}{' '}
          <a href={redirect} className="underline">
            Continuar
          </a>
        </p>
      )}

      <button
        type="submit"
        disabled={loading || Boolean(success)}
        className="rounded-lg bg-dourado py-2.5 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro disabled:opacity-50"
      >
        {success ? 'Conta confirmada' : loading ? 'Entrando...' : 'Entrar'}
      </button>
    </form>
  )
}

export default function LoginPage() {
  return (
    <AuthShell
      title="Entre na sua conta"
      subtitle={<>Acesse seu perfil, hist&oacute;rico e verifica&ccedil;&otilde;es salvas.</>}
      footer={
        <p className="text-center text-xs text-texto-terciario">
          N&atilde;o tem conta?{' '}
          <Link href="/cadastro" className="text-dourado hover:underline">
            Cadastre-se
          </Link>
        </p>
      }
    >
      <Suspense fallback={<p className="py-8 text-center text-sm text-texto-terciario">Carregando...</p>}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  )
}
