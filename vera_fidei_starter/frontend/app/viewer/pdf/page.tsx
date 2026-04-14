'use client'

import { Suspense, useEffect, useRef, useState, useMemo } from 'react'
import { useSearchParams } from 'next/navigation'

// ─── Tipos ──────────────────────────────────────────────────────────────────

type PdfTextItem = {
  str: string
  transform: number[]
  width: number
  height: number
}

type HighlightBox = {
  left: number
  top: number
  width: number
  height: number
}

// ─── Utilitários de texto ────────────────────────────────────────────────────

function normalizeText(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
}

function buildJoinedText(items: PdfTextItem[]) {
  const parts: Array<{
    normalized: string
    start: number
    end: number
    item: PdfTextItem
  }> = []
  let cursor = 0
  for (const item of items) {
    const normalized = normalizeText(item.str || '')
    const start = cursor
    const end = start + normalized.length
    parts.push({ normalized, start, end, item })
    cursor = end + 1
  }
  const fullNormalized = parts.map((p) => p.normalized).join(' ')
  return { parts, fullNormalized }
}

function findQuoteRange(fullNormalized: string, quote: string) {
  const nq = normalizeText(quote)
  if (!nq) return null
  const idx = fullNormalized.indexOf(nq)
  if (idx !== -1) return { start: idx, end: idx + nq.length }
  // fallback: primeiras 10 palavras
  const words = nq.split(' ').filter(Boolean)
  if (words.length >= 4) {
    const reduced = words.slice(0, Math.min(words.length, 10)).join(' ')
    const ridx = fullNormalized.indexOf(reduced)
    if (ridx !== -1) return { start: ridx, end: ridx + reduced.length }
  }
  return null
}

// ─── getItemBox corrigido ────────────────────────────────────────────────────
// Após Util.transform(viewport.transform, item.transform):
//   tx[4] = x do origin do texto (canvas pixels)
//   tx[5] = y da baseline (canvas pixels, eixo Y vai para baixo)
//   tx[0] e tx[3] = escala aplicada — |tx[3]| é a altura da fonte em canvas px

function getItemBox(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  viewport: any,
  item: PdfTextItem,
): HighlightBox {
  const tx: number[] = pdfjsLib.Util.transform(viewport.transform, item.transform)
  const fontHeight = Math.abs(tx[3])
  const left = tx[4]
  const top = tx[5] - fontHeight
  const width = Math.abs(item.width * tx[0] / item.transform[0]) || item.width * viewport.scale
  const height = fontHeight
  return { left, top, width, height }
}

function computeHighlightBoxes(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib: any,
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  viewport: any,
  items: PdfTextItem[],
  quote: string,
): HighlightBox[] {
  const { parts, fullNormalized } = buildJoinedText(items)
  const range = findQuoteRange(fullNormalized, quote)
  if (!range) return []
  return parts
    .filter((p) => p.normalized && !(p.end < range.start || p.start > range.end))
    .map((p) => getItemBox(pdfjsLib, viewport, p.item))
}

// ─── Viewer interno (usa searchParams) ──────────────────────────────────────

