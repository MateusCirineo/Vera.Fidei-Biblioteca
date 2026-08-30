'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import {
  deleteHistoricoEntry,
  getHistorico,
} from '@/lib/auth'
import type { MatchReference } from '@/lib/types'

interface HistoricoEntry {
  id: number
  citation_text: string
  attributed_to: string | null
  status_code: string | null
  label: string | null
  confidence: string | null
  author: string | null
  work: string | null
  matched_excerpt: string | null
  reference: MatchReference | null
  variant_analysis?: string | null
  created_at: string | null
}

const PLAN_ORDER = ['fiel', 'catequista', 'apologeta', 'patristico', 'magisterio']

function hasPlan(userPlan: string | undefined, min: string): boolean {
  if (!userPlan) return false
  return PLAN_ORDER.indexOf(userPlan) >= PLAN_ORDER.indexOf(min)
}

const CONFIDENCE_COLOR: Record<string, string> = {
  Alta: 'text-green-400',
  Media: 'text-yellow-400',
  Baixa: 'text-orange-400',
  Nenhuma: 'text-red-400',
}

export default function ProfileHistory({
  userPlan,
  embedded = false,
}: {
  userPlan?: string
  embedded?: boolean
}) {
  const [items, setItems] = useState<HistoricoEntry[]>([])
  const [total, setTotal] = useState(0)
  const [totalAll, setTotalAll] = useState(0)
  const [historyScope, setHistoryScope] = useState<'recent' | 'complete'>('recent')
  const [historyLimit, setHistoryLimit] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')

  async function load(p: number) {
    setLoading(true)
    setError('')
    try {
      const data = await getHistorico(p, 20)
      setItems(data.items)
      setTotal(data.total)
      setTotalAll(data.total_all ?? data.total)
      setHistoryScope(data.history_scope ?? 'recent')
      setHistoryLimit(data.history_limit ?? null)
      setPage(p)
    } catch {
      setError('Erro ao carregar historico.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load(1)
  }, [])

  async function handleDelete(id: number) {
    try {
      await deleteHistoricoEntry(id)
      setItems((prev) => prev.filter((entry) => entry.id !== id))
      setTotal((current) => Math.max(0, current - 1))
    } catch {
      alert('Erro ao remover entrada.')
    }
  }

  function startDownload(url: string) {
    const link = document.createElement('a')
    link.href = url
    link.download = ''
    document.body.appendChild(link)
    link.click()
    window.setTimeout(() => link.remove(), 100)
  }

  function handleDownloadLaudo(id: number) {
    startDownload(`/download/laudo/${id}`)
  }

  function handleExportExcel() {
    setExporting(true)
    startDownload('/download/historico-excel')
    window.setTimeout(() => setExporting(false), 1200)
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <section
      id={embedded ? 'historico-verificacoes' : 'historico'}
      className={embedded
        ? 'pt-5'
        : 'mt-6 rounded-lg border border-fundo-borda bg-fundo-card p-5 sm:p-6'}
    >
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium uppercase tracking-[0.18em] text-texto-terciario">
            Historico
          </p>
          <h2 className="mt-1 font-eb-garamond text-xl text-texto">
            Verificacoes recentes
          </h2>
          <p className="mt-1 text-xs text-texto-terciario">
            {total} verificacao{total !== 1 ? 'es' : ''} exibida{total !== 1 ? 's' : ''}
          </p>
          {historyScope === 'recent' && historyLimit !== null && totalAll > historyLimit && (
            <p className="mt-1 text-xs text-dourado">
              Plano Fiel mostra as {historyLimit} mais recentes. O histórico completo fica no Catequista+.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {hasPlan(userPlan, 'apologeta') && (
            <button
              type="button"
              onClick={handleExportExcel}
              disabled={exporting || total === 0}
              className="inline-flex rounded-md border border-dourado/40 px-3 py-2 text-xs text-dourado transition-colors hover:bg-dourado hover:text-fundo disabled:opacity-50"
            >
              {exporting ? 'Exportando...' : 'Exportar Excel'}
            </button>
          )}
          <Link
            href="/verificador"
            className="inline-flex rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:border-dourado hover:text-dourado"
          >
            Nova verificacao
          </Link>
        </div>
      </div>

      {loading && (
        <p className="py-10 text-center text-sm text-texto-terciario">Carregando...</p>
      )}

      {error && (
        <p className="py-10 text-center text-sm text-vermelho">{error}</p>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="py-10 text-center text-sm text-texto-terciario">
          Nenhuma verificacao registrada ainda. Verifique uma citacao para comecar.
        </p>
      )}

      <div className="mt-4 flex flex-col gap-3">
        {items.map((entry) => (
          <HistoryEntryCard
            key={entry.id}
            entry={entry}
            canDownloadLaudo={hasPlan(userPlan, 'catequista')}
            onDelete={handleDelete}
            onDownloadLaudo={handleDownloadLaudo}
          />
        ))}
      </div>

      {totalPages > 1 && (
        <div className="mt-5 flex justify-center gap-2">
          <button
            type="button"
            onClick={() => load(page - 1)}
            disabled={page <= 1 || loading}
            className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:text-dourado disabled:opacity-40"
          >
            Anterior
          </button>
          <span className="flex items-center text-xs text-texto-terciario">{page} / {totalPages}</span>
          <button
            type="button"
            onClick={() => load(page + 1)}
            disabled={page >= totalPages || loading}
            className="rounded-md border border-fundo-borda px-3 py-2 text-xs text-texto-secundario transition-colors hover:text-dourado disabled:opacity-40"
          >
            Proxima
          </button>
        </div>
      )}
    </section>
  )
}

function HistoryEntryCard({
  entry,
  canDownloadLaudo,
  onDelete,
  onDownloadLaudo,
}: {
  entry: HistoricoEntry
  canDownloadLaudo: boolean
  onDelete: (id: number) => void
  onDownloadLaudo: (id: number) => void
}) {
  const confidenceKey = entry.confidence
    ?.normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')

  return (
    <article className="rounded-lg border border-fundo-borda bg-fundo p-4">
      <div className="mb-2 flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="mb-1 text-xs text-texto-terciario">
            {entry.attributed_to && (
              <span className="font-medium text-texto-secundario">
                {entry.attributed_to} -{' '}
              </span>
            )}
            {entry.created_at && new Date(entry.created_at).toLocaleDateString('pt-BR', {
              day: '2-digit',
              month: 'short',
              year: 'numeric',
            })}
          </p>
          <p className="line-clamp-2 text-sm italic text-texto">
            &quot;{entry.citation_text}&quot;
          </p>
        </div>
        <button
          type="button"
          onClick={() => onDelete(entry.id)}
          className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md text-texto-terciario transition-colors hover:bg-fundo-card hover:text-vermelho"
          title="Remover"
          aria-label="Remover verificacao do historico"
        >
          x
        </button>
      </div>

      {entry.label && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-fundo-borda bg-fundo-card px-2 py-0.5 text-xs text-texto-secundario">
            {entry.label}
          </span>
          {entry.confidence && (
            <span className={`text-xs font-medium ${CONFIDENCE_COLOR[confidenceKey ?? ''] ?? 'text-texto-terciario'}`}>
              {entry.confidence}
            </span>
          )}
          {entry.author && (
            <span className="truncate text-xs text-texto-terciario">{entry.author}</span>
          )}
        </div>
      )}

      {entry.reference && (
        <p className="mt-2 text-xs text-texto-terciario">
          {entry.reference.collection}
          {entry.reference.volume ? `, vol. ${entry.reference.volume}` : ''}
          {entry.reference.pdf_page ? `, p. ${entry.reference.pdf_page}` : ''}
          {entry.reference.edition_label ? ` - ${entry.reference.edition_label}` : ''}
        </p>
      )}

      {entry.variant_analysis && (
        <p className="mt-2 text-xs leading-relaxed text-texto-secundario">
          {entry.variant_analysis}
        </p>
      )}

      {canDownloadLaudo && (
        <button
          type="button"
          onClick={() => onDownloadLaudo(entry.id)}
          className="mt-3 rounded-md border border-dourado/40 px-3 py-2 text-xs text-dourado transition-colors hover:bg-dourado hover:text-fundo"
        >
          Baixar laudo PDF
        </button>
      )}
    </article>
  )
}
