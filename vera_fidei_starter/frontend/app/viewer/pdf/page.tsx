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
  return text
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
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
  for (const size of [12, 10, 8, 6, 5]) {
    if (size > words.length) continue
    for (let i = 0; i <= words.length - size; i++) {
      const win = words.slice(i, i + size).join(' ')
      const widx = fullNormalized.indexOf(win)
      if (widx !== -1) return { start: widx, end: widx + win.length }
    }
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

// ─── Página individual (mobile e desktop compartilham) ────────────────────────

function PdfPageCanvas({
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib, pdfDoc, pageNum, scale, quote, fallbackQuote, onVisible, placeholderHeight,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib: any; pdfDoc: any; pageNum: number; scale: number;
  quote: string; fallbackQuote: string;
  onVisible?: (n: number) => void;
  placeholderHeight: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [rendered, setRendered] = useState(false)

  // Aciona render quando a página se aproxima do viewport
  useEffect(() => {
    const el = wrapRef.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setRendered(true) },
      { rootMargin: '600px' },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  // Atualiza o número da página visível no header
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

  // Renderiza o canvas quando a página está próxima
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

      // Pixel ratio para nitidez em telas retina/2x
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      canvas.width = viewport.width * dpr
      canvas.height = viewport.height * dpr
      canvas.style.width = `${viewport.width}px`
      canvas.style.height = `${viewport.height}px`
      overlay.style.width = `${viewport.width}px`
      overlay.style.height = `${viewport.height}px`
      overlay.innerHTML = ''

      const ctx = canvas.getContext('2d')!
      ctx.scale(dpr, dpr)
      await page.render({ canvasContext: ctx, viewport }).promise
      if (cancelled) return

      const activeQuote = quote || fallbackQuote
      if (activeQuote) {
        const textContent = await page.getTextContent()
        const items = (textContent.items as PdfTextItem[]).filter((i) => i.str)
        const { parts, fullNormalized } = buildJoinedText(items)
        let range = quote ? findQuoteRange(fullNormalized, quote) : null
        if (!range && fallbackQuote) range = findQuoteRange(fullNormalized, fallbackQuote)
        if (range) {
          parts
            .filter((p) => p.normalized && !(p.end < range!.start || p.start > range!.end))
            .forEach((p) => {
              const box = getItemBox(pdfjsLib, viewport, p.item)
              const bg = document.createElement('div')
              Object.assign(bg.style, {
                position: 'absolute', left: `${box.left}px`, top: `${box.top}px`,
                width: `${box.width}px`, height: `${box.height}px`,
                background: 'rgba(255,220,0,0.28)', borderRadius: '2px', pointerEvents: 'none',
              })
              overlay.appendChild(bg)
              const line = document.createElement('div')
              Object.assign(line.style, {
                position: 'absolute', left: `${box.left}px`, top: `${box.top + box.height + 1}px`,
                width: `${box.width}px`, height: '2.5px', background: '#f5c518',
                borderRadius: '999px', pointerEvents: 'none',
              })
              overlay.appendChild(line)
            })
        }
      }
    }

    renderPage().catch(() => {})
    return () => { cancelled = true }
  }, [rendered, pdfDoc, pdfjsLib, pageNum, scale, quote, fallbackQuote])

  return (
    <div ref={wrapRef} className="relative w-full">
      {rendered ? (
        <>
          <canvas ref={canvasRef} className="block w-full" style={{ imageRendering: 'auto' }} />
          <div ref={overlayRef} className="pointer-events-none absolute left-0 top-0" />
        </>
      ) : (
        // Placeholder com altura estimada para manter scroll correto
        <div className="w-full bg-zinc-900" style={{ height: placeholderHeight }} />
      )}
    </div>
  )
}

// ─── Viewer principal (mobile e desktop) ─────────────────────────────────────

