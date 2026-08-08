'use client'

import { Suspense, useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'
import AuthShell from '@/components/auth/AuthShell'
import { verifyEmail } from '@/lib/auth'

function VerifyContent() {
  const params = useSearchParams()
  const token = params.get('token') ?? ''
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')
  const ran = useRef(false)

  useEffect(() => {
    if (ran.current) return
    ran.current = true
    if (!token) {
      setStatus('error')
      setMessage('Link inválido. Nenhum token encontrado.')
      return
    }
    verifyEmail(token)
      .then(() => setStatus('success'))
      .catch((err: unknown) => {
        setStatus('error')
        setMessage(err instanceof Error ? err.message : 'Erro ao verificar e-mail')
      })
  }, [token])

  if (status === 'loading') {
    return (
      <div className="py-6 text-center">
        <p className="text-sm text-texto-secundario">Verificando seu e-mail...</p>
      </div>
    )
  }

  if (status === 'success') {
    return (
      <div className="rounded-lg border border-dourado/30 bg-dourado/8 px-4 py-5 text-center">
        <p className="text-sm font-medium text-dourado">E-mail verificado com sucesso</p>
        <p className="mt-2 text-xs leading-relaxed text-texto-secundario">
          Sua conta está confirmada. Bem-vindo à Biblioteca Católica Digital.
        </p>
        <Link
          href="/biblioteca"
          className="mt-4 inline-block rounded-lg bg-dourado px-5 py-2 text-sm font-medium text-fundo hover:bg-dourado-claro"
        >
          Acessar a Biblioteca
        </Link>
      </div>
    )
  }

  return (
    <div className="rounded-lg border border-vermelho/30 bg-vermelho/5 px-4 py-5 text-center">
      <p className="text-sm text-vermelho">{message || 'Não foi possível verificar o e-mail.'}</p>
      <p className="mt-2 text-xs text-texto-secundario">
        O link pode ter expirado ou já ter sido utilizado.
      </p>
      <Link href="/perfil" className="mt-3 inline-block text-xs text-dourado hover:underline">
        Reenviar verificação no perfil
      </Link>
    </div>
  )
}

export default function VerificarEmailPage() {
  return (
    <AuthShell
      title="Verificação de e-mail"
      subtitle="Aguarde enquanto confirmamos seu endereço."
      footer={
        <p className="text-center text-xs text-texto-terciario">
          <Link href="/login" className="text-dourado hover:underline">
            Voltar ao login
          </Link>
        </p>
      }
    >
      <Suspense fallback={<p className="py-8 text-center text-sm text-texto-terciario">Carregando...</p>}>
        <VerifyContent />
      </Suspense>
    </AuthShell>
  )
}
