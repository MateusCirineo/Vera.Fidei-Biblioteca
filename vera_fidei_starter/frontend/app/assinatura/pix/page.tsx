'use client'

import dynamic from 'next/dynamic'
import Image from 'next/image'
import Link from 'next/link'
import { Suspense, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { getPixSubscriptionRequest, type PixSubscriptionRequest } from '@/lib/auth'

const QRCodeSVG = dynamic(
  () => import('qrcode.react').then((mod) => mod.QRCodeSVG),
  { ssr: false },
)

function PixContent() {
  const params = useSearchParams()
  const ref = params.get('ref') ?? ''
  const [request, setRequest] = useState<PixSubscriptionRequest | null>(null)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState('')

  useEffect(() => {
    if (!ref) return
    getPixSubscriptionRequest(ref)
      .then(setRequest)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Erro ao carregar Pix.'))
  }, [ref])

  async function copy(value: string, label: string) {
    await navigator.clipboard.writeText(value)
    setCopied(label)
    setTimeout(() => setCopied(''), 2200)
  }

  return (
    <div className="mx-auto flex w-full max-w-md flex-col items-center px-4 pb-28 pt-8">
      <Image
        src="/branding/Logo-VF-seal.png"
        alt="Vera.Fidei"
        width={144}
        height={144}
        priority
        className="h-24 w-24 rounded-full shadow-[0_0_34px_rgba(201,168,76,0.18)]"
      />
      <div className="mt-4 text-center">
        <p className="font-garamond text-4xl font-semibold leading-none text-dourado">
          Vera.Fidei
        </p>
        <p className="mt-2 text-xs font-medium uppercase tracking-[0.22em] text-dourado-claro">
          Assinatura via Pix
        </p>
      </div>

      <div className="mt-8 w-full rounded-lg border border-dourado/25 bg-fundo-card p-5 shadow-[0_18px_70px_rgba(0,0,0,0.32)]">
        {!ref ? (
          <div className="text-center">
            <h1 className="font-garamond text-2xl text-texto">Nao foi possivel abrir o Pix</h1>
            <p className="mt-2 text-sm text-vermelho">Referencia da assinatura ausente.</p>
            <Link
              href="/planos"
              className="mt-5 inline-flex rounded-md bg-dourado px-4 py-2 text-sm font-medium text-fundo"
            >
              Voltar aos planos
            </Link>
          </div>
        ) : error ? (
          <div className="text-center">
            <h1 className="font-garamond text-2xl text-texto">Nao foi possivel abrir o Pix</h1>
            <p className="mt-2 text-sm text-vermelho">{error}</p>
            <Link
              href="/planos"
              className="mt-5 inline-flex rounded-md bg-dourado px-4 py-2 text-sm font-medium text-fundo"
            >
              Voltar aos planos
            </Link>
          </div>
        ) : !request ? (
          <p className="py-8 text-center text-sm text-texto-terciario">Carregando Pix...</p>
        ) : (
          <>
            <div className="text-center">
              <h1 className="font-garamond text-2xl text-texto">
                Plano {request.plan_name}
              </h1>
              <p className="mt-1 font-garamond text-4xl font-semibold text-dourado">
                {request.amount_label}
              </p>
              <p className="mt-2 text-xs text-texto-terciario">
                Referencia: <span className="text-texto">{request.reference_code}</span>
              </p>
            </div>

            {request.pix_payload && (
              <div className="mt-5 flex justify-center">
                <div className="rounded-lg bg-white p-3">
                  <QRCodeSVG
                    value={request.pix_payload}
                    size={190}
                    bgColor="#ffffff"
                    fgColor="#111111"
                    level="M"
                  />
                </div>
              </div>
            )}

            <div className="mt-5 space-y-3">
              <div className="rounded-md border border-fundo-borda bg-fundo p-3">
                <p className="text-xs text-texto-terciario">Recebedor</p>
                <p className="mt-1 text-sm text-texto">{request.recipient_name}</p>
                <p className="mt-0.5 text-xs text-texto-terciario">{request.recipient_bank}</p>
              </div>

              <button
                type="button"
                onClick={() => copy(request.pix_key, 'pix')}
                className="w-full rounded-md bg-dourado px-4 py-3 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro"
              >
                {copied === 'pix' ? 'Chave Pix copiada' : 'Copiar chave Pix'}
              </button>

              {request.pix_payload && (
                <button
                  type="button"
                  onClick={() => copy(request.pix_payload ?? '', 'payload')}
                  className="w-full rounded-md border border-dourado/40 px-4 py-3 text-sm font-medium text-dourado transition-colors hover:bg-dourado hover:text-fundo"
                >
                  {copied === 'payload' ? 'Codigo Pix copiado' : 'Copiar Pix copia e cola'}
                </button>
              )}
            </div>

            <div className="mt-5 rounded-md border border-fundo-borda bg-fundo/60 p-3 text-xs leading-relaxed text-texto-terciario">
              Pague o valor do plano mensal e guarde a referencia acima junto ao comprovante.
              A liberacao do plano acontece apos confirmacao do pagamento.
            </div>

            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Link
                href="/perfil"
                className="rounded-md border border-fundo-borda px-4 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
              >
                Ir para perfil
              </Link>
              <Link
                href="/planos"
                className="rounded-md border border-fundo-borda px-4 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
              >
                Ver planos
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

export default function PixSubscriptionPage() {
  return (
    <Suspense fallback={<p className="py-12 text-center text-sm text-texto-terciario">Carregando...</p>}>
      <PixContent />
    </Suspense>
  )
}
