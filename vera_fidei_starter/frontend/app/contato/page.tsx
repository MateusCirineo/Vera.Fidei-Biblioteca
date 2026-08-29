'use client'

import { useState } from 'react'
import Link from 'next/link'
import BrandHeader from '@/components/BrandHeader'
import { fetchWithTimeout } from '@/lib/http'
import { getPublicApiBase } from '@/lib/api-base'

const BASE = getPublicApiBase()

const channels = [
  {
    label: 'E-mail',
    value: 'vera.fidei661@gmail.com',
    href: 'mailto:vera.fidei661@gmail.com?subject=Suporte%20Vera.Fidei',
  },
  {
    label: 'Instagram',
    value: '@vera.fidei',
    href: 'https://www.instagram.com/vera.fidei',
  },
  {
    label: 'YouTube',
    value: '@mattcirineo',
    href: 'https://www.youtube.com/@mattcirineo',
  },
]

const supportTips = [
  'Para assinatura, envie o e-mail da conta e o plano escolhido.',
  'Para erro no verificador, envie o texto consultado e o horário aproximado.',
  'Para privacidade, diga qual direito deseja exercer e qual conta está envolvida.',
]

export default function ContatoPage() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [subject, setSubject] = useState('')
  const [message, setMessage] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await fetchWithTimeout(`${BASE}/auth/contact`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, subject, message }),
      }, {
        timeoutMessage: 'O envio da mensagem demorou demais. Verifique sua conexão e tente novamente.',
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data.detail ?? 'Erro ao enviar mensagem')
      }
      setSent(true)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Erro ao enviar mensagem')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:py-10">
      <BrandHeader
        title="Contato e suporte"
        description="Canais para dúvidas, assinatura, privacidade e suporte técnico."
      />

      <section className="grid gap-3 sm:grid-cols-3">
        {channels.map((channel) => (
          <a
            key={channel.label}
            href={channel.href}
            target={channel.href.startsWith('http') ? '_blank' : undefined}
            rel={channel.href.startsWith('http') ? 'noreferrer' : undefined}
            className="rounded-lg border border-fundo-borda bg-fundo-card p-4 transition-colors hover:border-dourado/45"
          >
            <p className="text-xs uppercase tracking-[0.18em] text-texto-terciario">
              {channel.label}
            </p>
            <p className="mt-2 break-words text-sm font-medium text-texto">
              {channel.value}
            </p>
          </a>
        ))}
      </section>

      {/* Contact form */}
      <section className="mt-8 rounded-lg border border-fundo-borda bg-fundo-card p-5">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Enviar mensagem
        </h2>
        {sent ? (
          <div className="mt-5 rounded-lg border border-dourado/30 bg-dourado/8 px-4 py-5 text-center">
            <p className="text-sm font-medium text-dourado">Mensagem enviada</p>
            <p className="mt-2 text-xs text-texto-secundario">
              Responderemos em breve no e-mail informado.
            </p>
            <button
              onClick={() => { setSent(false); setName(''); setEmail(''); setSubject(''); setMessage('') }}
              className="mt-3 text-xs text-dourado hover:underline"
            >
              Enviar outra mensagem
            </button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-5 flex flex-col gap-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-xs text-texto-secundario">Nome</label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                  minLength={2}
                  maxLength={200}
                  className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-texto-secundario">E-mail</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
                />
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs text-texto-secundario">Assunto</label>
              <input
                type="text"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                required
                minLength={2}
                maxLength={200}
                className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs text-texto-secundario">Mensagem</label>
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                required
                minLength={10}
                maxLength={4000}
                rows={5}
                className="w-full resize-y rounded-lg border border-fundo-borda bg-fundo px-3 py-2 text-sm text-texto transition-colors placeholder:text-texto-terciario focus:border-dourado focus:outline-none"
              />
              <p className="mt-1 text-right text-[11px] text-texto-terciario">{message.length}/4000</p>
            </div>

            {error && <p className="text-xs text-vermelho">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="self-start rounded-lg bg-dourado px-6 py-2.5 text-sm font-medium text-fundo transition-colors hover:bg-dourado-claro disabled:opacity-50"
            >
              {loading ? 'Enviando...' : 'Enviar mensagem'}
            </button>
          </form>
        )}
      </section>

      <section className="mt-8 rounded-lg border border-fundo-borda bg-fundo-card p-5">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Como agilizar o atendimento
        </h2>
        <div className="mt-4 grid gap-3">
          {supportTips.map((tip) => (
            <div key={tip} className="flex gap-3 text-sm leading-relaxed text-texto-secundario">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-dourado" />
              <p>{tip}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8 space-y-4">
        <h2 className="font-garamond text-2xl font-semibold text-dourado">
          Links úteis
        </h2>
        <div className="flex flex-wrap gap-3">
          <Link
            href="/planos"
            className="rounded-md border border-dourado/40 px-4 py-2.5 text-sm font-semibold text-dourado transition-colors hover:bg-dourado hover:text-fundo"
          >
            Planos
          </Link>
          <Link
            href="/termos"
            className="rounded-md border border-fundo-borda px-4 py-2.5 text-sm font-semibold text-texto-secundario transition-colors hover:border-dourado/40 hover:text-dourado"
          >
            Termos de uso
          </Link>
          <Link
            href="/privacidade"
            className="rounded-md border border-fundo-borda px-4 py-2.5 text-sm font-semibold text-texto-secundario transition-colors hover:border-dourado/40 hover:text-dourado"
          >
            Privacidade
          </Link>
        </div>
      </section>
    </div>
  )
}
