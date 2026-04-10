import type { StatusCode } from '@/lib/types'

const config: Record<
  StatusCode,
  { bg: string; text: string; label: string }
> = {
  CONFIRMADA_EXATA: {
    bg: 'bg-green-900/40',
    text: 'text-green-300',
    label: 'Confirmada',
  },
  CONFIRMADA_TRADUCAO: {
    bg: 'bg-blue-900/40',
    text: 'text-blue-300',
    label: 'Confirmada (tradução)',
  },
  ATRIBUICAO_DUVIDOSA: {
    bg: 'bg-amber-900/40',
    text: 'text-amber-300',
    label: 'Atribuição duvidosa',
  },
  PARAFRASE_PLAUSIVEL: {
    bg: 'bg-orange-900/40',
    text: 'text-orange-300',
    label: 'Paráfrase plausível',
  },
  NAO_ENCONTRADA: {
    bg: 'bg-red-900/40',
    text: 'text-red-300',
    label: 'Não encontrada',
  },
}

export default function StatusBadge({
  code,
  confidence,
}: {
  code: StatusCode
  confidence: string
}) {
  const { bg, text, label } = config[code]
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <span
        className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${bg} ${text}`}
      >
        {label}
      </span>
      <span className="text-sm text-texto-secundario">
        Confiança:{' '}
        <span className="text-texto font-medium">{confidence}</span>
      </span>
    </div>
  )
}
