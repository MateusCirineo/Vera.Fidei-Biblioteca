'use client'

import { Suspense, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import AuthShell from '@/components/auth/AuthShell'
import { resetPassword } from '@/lib/auth'

function ResetForm() {
  const params = useSearchParams()
  const token = params.get('token') ?? ''

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    if (password !== confirm) {
      setError('As senhas não coincidem.')
      return
    }
    if (password.length < 8) {
      setError('A senha deve ter pelo menos 8 caracteres.')
      return
    }
    if (!token) {
      setError('Link inválido. Solicite um novo link de redefinição.')
      return
    }
    setLoading(true)
    try {
      await resetPassword(token, password)
      setDone(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao redefinir senha')
    } finally {
      setLoading(false)
    }
  }

  if (!token) {
    return (
      <div className="rounded-lg border border-vermelho/30 bg-vermelho/5 px-4 py-5 text-center">
        <p className="text-sm text-vermelho">Link inválido ou expirado.</p>
        <Link href="/esqueci-senha" className="mt-3 inline-block text-xs text-dourado hover:underline">
          Solicitar novo link
        </Link>
      </div>
    )
  }

  if (done) {
    return (
      <div className="rounded-lg border border-dourado/30 bg-dourado/8 px-4 py-5 text-center">
        <p className="text-sm font-medium text-dourado">Senha redefinida com sucesso</p>
        <p className="mt-2 text-xs text-texto-secundario">
          Você já pode entrar com sua nova senha.
        </p>
        <Link
          href="/login"
          className="mt-4 inline-block rounded-lg bg-dourado px-5 py-2 text-sm font-medium text-fundo hover:bg-dourado-claro"
        >
          Ir para o login
        </Link>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      <div>
        <label className="mb-1 block text-xs text-texto-secundario">Nova senha</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          autoComplete="new-password"
          minLength={8}
          className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
        />
      </div>
      <div>
        <label className="mb-1 block text-xs text-texto-secundario">Confirmar nova senha</label>
        <input
          type="password"
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          required
          autoComplete="new-password"
          minLength={8}
          className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
        />
      </div>

      {error && <p className="text-xs text-vermelho">{error}</p>}

      <button
        type="submit"
        disabled={loading}
        className="rounded-lg bg-dourado py-2.5 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro disabled:opacity-50"
      >
        {loading ? 'Salvando...' : 'Redefinir senha'}
      </button>
    </form>
  )
}

export default function RedefinirSenhaPage() {
  return (
    <AuthShell
      title="Redefinir senha"
      subtitle="Digite sua nova senha abaixo."
      footer={
        <p className="text-center text-xs text-texto-terciario">
          <Link href="/login" className="text-dourado hover:underline">
            Voltar ao login
          </Link>
        </p>
      }
    >
      <Suspense fallback={<p className="py-8 text-center text-sm text-texto-terciario">Carregando...</p>}>
        <ResetForm />
      </Suspense>
    </AuthShell>
  )
}