function PdfViewerInner() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const fileUrl = searchParams.get('file') || ''
  const quote = searchParams.get('quote') || ''
  const fallbackQuote = searchParams.get('fallbackQuote') || ''
  const initialPage = useMemo(() => Math.max(1, Number(searchParams.get('page') || '1')), [searchParams])

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [pdfjsLib, setPdfjsLib] = useState<any>(null)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [pdfDoc, setPdfDoc] = useState<any>(null)
  const [numPages, setNumPages] = useState(0)
  const [currentPage, setCurrentPage] = useState(initialPage)
  const [scale, setScale] = useState(1.5)
  const [placeholderH, setPlaceholderH] = useState(800)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [isMobile, setIsMobile] = useState<boolean | null>(null)

  const pageRefs = useRef<(HTMLDivElement | null)[]>([])

  // Detecta mobile uma vez no cliente
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  // Carrega o PDF e calcula a escala baseada na tela
  useEffect(() => {
    if (!fileUrl || isMobile === null) return
    let cancelled = false
    async function load() {
      const lib = await import('pdfjs-dist')
      lib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'
      const doc = await lib.getDocument(fileUrl).promise
      if (cancelled) return

      // Calcula escala automática pela largura da tela (mobile) ou fixa (desktop)
      if (isMobile) {
        const firstPage = await doc.getPage(1)
        const baseVp = firstPage.getViewport({ scale: 1 })
        const autoScale = window.innerWidth / baseVp.width
        setScale(autoScale)
        setPlaceholderH(Math.round(baseVp.height * autoScale))
      }

      setPdfjsLib(lib)
      setPdfDoc(doc)
      setNumPages(doc.numPages)
      setLoading(false)
    }
    load().catch((e) => { if (!cancelled) { setError(e.message); setLoading(false) } })
    return () => { cancelled = true }
  }, [fileUrl, isMobile])

  // Scroll para a página inicial após o PDF carregar
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

  if (isMobile === null) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
      </div>
    )
  }

  return (
    <div className="flex flex-col bg-zinc-950 text-white" style={{ height: '100dvh' }}>

      {/* ── Header ── */}
      <div className="shrink-0 sticky top-0 z-20 flex items-center gap-2 border-b border-zinc-800 bg-zinc-950/95 px-3 py-2 backdrop-blur-sm">
        <button
          onClick={() => router.back()}
          className="flex items-center gap-1 rounded px-2 py-1.5 text-sm text-zinc-400 hover:bg-zinc-800 active:scale-95 transition-all"
        >
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4">
            <path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" />
          </svg>
          Voltar
        </button>

        <span className="text-xs text-zinc-500 ml-1">Visualizador de PDF</span>

        {/* Zoom (só desktop) */}
        {!isMobile && (
          <div className="flex items-center gap-1 ml-auto">
            <button onClick={() => setScale((s) => Math.max(0.8, s - 0.2))} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 text-lg font-light">−</button>
            <span className="text-xs text-zinc-500 w-10 text-center">{Math.round(scale * 100)}%</span>
            <button onClick={() => setScale((s) => Math.min(3.0, s + 0.2))} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 text-lg font-light">+</button>
          </div>
        )}

        {/* Contador de página */}
        {numPages > 0 && (
          <div className="flex items-center gap-1 ml-auto">
            {!isMobile && (
              <button onClick={() => goToPage(currentPage - 1)} disabled={currentPage <= 1} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 disabled:opacity-30">
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" /></svg>
              </button>
            )}
            <span className="text-xs text-zinc-400 whitespace-nowrap tabular-nums">{currentPage} / {numPages}</span>
            {!isMobile && (
              <button onClick={() => goToPage(currentPage + 1)} disabled={currentPage >= numPages} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 disabled:opacity-30">
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06L9.28 14.78a.75.75 0 0 1-1.06-1.06L12.44 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" /></svg>
              </button>
            )}
          </div>
        )}
      </div>

      {/* ── Banner de citação ── */}
      {(quote || fallbackQuote) && (
        <div className="shrink-0 flex items-start gap-2 bg-amber-950/40 border-b border-amber-900/40 px-3 py-2">
          <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4 text-amber-400 shrink-0 mt-0.5">
            <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 1 0 0 11 5.5 5.5 0 0 0 0-11ZM2 9a7 7 0 1 1 12.452 4.391l3.328 3.329a.75.75 0 1 1-1.06 1.06l-3.329-3.328A7 7 0 0 1 2 9Z" clipRule="evenodd" />
          </svg>
          <p className="text-xs text-amber-300/80 leading-relaxed">
            Trecho destacado em amarelo: <span className="italic">&ldquo;{(quote || fallbackQuote).slice(0, 80)}{(quote || fallbackQuote).length > 80 ? '…' : ''}&rdquo;</span>
          </p>
        </div>
      )}

      {/* ── Estados de loading/erro ── */}
      {loading && (
        <div className="flex items-center gap-2 px-4 py-3 text-sm text-zinc-400">
          <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
          Carregando PDF…
        </div>
      )}
      {error && <div className="px-4 py-3 text-sm text-red-400">{error}</div>}

      {/* ── Scroll contínuo de páginas ── */}
      <div
        className="flex-1 overflow-auto"
        style={{
          touchAction: 'pan-x pan-y pinch-zoom',
          WebkitOverflowScrolling: 'touch',
          overscrollBehavior: 'contain',
        } as React.CSSProperties}
      >
        {pdfDoc && Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
          <div
            key={pageNum}
            ref={(el) => { pageRefs.current[pageNum - 1] = el }}
            className={isMobile ? '' : 'px-2 py-3'}
          >
            <PdfPageCanvas
              pdfjsLib={pdfjsLib}
              pdfDoc={pdfDoc}
              pageNum={pageNum}
              scale={scale}
              quote={quote}
              fallbackQuote={fallbackQuote}
              onVisible={handleVisible}
              placeholderHeight={placeholderH}
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
