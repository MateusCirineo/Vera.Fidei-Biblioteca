'use client'

import { useRouter } from 'next/navigation'
import type { MatchReference } from '@/lib/types'
import { getPdfUrl } from '@/lib/api'
import { formatLanguage } from '@/lib/language'

export default function MatchReferenceCard({
  reference,
  quote,
  fallbackQuote,
}: {
  reference: MatchReference
  quote?: string
  fallbackQuote?: string
}) {
  const router = useRouter()
  const isPrimary = reference.is_primary_source

  const locationParts: string[] = []
  if (reference.collection) {
    let loc = reference.collection
    if (reference.volume) loc += ` vol. ${reference.volume}`
    locationParts.push(loc)
  }
  if (reference.column_start) locationParts.push(`col. ${reference.column_start}`)
  if (reference.chapter_or_section) locationParts.push(reference.chapter_or_section)
  if (reference.pdf_page) locationParts.push(`p. ${reference.pdf_page}`)

  function openPdfViewer() {
    if (!reference.pdf_file_id) return
    const fileUrl           = getPdfUrl(reference.pdf_file_id)   // URL limpa, sem âncora de página
    const page              = reference.pdf_page ?? 1
    const safeQuote         = (quote ?? '').slice(0, 800)
    // Recorte central do fallback: evita transições de chunk nas bordas, mais estável para highlight
    const fb     = fallbackQuote ?? ''
    const fbMid  = Math.floor(fb.length / 2)
    const fbHalf = 200
    const safeFallbackQuote = fb.slice(Math.max(0, fbMid - fbHalf), fbMid + fbHalf)
    const params            = new URLSearchParams({
      file: fileUrl,
      page: String(page),
      ...(safeQuote         ? { quote:         safeQuote         } : {}),
      ...(safeFallbackQuote ? { fallbackQuote: safeFallbackQuote } : {}),
    })
    router.push(`/viewer/pdf?${params.toString()}`)
  }

  return (
    <div
      className={`rounded-lg border p-4 space-y-3 ${
        isPrimary
          ? 'border-dourado/35 bg-vinho-escuro/25'
          : 'border-fundo-borda bg-fundo-card'
      }`}
    >
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              isPrimary
                ? 'bg-dourado/20 text-dourado'
                : 'bg-fundo text-texto-secundario'
            }`}
          >
            {isPrimary ? 'Fonte primária' : 'Fonte de apoio'}
          </span>
          {reference.language && (
            <span className="text-xs text-texto-secundario">
              {formatLanguage(reference.language)}
            </span>
          )}
        </div>
      </div>

      {/* Edition + Source */}
      <div className="space-y-0.5">
        {reference.edition_label && (
          <p className="text-sm text-texto">
            {reference.edition_label}
            {reference.source_label && (
              <span className="text-texto-secundario">
                {' '}
                · {reference.source_label}
              </span>
            )}
          </p>
        )}
        {locationParts.length > 0 && (
          <p className="text-sm text-texto-secundario">
            {locationParts.join(' · ')}
          </p>
        )}
      </div>

      {/* Editor / Translator */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-texto-terciario">
        <span>
          Editor:{' '}
          <span className="text-texto-secundario">
            {reference.editor ?? '—'}
          </span>
        </span>
        <span>
          Tradutor:{' '}
          <span className="text-texto-secundario">
            {reference.translator ?? '—'}
          </span>
        </span>
      </div>

      {/* Open PDF button */}
      {reference.pdf_file_id && (
        <button
          onClick={openPdfViewer}
          className="mt-1 inline-flex items-center gap-1.5 rounded-md border border-dourado/50 px-3 py-1.5 text-xs font-medium text-dourado transition-colors hover:bg-dourado/10"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-3.5 h-3.5">
            <path d="M10.75 2.75a.75.75 0 0 0-1.5 0v8.614L6.295 8.235a.75.75 0 1 0-1.09 1.03l4.25 4.5a.75.75 0 0 0 1.09 0l4.25-4.5a.75.75 0 0 0-1.09-1.03l-2.955 3.129V2.75Z" />
            <path d="M3.5 12.75a.75.75 0 0 0-1.5 0v2.5A2.75 2.75 0 0 0 4.75 18h10.5A2.75 2.75 0 0 0 18 15.25v-2.5a.75.75 0 0 0-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5Z" />
          </svg>
          Abrir trecho no PDF
        </button>
      )}
    </div>
  )
}