function PdfViewerInner() {
  const searchParams = useSearchParams()
  const fileUrl = searchParams.get('file') || ''
  const quote = searchParams.get('quote') || ''
  const page = useMemo(() => Math.max(1, Number(searchParams.get('page') || '1')), [searchParams])

  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [found, setFound] = useState<boolean | null>(null)

  useEffect(() => {
    let cancelled = false

    async function run() {
      setLoading(true)
      setError(null)
      setFound(null)

      try {
        if (!fileUrl) throw new Error('URL do PDF não informada.')

        // Dynamic import evita processamento pelo webpack
        const pdfjsLib = await import('pdfjs-dist')
        pdfjsLib.GlobalWorkerOptions.workerSrc =
          `//cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjsLib.version}/pdf.worker.min.js`

        const pdf = await pdfjsLib.getDocument(fileUrl).promise
        const pdfPage = await pdf.getPage(page)

        if (cancelled) return

        const scale = 1.6
        const viewport = pdfPage.getViewport({ scale })

        const canvas = canvasRef.current
        const overlay = overlayRef.current
        const scrollContainer = scrollRef.current
        if (!canvas || !overlay || !scrollContainer) return

        const ctx = canvas.getContext('2d')
        if (!ctx) throw new Error('Canvas não suportado.')

        canvas.width = viewport.width
        canvas.height = viewport.height
        canvas.style.width = `${viewport.width}px`
        canvas.style.height = `${viewport.height}px`
        overlay.style.width = `${viewport.width}px`
        overlay.style.height = `${viewport.height}px`
        overlay.innerHTML = ''

        await pdfPage.render({ canvasContext: ctx, viewport }).promise

        if (cancelled) return

        const textContent = await pdfPage.getTextContent()
        const items = (textContent.items as PdfTextItem[]).filter((i) => i.str)

        const boxes = quote
          ? computeHighlightBoxes(pdfjsLib, viewport, items, quote)
          : []

        setFound(boxes.length > 0)

        boxes.forEach((box, i) => {
          // fundo amarelo suave
          const bg = document.createElement('div')
          Object.assign(bg.style, {
            position: 'absolute',
            left: `${box.left}px`,
            top: `${box.top}px`,
            width: `${box.width}px`,
            height: `${box.height}px`,
            background: 'rgba(255, 220, 0, 0.20)',
            borderRadius: '2px',
            pointerEvents: 'none',
          })
          overlay.appendChild(bg)

          // sublinhado dourado
          const line = document.createElement('div')
          Object.assign(line.style, {
            position: 'absolute',
            left: `${box.left}px`,
            top: `${box.top + box.height + 1}px`,
            width: `${box.width}px`,
            height: '2.5px',
            background: '#f5c518',
            borderRadius: '999px',
            pointerEvents: 'none',
          })
          overlay.appendChild(line)

          if (i === 0) {
            setTimeout(() => {
              scrollContainer.scrollTo({
                top: Math.max(box.top - 160, 0),
                behavior: 'smooth',
              })
            }, 150)
          }
        })

        setLoading(false)
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Erro ao abrir o PDF.')
          setLoading(false)
        }
      }
    }

    run()
    return () => { cancelled = true }
  }, [fileUrl, quote, page])

  return (
    <div className="min-h-screen bg-zinc-950 text-white">
      {/* Header */}
      <div className="sticky top-0 z-20 border-b border-zinc-800 bg-zinc-950/95 px-4 py-3 space-y-0.5">
        <p className="text-sm text-zinc-300">
          Página <span className="font-semibold text-white">{page}</span>
        </p>
        {quote && (
          <p className="text-xs text-zinc-500 truncate max-w-xl">
            Procurando:{' '}
            <span className="text-zinc-400 italic">&ldquo;{quote.slice(0, 100)}{quote.length > 100 ? '…' : ''}&rdquo;</span>
          </p>
        )}
        {found === false && !loading && (
          <p className="text-xs text-amber-500">
            Citação não localizada na camada de texto — PDF pode ser imagem.
          </p>
        )}
        {found === true && !loading && (
          <p className="text-xs text-green-400">
            Citação destacada na página.
          </p>
        )}
      </div>

      {loading && (
        <div className="flex items-center gap-2 px-6 py-4 text-sm text-zinc-400">
          <span className="inline-block w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          Abrindo trecho no PDF...
        </div>
      )}

      {error && (
        <div className="px-6 py-4 text-sm text-red-400">{error}</div>
      )}

      {/* Scroll container */}
      <div
        ref={scrollRef}
        className="relative overflow-auto"
        style={{ height: 'calc(100vh - 70px)' }}
      >
        <div className="relative mx-auto w-fit px-4 py-6">
          <canvas ref={canvasRef} className="block rounded shadow-2xl" />
          <div ref={overlayRef} className="pointer-events-none absolute left-4 top-6" />
        </div>
      </div>
    </div>
  )
}

// ─── Página exportada com Suspense (obrigatório para useSearchParams) ────────

export default function PdfViewerPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-zinc-400 text-sm">
          Carregando visualizador...
        </div>
      }
    >
      <PdfViewerInner />
    </Suspense>
  )
}
