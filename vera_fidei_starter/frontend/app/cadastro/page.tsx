'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import AuthShell from '@/components/auth/AuthShell'
import { getUser, register } from '@/lib/auth'

export default function CadastroPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    getUser().then((user) => {
      if (user) router.replace('/perfil')
    })
  }, [router])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password.length < 8) {
      setError('A senha deve ter pelo menos 8 caracteres.')
      return
    }
    setLoading(true)
    try {
      await register(name, email, password)
      window.location.replace('/perfil')
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao cadastrar')
    } finally {
      setLoading(false)
    }
  }

  return (
    <AuthShell
      title="Crie sua conta"
      subtitle={<>Seu perfil Vera.Fidei ser&aacute; aberto ao concluir o cadastro.</>}
      footer={
        <p className="text-center text-xs text-texto-terciario">
          J&aacute; tem conta?{' '}
          <Link href="/login" className="text-dourado hover:underline">
            Entrar
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <div>
          <label className="mb-1 block text-xs text-texto-secundario">Nome</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            minLength={2}
            autoComplete="name"
            className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
          />
        </div>
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
          <label className="mb-1 block text-xs text-texto-secundario">Senha</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete="new-password"
            className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
          />
          <p className="mt-1 text-xs text-texto-terciario">Mínimo de 8 caracteres</p>
        </div>

        {error && <p className="text-xs text-vermelho">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-dourado py-2.5 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro disabled:opacity-50"
        >
          {loading ? 'Criando conta...' : 'Criar conta'}
        </button>
      </form>
    </AuthShell>
  )
}
