'use client'

import { Suspense, useEffect, useRef, useState, useMemo, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'

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
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/\s+/g, ' ').trim().toLowerCase()
}

function buildJoinedText(items: PdfTextItem[]) {
  const parts: Array<{ normalized: string; start: number; end: number; item: PdfTextItem }> = []
  let cursor = 0
  for (const item of items) {
    const normalized = normalizeText(item.str || '')
    parts.push({ normalized, start: cursor, end: cursor + normalized.length, item })
    cursor += normalized.length + 1
  }
  return { parts, fullNormalized: parts.map((p) => p.normalized).join(' ') }
}

function findQuoteRange(fullNormalized: string, quote: string) {
  const nq = normalizeText(quote)
  if (!nq) return null
  const idx = fullNormalized.indexOf(nq)
  if (idx !== -1) return { start: idx, end: idx + nq.length }
  const words = nq.split(' ').filter(Boolean)
  if (words.length >= 4) {
    const reduced = words.slice(0, Math.min(words.length, 10)).join(' ')
    const ridx = fullNormalized.indexOf(reduced)
    if (ridx !== -1) return { start: ridx, end: ridx + reduced.length }
  }
  return null
}

function getItemBox(
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib: any, viewport: any, item: PdfTextItem,
): HighlightBox {
  const tx: number[] = pdfjsLib.Util.transform(viewport.transform, item.transform)
  const fontHeight = Math.abs(tx[3])
  return {
    left: tx[4],
    top: tx[5] - fontHeight,
    width: Math.abs(item.width * tx[0] / item.transform[0]) || item.width * viewport.scale,
    height: fontHeight,
  }
}

// ─── Componente de uma página ────────────────────────────────────────────────

