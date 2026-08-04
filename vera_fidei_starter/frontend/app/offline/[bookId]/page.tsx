'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import type { OfflineBookEntry } from '@/lib/offlineBooks'
import { getOfflineBook, removeBookOffline } from '@/lib/offlineBooks'
import { formatLanguage } from '@/lib/language'

export default function OfflineReaderPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const [entry, setEntry] = useState<OfflineBookEntry | null>(null)
  const [loading, setLoading] = useState(true)
  const [showPt, setShowPt] = useState(true)

  useEffect(() => {
    getOfflineBook(Number(bookId))
      .then((e) => setEntry(e ?? null))
      .finally(() => setLoading(false))
  }, [bookId])

  async function handleRemove() {
    await removeBookOffline(Number(bookId))
    router.back()
  }

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <span className="animate-pulse text-sm text-texto-terciario">Carregando…</span>
      </div>
    )
  }

  if (!entry) {
    return (
      <div className="mx-auto max-w-2xl px-4 pt-12 text-center">
        <p className="text-texto-secundario">Obra não encontrada no armazenamento offline.</p>
        <button
          type="button"
          onClick={() => router.back()}
          className="mt-4 text-sm text-dourado hover:underline"
        >
          Voltar
        </button>
      </div>
    )
  }

  const hasPt = entry.chunks.some((c) => c.translation_pt)

  return (
    <div className="mx-auto max-w-2xl px-4 pb-20 pt-6">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between gap-4">
        <button
          type="button"
          onClick={() => router.back()}
          className="mt-1 shrink-0 text-sm text-texto-secundario hover:text-texto"
        >
          ← Voltar
        </button>
        <button
          type="button"
          onClick={handleRemove}
          className="shrink-0 rounded border border-red-800/40 px-2 py-1 text-[10px] text-red-400 hover:bg-red-900/20"
        >
          Remover offline
        </button>
      </div>

      <div className="mb-1 rounded-lg border border-dourado/20 bg-dourado/5 p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
          Leitura offline — trechos indexados
        </p>
        <h1 className="mt-2 font-garamond text-2xl font-semibold leading-tight text-texto">
          {entry.title}
        </h1>
        {entry.author && (
          <p className="mt-1 text-sm text-texto-secundario">{entry.author}</p>
        )}
        <div className="mt-2 flex flex-wrap gap-3 text-xs text-texto-terciario">
          {entry.edition_label && <span>{entry.edition_label}</span>}
          {entry.language && <span>{formatLanguage(entry.language)}</span>}
          <span>{entry.total_chunks} trechos</span>
          <span className="italic">
            Salvo em {new Date(entry.saved_at).toLocaleDateString('pt-BR')}
          </span>
        </div>

        {hasPt && (
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={() => setShowPt(true)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                showPt ? 'bg-dourado/20 text-dourado' : 'text-texto-terciario hover:text-texto'
              }`}
            >
              Português
            </button>
            <button
              type="button"
              onClick={() => setShowPt(false)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition-colors ${
                !showPt ? 'bg-dourado/20 text-dourado' : 'text-texto-terciario hover:text-texto'
              }`}
            >
              Original
            </button>
          </div>
        )}
      </div>

      <p className="mb-4 mt-2 rounded border border-amber-900/30 bg-amber-950/20 px-3 py-2 text-[10px] text-amber-400/80">
        Estes trechos são fragmentos do texto já extraído e indexado para verificação.
        O arquivo original permanece no servidor — este modo permite estudo offline sem download de obras protegidas.
      </p>

      {/* Chunks */}
      <div className="space-y-4">
        {entry.chunks.map((chunk, i) => {
          const displayText = hasPt && showPt && chunk.translation_pt
            ? chunk.translation_pt
            : chunk.text
          const isTranslation = hasPt && showPt && !!chunk.translation_pt

          return (
            <div
              key={chunk.chunk_id}
              className="rounded-lg border border-fundo-borda bg-fundo-card p-4"
            >
              <div className="mb-2 flex flex-wrap items-center gap-2 text-[10px] text-texto-terciario">
                <span className="font-mono">#{i + 1}</span>
                {chunk.chapter_or_section && <span>{chunk.chapter_or_section}</span>}
                {chunk.pdf_page != null && <span>p. {chunk.pdf_page}</span>}
                {chunk.volume != null && <span>vol. {chunk.volume}</span>}
                {isTranslation && (
                  <span className="rounded bg-dourado/10 px-1.5 py-0.5 text-dourado">PT</span>
                )}
              </div>
              <p className={`text-sm leading-relaxed ${isTranslation ? 'text-texto' : 'text-texto-secundario italic'}`}>
                {displayText}
              </p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
