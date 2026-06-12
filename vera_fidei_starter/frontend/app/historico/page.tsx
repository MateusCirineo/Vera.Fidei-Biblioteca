'use client'

import { useEffect, useState } from 'react'
import { getHistorico, deleteHistoricoEntry } from '@/lib/auth'

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
  created_at: string | null
}

const CONFIDENCE_COLOR: Record<string, string> = {
  Alta: 'text-green-400',
  Média: 'text-yellow-400',
  Baixa: 'text-orange-400',
  Nenhuma: 'text-red-400',
}

export default function HistoricoPage() {
  const [items, setItems] = useState<HistoricoEntry[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  async function load(p: number) {
    setLoading(true)
    setError('')
    try {
      const data = await getHistorico(p, 20)
      setItems(data.items)
      setTotal(data.total)
      setPage(p)
    } catch {
      setError('Erro ao carregar histórico. Verifique se está logado.')
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
      setItems((prev) => prev.filter((e) => e.id !== id))
      setTotal((t) => t - 1)
    } catch {
      alert('Erro ao remover entrada.')
    }
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="font-eb-garamond text-2xl text-dourado mb-1">Meu Histórico</h1>
      <p className="text-xs text-texto-terciario mb-6">{total} verificação{total !== 1 ? 'ões' : ''} registrada{total !== 1 ? 's' : ''}</p>

      {loading && (
        <p className="text-sm text-texto-terciario text-center py-12">Carregando…</p>
      )}

      {error && (
        <p className="text-sm text-vermelho text-center py-12">{error}</p>
      )}

      {!loading && !error && items.length === 0 && (
        <p className="text-sm text-texto-terciario text-center py-12">
          Nenhuma verificação registrada ainda. Verifique uma citação para começar.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {items.map((entry) => (
          <div
            key={entry.id}
            className="bg-fundo-card border border-fundo-borda rounded-lg p-4"
          >
            <div className="flex items-start justify-between gap-2 mb-2">
              <div className="flex-1 min-w-0">
                <p className="text-xs text-texto-terciario mb-1">
                  {entry.attributed_to && <span className="font-medium text-texto-secundario">{entry.attributed_to} · </span>}
                  {entry.created_at && new Date(entry.created_at).toLocaleDateString('pt-BR', {
                    day: '2-digit', month: 'short', year: 'numeric',
                  })}
                </p>
                <p className="text-sm text-texto line-clamp-2 italic">"{entry.citation_text}"</p>
              </div>
              <button
                onClick={() => handleDelete(entry.id)}
                className="text-texto-terciario hover:text-vermelho transition-colors flex-shrink-0 text-xs mt-0.5"
                title="Remover"
              >
                ✕
              </button>
            </div>

            {entry.label && (
              <div className="flex items-center gap-2 mt-2">
                <span className="text-xs bg-fundo px-2 py-0.5 rounded-full border border-fundo-borda text-texto-secundario">
                  {entry.label}
                </span>
                {entry.confidence && (
                  <span className={`text-xs font-medium ${CONFIDENCE_COLOR[entry.confidence] ?? 'text-texto-terciario'}`}>
                    {entry.confidence}
                  </span>
                )}
                {entry.author && (
                  <span className="text-xs text-texto-terciario truncate">{entry.author}</span>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex justify-center gap-2 mt-6">
          <button
            onClick={() => load(page - 1)}
            disabled={page <= 1 || loading}
            className="text-xs px-3 py-1.5 rounded border border-fundo-borda text-texto-secundario disabled:opacity-40 hover:text-dourado transition-colors"
          >
            ← Anterior
          </button>
          <span className="text-xs text-texto-terciario flex items-center">{page} / {totalPages}</span>
          <button
            onClick={() => load(page + 1)}
            disabled={page >= totalPages || loading}
            className="text-xs px-3 py-1.5 rounded border border-fundo-borda text-texto-secundario disabled:opacity-40 hover:text-dourado transition-colors"
          >
            Próxima →
          </button>
        </div>
      )}
    </div>
  )
}