function PdfPageCanvas({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib, pdfDoc, pageNum, scale, quote, onVisible,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib: any; pdfDoc: any; pageNum: number; scale: number;
  quote: string; onVisible?: (n: number) => void
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [rendered, setRendered] = useState(false)

  // IntersectionObserver: render somente quando a página está próxima do viewport
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setRendered(true) },
      { rootMargin: '400px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Visibilidade da página para atualizar o número no header
  useEffect(() => {
    const el = wrapRef.current
    if (!el || !onVisible) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) onVisible(pageNum) },
      { threshold: 0.3 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [pageNum, onVisible])

  useEffect(() => {
    if (!rendered || !pdfDoc) return
    let cancelled = false

    async function renderPage() {
      const page = await pdfDoc.getPage(pageNum)
      if (cancelled) return
      const viewport = page.getViewport({ scale })
      const canvas = canvasRef.current
      const overlay = overlayRef.current
      if (!canvas || !overlay) return
      canvas.width = viewport.width
      canvas.height = viewport.height
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`
      overlay.style.width = `${viewport.width}px`
      overlay.style.height = `${viewport.height}px`
      overlay.innerHTML = ''

      await page.render({ canvas, viewport }).promise
      if (cancelled) return

      if (quote) {
        const textContent = await page.getTextContent()
        const items = (textContent.items as PdfTextItem[]).filter((i) => i.str)
        const { parts, fullNormalized } = buildJoinedText(items)
        const range = findQuoteRange(fullNormalized, quote)
        if (range) {
          parts
            .filter((p) => p.normalized && !(p.end < range.start || p.start > range.end))
            .forEach((p, i) => {
              const box = getItemBox(pdfjsLib, viewport, p.item)
              const bg = document.createElement('div')
              Object.assign(bg.style, {
                position: 'absolute', left: `${box.left}px`, top: `${box.top}px`,
                width: `${box.width}px`, height: `${box.height}px`,
                background: 'rgba(255,220,0,0.22)', borderRadius: '2px', pointerEvents: 'none',
              })
              overlay.appendChild(bg)
              if (i === 0) {
                const line = document.createElement('div')
                Object.assign(line.style, {
                  position: 'absolute', left: `${box.left}px`, top: `${box.top + box.height + 1}px`,
                  width: `${box.width}px`, height: '2.5px', background: '#f5c518',
                  borderRadius: '999px', pointerEvents: 'none',
                })
                overlay.appendChild(line)
              }
            })
        }
      }
    }

    renderPage().catch(() => {})
    return () => { cancelled = true }
  }, [rendered, pdfDoc, pageNum, scale, quote, pdfjsLib])

  return (
    <div ref={wrapRef} className="relative mx-auto w-fit px-2 py-3">
      <canvas ref={canvasRef} className="block rounded shadow-xl" />
      <div ref={overlayRef} className="pointer-events-none absolute left-2 top-3" />
      {!rendered && (
        <div className="flex items-center justify-center rounded bg-zinc-900" style={{ width: 600, height: 800 }}>
          <span className="text-sm text-zinc-600">Página {pageNum}</span>
        </div>
      )}
    </div>
  )
}

// ─── Viewer principal ────────────────────────────────────────────────────────

function PdfViewerInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const fileUrl = searchParams.get('file') || ''
  const quote = searchParams.get('quote') || ''
  const initialPage = useMemo(() => Math.max(1, Number(searchParams.get('page') || '1')), [searchParams])

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [pdfjsLib, setPdfjsLib] = useState<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [pdfDoc, setPdfDoc] = useState<any>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(initialPage)
  const [scale, setScale] = useState(1.5)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const scrollRef = useRef<HTMLDivElement>(null)
  const pageRefs = useRef<(HTMLDivElement | null)[]>([])

  useEffect(() => {
    if (!fileUrl) { setError('URL do PDF não informada.'); setLoading(false); return }
    let cancelled = false
    async function load() {
      const lib = await import('pdfjs-dist')
      // Local worker — no CDN dependency, works on mobile without internet relay
      lib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'
      const doc = await lib.getDocument(fileUrl).promise
      if (cancelled) return
      setPdfjsLib(lib)
      setPdfDoc(doc)
      setNumPages(doc.numPages)
      setLoading(false)
    }
    load().catch((e) => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [fileUrl])

  // Scroll to initial page once pages are known
  useEffect(() => {
    if (!pdfDoc || initialPage <= 1) return
    setTimeout(() => {
      pageRefs.current[initialPage - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 300)
  }, [pdfDoc, initialPage])

  const goToPage = useCallback((n: number) => {
    const target = Math.min(Math.max(1, n), numPages)
    pageRefs.current[target - 1]?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    setCurrentPage(target)
  }, [numPages])

  const handleVisible = useCallback((n: number) => setCurrentPage(n), [])

  return (
    <div className="flex flex-col h-[100dvh] bg-zinc-950 text-white">
      {/* Header fixo */}
      <div className="shrink-0 sticky top-0 z-20 flex items-center gap-2 border-b border-zinc-800 bg-zinc-950/95 px-3 py-2">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 rounded px-2 py-1.5 text-sm text-zinc-400 hover:bg-zinc-800 active:scale-95 transition-all"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
          </svg>
          Voltar
        </button>

        <div className="flex items-center gap-1 ml-auto">
          {/* Controles de zoom */}
          <button
            onClick={() => setScale((s) => Math.max(0.8, s - 0.2))}
            className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 text-lg font-light"
            title="Diminuir zoom"
          >−</button>
          <span className="text-xs text-zinc-500 w-10 text-center">{Math.round(scale * 100)}%</span>
          <button
            onClick={() => setScale((s) => Math.min(3.0, s + 0.2))}
            className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 text-lg font-light"
            title="Aumentar zoom"
          >+</button>
        </div>

        {/* Navegação de páginas */}
        {numPages > 0 && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => goToPage(currentPage - 1)}
              disabled={currentPage <= 1}
              className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 disabled:opacity-30"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
              </svg>
            </button>
            <span className="text-xs text-zinc-400 whitespace-nowrap">
              {currentPage} / {numPages}
            </span>
            <button
              onClick={() => goToPage(currentPage + 1)}
              disabled={currentPage >= numPages}
              className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 disabled:opacity-30"
            >
              <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
                <path fillRule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06L9.28 14.78a.75.75 0 0 1-1.06-1.06L12.44 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
              </svg>
            </button>
          </div>
        )}
      </div>

      {/* Estado de loading/erro */}
      {loading && (
        <div className="flex items-center gap-2 px-4 py-3 text-sm text-zinc-400">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          Carregando PDF...
        </div>
      )}
      {error && <div className="px-4 py-3 text-sm text-red-400">{error}</div>}

      {/* Scroll container com suporte touch */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-auto"
        style={{ touchAction: 'pan-x pan-y pinch-zoom', WebkitOverflowScrolling: 'touch' } as React.CSSProperties}
      >
        {pdfDoc && Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
          <div
            key={pageNum}
            ref={(el) => { pageRefs.current[pageNum - 1] = el }}
          >
            <PdfPageCanvas
              pdfjsLib={pdfjsLib}
              pdfDoc={pdfDoc}
              pageNum={pageNum}
              scale={scale}
              quote={quote}
              onVisible={handleVisible}
            />
          </div>
        ))}

        {pdfDoc && numPages === 0 && !loading && (
          <p className="px-4 py-6 text-sm text-zinc-500">Nenhuma página encontrada.</p>
        )}
      </div>
    </div>
  )
}

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
