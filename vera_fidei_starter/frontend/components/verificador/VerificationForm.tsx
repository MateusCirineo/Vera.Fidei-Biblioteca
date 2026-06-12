'use client'

import { useEffect, useRef, useState } from 'react'
import { verifyCitation } from '@/lib/api'
import { getUser } from '@/lib/auth'
import type { VerifyCitationResponse } from '@/lib/types'
import VerificationResult from './VerificationResult'

const examples = [
  {
    label: 'Clemente',
    quote: 'Cristo está entre os humildes, e não entre aqueles que se sobrepõem ao seu rebanho.',
    author: 'São Clemente de Roma',
    language: 'Português',
  },
  {
    label: 'Irineu',
    quote: 'Lêem coisas que não foram escritas e, como se costuma dizer, trançando cordas com areia.',
    author: 'Santo Irineu de Lião',
    language: 'Português',
  },
]

export default function VerificationForm() {
  const quoteRef = useRef<HTMLTextAreaElement>(null)
  const attributedRef = useRef<HTMLInputElement>(null)
  const languageRef = useRef<HTMLInputElement>(null)
  const [quote, setQuote] = useState('')
  const [attributedTo, setAttributedTo] = useState('')
  const [language, setLanguage] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<VerifyCitationResponse | null>(null)
  const [submittedQuote, setSubmittedQuote] = useState<string>('')
  const [error, setError] = useState<string | null>(null)
  const [hydrated, setHydrated] = useState(false)
  const [userPlan, setUserPlan] = useState<string | undefined>(undefined)

  useEffect(() => {
    setHydrated(true)
    getUser().then(u => setUserPlan(u?.plan)).catch(() => {})
  }, [])

  async function runVerification(form: HTMLFormElement) {
    const formData = new FormData(form)
    const currentQuote = (formData.get('quote')?.toString() || quote).trim()
    const currentAttributedTo = (formData.get('attributed')?.toString() || attributedTo).trim()
    const currentLanguage = (formData.get('language')?.toString() || language).trim()
    if (!currentQuote || !currentAttributedTo) {
      setError('Preencha a citação e o autor antes de verificar.')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)
    setQuote(currentQuote)
    setAttributedTo(currentAttributedTo)
    setLanguage(currentLanguage)
    setSubmittedQuote(currentQuote)

    try {
      const res = await verifyCitation(
        currentQuote,
        currentAttributedTo,
        currentLanguage || undefined
      )
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    void runVerification(e.currentTarget)
  }

  function applyExample(example: typeof examples[number]) {
    if (quoteRef.current) quoteRef.current.value = example.quote
    if (attributedRef.current) attributedRef.current.value = example.author
    if (languageRef.current) languageRef.current.value = example.language
    setQuote(example.quote)
    setAttributedTo(example.author)
    setLanguage(example.language)
    setResult(null)
    setError(null)
  }

  return (
    <div className="space-y-6">
      <section className="border-y border-fundo-borda py-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
          Ferramenta apologética
        </p>
        <h2 className="mt-1 font-garamond text-2xl font-medium text-texto">
          Confronte a atribuição com o acervo indexado
        </h2>
        <p className="mt-1 max-w-2xl text-sm leading-relaxed text-texto-secundario">
          O Vera.Fidei procura correspondência, fonte, edição, idioma, tradução e trecho próximo para separar citação real, paráfrase e atribuição duvidosa.
        </p>
      </section>

      <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border border-fundo-borda bg-fundo-card p-4">
        <div className="border-b border-fundo-borda pb-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-garamond text-xl font-medium text-texto">
                Verificação de citação
              </p>
              <p className="mt-1 text-sm leading-relaxed text-texto-secundario">
                Informe o texto atribuído e o autor para confrontar com o acervo indexado.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              {examples.map(example => (
                <button
                  key={example.label}
                  type="button"
                  onClick={() => applyExample(example)}
                  className="rounded-md border border-fundo-borda px-2.5 py-1 text-xs text-texto-terciario transition-colors hover:border-dourado/35 hover:text-dourado"
                >
                  Exemplo: {example.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div>
          <label
            htmlFor="quote"
            className="mb-1.5 block text-sm font-medium text-texto-secundario"
          >
            Citação a verificar
          </label>
          <textarea
            id="quote"
            name="quote"
            ref={quoteRef}
            defaultValue=""
            placeholder="Cole aqui a citação que deseja verificar..."
            rows={5}
            required
            minLength={3}
            className="w-full resize-none rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm leading-relaxed text-texto placeholder:text-texto-terciario focus:border-dourado/60 focus:outline-none focus:ring-1 focus:ring-dourado/30"
          />
        </div>

        <div className="grid gap-4 sm:grid-cols-[minmax(0,1fr)_180px]">
          <div>
            <label
              htmlFor="attributed"
              className="mb-1.5 block text-sm font-medium text-texto-secundario"
            >
              Atribuída a
            </label>
            <input
              id="attributed"
              name="attributed"
              ref={attributedRef}
              type="text"
              defaultValue=""
              placeholder="Ex: São Cipriano de Cartago"
              required
              minLength={2}
              className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:border-dourado/60 focus:outline-none focus:ring-1 focus:ring-dourado/30"
            />
          </div>

          <div>
            <label
              htmlFor="language"
              className="mb-1.5 block text-sm font-medium text-texto-secundario"
            >
              Idioma{' '}
              <span className="font-normal text-texto-terciario">(opcional)</span>
            </label>
            <input
              id="language"
              name="language"
              ref={languageRef}
              type="text"
              defaultValue=""
              placeholder="Ex: Latim"
              className="w-full rounded-lg border border-fundo-borda bg-fundo px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:border-dourado/60 focus:outline-none focus:ring-1 focus:ring-dourado/30"
            />
          </div>
        </div>

        <button
          type="button"
          onClick={(e) => {
            const form = e.currentTarget.form
            if (form) void runVerification(form)
          }}
          disabled={loading || !hydrated}
          className="w-full rounded-lg border border-dourado/30 bg-vinho px-4 py-3 text-sm font-semibold text-texto transition-colors hover:bg-vinho-claro disabled:cursor-not-allowed disabled:opacity-50"
        >
          {!hydrated ? (
            'Preparando verificador...'
          ) : loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg
                className="h-4 w-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Verificando...
            </span>
          ) : (
            'Verificar citação'
          )}
        </button>
      </form>

      {error && (
        <div className="rounded-lg border border-red-800/50 bg-red-900/20 p-4">
          <p className="text-sm text-red-300">{error}</p>
        </div>
      )}

      {result && <VerificationResult result={result} originalQuery={submittedQuote} userPlan={userPlan} />}
    </div>
  )
}
