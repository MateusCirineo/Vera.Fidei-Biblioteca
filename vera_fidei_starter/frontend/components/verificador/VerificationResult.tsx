import type { VerifyCitationResponse } from '@/lib/types'
import { formatLanguage } from '@/lib/language'
import StatusBadge from './StatusBadge'
import MatchReferenceCard from './MatchReferenceCard'

export default function VerificationResult({
  result,
  originalQuery,
}: {
  result: VerifyCitationResponse
  originalQuery?: string
}) {
  const sourceLabel =
    result.reference?.source_label ||
    result.reference?.edition_label ||
    result.source_version ||
    'Acervo indexado do Vera.Fidei'
  const evidenceCount = [
    result.reference,
    result.matched_excerpt,
    result.matched_translation,
  ].filter(Boolean).length

  return (
    <div className="space-y-5">
      {/* Status */}
      <StatusBadge code={result.status_code} confidence={result.confidence} />

      <section className="rounded-lg border border-dourado/20 bg-dourado/5 px-4 py-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-dourado">
          Base da decisão
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-3">
          <div className="border-l border-fundo-borda pl-3">
            <p className="text-xs text-texto-terciario">Confiança</p>
            <p className="mt-0.5 text-sm font-medium text-texto">{result.confidence}</p>
          </div>
          <div className="border-l border-fundo-borda pl-3">
            <p className="text-xs text-texto-terciario">Fonte</p>
            <p className="mt-0.5 truncate text-sm font-medium text-texto">{sourceLabel}</p>
          </div>
          <div className="border-l border-fundo-borda pl-3">
            <p className="text-xs text-texto-terciario">Evidências</p>
            <p className="mt-0.5 text-sm font-medium text-texto">{evidenceCount}</p>
          </div>
        </div>
      </section>

      {/* Quando não encontrada: mostrar só o status + análise, sem conteúdo aleatório */}
      {result.status_code !== 'NAO_ENCONTRADA' && (
        <>
          {/* Author / Work */}
          {(result.author || result.work) && (
            <div>
              {result.author && (
                <p className="font-garamond text-lg text-texto">{result.author}</p>
              )}
              {result.work && (
                <p className="text-sm italic text-texto-secundario">{result.work}</p>
              )}
            </div>
          )}

          {/* Reference card */}
          {result.reference && (
            <div className="space-y-2">
              {result.reference.is_primary_source ? (
                <MatchReferenceCard
                  reference={result.reference}
                  quote={originalQuery ?? undefined}
                  fallbackQuote={result.matched_excerpt ?? undefined}
                />
              ) : (
                <>
                  <MatchReferenceCard
                    reference={result.reference}
                    quote={originalQuery ?? undefined}
                    fallbackQuote={result.matched_excerpt ?? undefined}
                  />
                  <p className="text-xs text-texto-terciario pl-1">
                    Fonte primária não disponível no acervo atual.
                  </p>
                </>
              )}
            </div>
          )}
        </>
      )}

      {/* Texto original + tradução — apenas para resultados confirmados */}
      {result.status_code !== 'NAO_ENCONTRADA' && result.matched_excerpt && (
        <div className="space-y-3">
          {/* Indicador de fidelidade */}
          {result.translation_fidelity && result.translation_fidelity !== 'nao_encontrada' && (
            <div className={`inline-flex items-center gap-1.5 text-xs font-semibold px-2 py-1 rounded-full ${
              result.translation_fidelity === 'fiel'
                ? 'bg-green-900/40 text-green-400'
                : 'bg-amber-900/40 text-amber-400'
            }`}>
              {result.translation_fidelity === 'fiel' ? 'Tradução fiel' : 'Tradução imprecisa'}
            </div>
          )}

          {/* Bloco original latim */}
          <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4 space-y-2">
            <p className="text-xs font-semibold uppercase tracking-wider text-texto-terciario">
              Texto original ({formatLanguage(result.original_language) || 'latim'})
            </p>
            {result.context_before && (
              <p className="text-xs text-texto-terciario leading-relaxed line-clamp-2">
                {result.context_before}
              </p>
            )}
            <blockquote className="border-l-2 border-dourado pl-3 text-sm text-texto leading-relaxed italic">
              {result.matched_excerpt}
            </blockquote>
            {result.context_after && (
              <p className="text-xs text-texto-terciario leading-relaxed line-clamp-2">
                {result.context_after}
              </p>
            )}
          </div>

          {/* Bloco tradução PT */}
          {result.matched_translation && (
            <div className="rounded-lg border border-fundo-borda bg-fundo-card p-4 space-y-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-texto-terciario">
                Tradução de referência ({formatLanguage(result.translation_language) || 'português'})
                {(result.translator ?? result.translation_edition) && (
                  <span className="normal-case font-normal ml-1">
                    — {result.translator ?? result.translation_edition}
                  </span>
                )}
              </p>
              <blockquote className="border-l-2 border-dourado/50 pl-3 text-sm text-texto-secundario leading-relaxed">
                {result.matched_translation}
              </blockquote>
            </div>
          )}
        </div>
      )}

      {/* Explanation */}
      {result.explanation && (
        <div className="rounded-lg bg-fundo-card border border-fundo-borda p-4">
          <p className="text-xs font-semibold uppercase tracking-wider text-texto-terciario mb-1">
            Análise
          </p>
          <p className="text-sm text-texto-secundario leading-relaxed">
            {result.explanation}
          </p>
        </div>
      )}
    </div>
  )
}
