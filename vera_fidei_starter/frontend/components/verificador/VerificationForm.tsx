'use client'

import { useState } from 'react'
import { verifyCitation } from '@/lib/api'
import type { VerifyCitationResponse } from '@/lib/types'
import VerificationResult from './VerificationResult'

export default function VerificationForm() {
  const [quote, setQuote] = useState('')
  const [attributedTo, setAttributedTo] = useState('')
  const [language, setLanguage] = useState('')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<VerifyCitationResponse | null>(null)
  const [submittedQuote, setSubmittedQuote] = useState<string>('')
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!quote.trim() || !attributedTo.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)
    setSubmittedQuote(quote.trim())

    try {
      const res = await verifyCitation(
        quote.trim(),
        attributedTo.trim(),
        language.trim() || undefined
      )
      setResult(res)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro desconhecido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label
            htmlFor="quote"
            className="block text-sm font-medium text-texto-secundario mb-1.5"
          >
            Citação
          </label>
          <textarea
            id="quote"
            value={quote}
            onChange={(e) => setQuote(e.target.value)}
            placeholder="Cole aqui a citação que deseja verificar…"
            rows={4}
            required
            minLength={3}
            className="w-full rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:border-dourado/60 focus:outline-none focus:ring-1 focus:ring-dourado/30 resize-none"
          />
        </div>

        <div>
          <label
            htmlFor="attributed"
            className="block text-sm font-medium text-texto-secundario mb-1.5"
          >
            Atribuída a
          </label>
          <input
            id="attributed"
            type="text"
            value={attributedTo}
            onChange={(e) => setAttributedTo(e.target.value)}
            placeholder="Ex: São Cipriano de Cartago"
            required
            minLength={2}
            className="w-full rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:border-dourado/60 focus:outline-none focus:ring-1 focus:ring-dourado/30"
          />
        </div>

        <div>
          <label
            htmlFor="language"
            className="block text-sm font-medium text-texto-secundario mb-1.5"
          >
            Idioma{' '}
            <span className="text-texto-terciario font-normal">(opcional)</span>
          </label>
          <input
            id="language"
            type="text"
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            placeholder="Ex: Latim, Português…"
            className="w-full rounded-lg border border-fundo-borda bg-fundo-card px-3 py-2.5 text-sm text-texto placeholder:text-texto-terciario focus:border-dourado/60 focus:outline-none focus:ring-1 focus:ring-dourado/30"
          />
        </div>

        <button
          type="submit"
          disabled={loading || !quote.trim() || !attributedTo.trim()}
          className="w-full rounded-lg bg-vinho px-4 py-3 text-sm font-semibold text-texto transition-colors hover:bg-vinho-claro disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg
                className="animate-spin w-4 h-4"
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
              Verificando…
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

      {result && <VerificationResult result={result} originalQuery={submittedQuote} />}
    </div>
  )
}
