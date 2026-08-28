'use client'

import { Suspense, type FormEvent, useEffect, useRef, useState, useMemo, useCallback } from 'react'
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

type SearchResult = {
  page: number
  occurrence: number
  top: number
  preview: string
}

type PageMetric = {
  width: number
  height: number
}

const PDF_SEARCH_TIMEOUT_MS = 120_000
const PDF_PAGE_RENDER_TIMEOUT_MS = 45_000

// ─── Utilitários de texto ────────────────────────────────────────────────────

function normalizeText(text: string): string {
  return text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
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

function findExactRanges(fullNormalized: string, query: string) {
  const nq = normalizeText(query)
  if (!nq) return []
  const ranges: Array<{ start: number; end: number }> = []
  let idx = fullNormalized.indexOf(nq)
  while (idx !== -1) {
    ranges.push({ start: idx, end: idx + nq.length })
    idx = fullNormalized.indexOf(nq, idx + Math.max(1, nq.length))
  }
  return ranges
}

function buildSearchPreview(rawText: string, term: string, occurrence: number) {
  const compact = rawText.replace(/\s+/g, ' ').trim()
  if (!compact) return ''

  const ranges = findExactRanges(normalizeText(compact), term)
  const startGuess = ranges[occurrence]?.start ?? ranges[0]?.start ?? 0
  const start = Math.max(0, startGuess - 70)
  const end = Math.min(compact.length, start + 180)
  const prefix = start > 0 ? '... ' : ''
  const suffix = end < compact.length ? ' ...' : ''
  return `${prefix}${compact.slice(start, end)}${suffix}`
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
  pdfjsLib, pdfDoc, pageNum, scale, quote, fallbackQuote, searchTerm, activeSearchPage, activeSearchOccurrence, onVisible, placeholderHeight,
}: {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  pdfjsLib: any; pdfDoc: any; pageNum: number; scale: number;
  quote: string; fallbackQuote: string;
  searchTerm?: string; activeSearchPage?: number | null; activeSearchOccurrence?: number | null;
  onVisible?: (n: number) => void;
  placeholderHeight: number;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const overlayRef = useRef<HTMLDivElement>(null)
  const wrapRef = useRef<HTMLDivElement>(null)
  const [rendered, setRendered] = useState(false)
  const [renderError, setRenderError] = useState('')
  const [renderAttempt, setRenderAttempt] = useState(0)

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
      { threshold: 0.65 },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [pageNum, onVisible])

  // Renderiza o canvas quando a página está próxima
  useEffect(() => {
    if (!rendered || !pdfDoc) return
    let cancelled = false
    let timedOut = false
    let timeoutId: ReturnType<typeof setTimeout> | undefined
    let removeAbortListener = () => {}
    const controller = new AbortController()
    let renderTask: { promise: Promise<unknown>; cancel: () => void } | null = null
    const interrupted = new Promise<never>((_, reject) => {
      const onAbort = () => reject(new DOMException('Renderização cancelada.', 'AbortError'))
      controller.signal.addEventListener('abort', onAbort, { once: true })
      removeAbortListener = () => controller.signal.removeEventListener('abort', onAbort)
      timeoutId = setTimeout(() => {
        timedOut = true
        try {
          renderTask?.cancel()
        } catch {
          // A tarefa pode ter terminado entre o deadline e cancel().
        }
        controller.abort()
      }, PDF_PAGE_RENDER_TIMEOUT_MS)
    })

    async function renderPage() {
      setRenderError('')
      const page = await Promise.race([pdfDoc.getPage(pageNum), interrupted])
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
      const currentRenderTask = page.render({ canvasContext: ctx, viewport })
      renderTask = currentRenderTask
      await Promise.race([currentRenderTask.promise, interrupted])
      if (cancelled) return

      const activeQuote = quote || fallbackQuote
      const activeSearch = searchTerm?.trim()
      if (activeQuote || activeSearch) {
        const textContent = await Promise.race([page.getTextContent(), interrupted])
        const items = (textContent.items as PdfTextItem[]).filter((i) => i.str)
        const { parts, fullNormalized } = buildJoinedText(items)
        const addHighlight = (
          range: { start: number; end: number } | null,
          background: string,
          lineColor: string,
        ) => {
          if (!range) return
          parts
            .filter((p) => p.normalized && p.end > range.start && p.start < range.end)
            .forEach((p) => {
              const box = getItemBox(pdfjsLib, viewport, p.item)
              const bg = document.createElement('div')
              Object.assign(bg.style, {
                position: 'absolute', left: `${box.left}px`, top: `${box.top}px`,
                width: `${box.width}px`, height: `${box.height}px`,
                background, borderRadius: '2px', pointerEvents: 'none',
              })
              overlay.appendChild(bg)
              const line = document.createElement('div')
              Object.assign(line.style, {
                position: 'absolute', left: `${box.left}px`, top: `${box.top + box.height + 1}px`,
                width: `${box.width}px`, height: '2.5px', background: lineColor,
                borderRadius: '999px', pointerEvents: 'none',
              })
              overlay.appendChild(line)
            })
        }

        let quoteRange = quote ? findQuoteRange(fullNormalized, quote) : null
        if (!quoteRange && fallbackQuote) quoteRange = findQuoteRange(fullNormalized, fallbackQuote)
        addHighlight(quoteRange, 'rgba(255,220,0,0.28)', '#f5c518')

        if (activeSearch && (!activeSearchPage || activeSearchPage === pageNum)) {
          const searchRanges = findExactRanges(fullNormalized, activeSearch)
          searchRanges.forEach((range, index) => {
            const isActive = activeSearchOccurrence === null || activeSearchOccurrence === undefined || index === activeSearchOccurrence
            addHighlight(
              range,
              isActive ? 'rgba(34,211,238,0.34)' : 'rgba(34,211,238,0.16)',
              isActive ? '#22d3ee' : 'rgba(34,211,238,0.55)',
            )
          })
        }
      }
    }

    void renderPage().catch((error) => {
      if (cancelled) return
      const wasCancelled = error instanceof DOMException && error.name === 'AbortError'
      if (wasCancelled && !timedOut) return
      setRenderError(timedOut
        ? `A página ${pageNum} demorou demais para carregar.`
        : `Não foi possível carregar a página ${pageNum}.`)
    }).finally(() => {
      if (timeoutId !== undefined) clearTimeout(timeoutId)
      removeAbortListener()
    })
    return () => {
      cancelled = true
      controller.abort()
      try {
        renderTask?.cancel()
      } catch {
        // A renderização já terminou.
      }
      if (timeoutId !== undefined) clearTimeout(timeoutId)
      removeAbortListener()
    }
  }, [rendered, pdfDoc, pdfjsLib, pageNum, scale, quote, fallbackQuote, searchTerm, activeSearchPage, activeSearchOccurrence, renderAttempt])

  return (
    <div
      ref={wrapRef}
      className="relative w-full"
      style={rendered ? { minHeight: placeholderHeight } : undefined}
    >
      {rendered ? (
        <>
          <canvas ref={canvasRef} className="block" style={{ imageRendering: 'auto' }} />
          <div ref={overlayRef} className="pointer-events-none absolute left-0 top-0" />
          {renderError && (
            <div
              role="alert"
              className="absolute inset-0 z-10 flex min-h-40 flex-col items-center justify-center gap-3 bg-zinc-950/95 px-6 text-center text-sm text-zinc-200"
            >
              <span>{renderError}</span>
              <button
                type="button"
                className="rounded border border-amber-500/60 px-3 py-2 text-amber-300"
                onClick={() => setRenderAttempt((attempt) => attempt + 1)}
              >
                Tentar novamente
              </button>
            </div>
          )}
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
  const [fitScale, setFitScale] = useState(1.5)
  const [placeholderH, setPlaceholderH] = useState(800)
  const [pageMetrics, setPageMetrics] = useState<PageMetric[]>([])
  const [loading, setLoading] = useState(true)
  const [loadProgress, setLoadProgress] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isMobile, setIsMobile] = useState<boolean | null>(null)
  const [pageInput, setPageInput] = useState(String(initialPage))
  const [isEditingPage, setIsEditingPage] = useState(false)
  const [searchText, setSearchText] = useState('')
  const [submittedSearchText, setSubmittedSearchText] = useState('')
  const [searchResults, setSearchResults] = useState<SearchResult[]>([])
  const [activeSearchIndex, setActiveSearchIndex] = useState(0)
  const [searching, setSearching] = useState(false)
  const [searchMessage, setSearchMessage] = useState('')
  const [showSearch, setShowSearch] = useState(false)
  const [isIosStandalone, setIsIosStandalone] = useState(false)

  const pageRefs = useRef<(HTMLDivElement | null)[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const searchAbortRef = useRef<AbortController | null>(null)

  useEffect(() => () => searchAbortRef.current?.abort(), [])

  const estimatePageHeight = useCallback((index: number, targetScale = scale) => {
    const metric = pageMetrics[index] ?? pageMetrics[0]
    if (metric?.height) return Math.round(metric.height * targetScale)
    const currentScale = scale > 0 ? scale : targetScale || 1
    return Math.round(placeholderH * (targetScale / currentScale))
  }, [pageMetrics, placeholderH, scale])

  const getPageTop = useCallback((pageNumber: number, targetScale = scale) => {
    const target = Math.min(Math.max(1, pageNumber), numPages || 1)
    const wrapperGap = isMobile ? 0 : 24
    let top = 0
    for (let index = 0; index < target - 1; index += 1) {
      top += estimatePageHeight(index, targetScale) + wrapperGap
    }
    return Math.max(0, Math.round(top))
  }, [estimatePageHeight, isMobile, numPages, scale])

  const clampPage = useCallback((page: number) => {
    if (numPages <= 0) return 1
    return Math.min(Math.max(1, Math.round(page)), numPages)
  }, [numPages])

  const goToPage = useCallback((n: number, pageOffset = 0) => {
    if (numPages <= 0) return
    const target = clampPage(n)
    const container = scrollRef.current
    const targetTop = getPageTop(target, scale) + Math.max(0, Math.round(pageOffset * scale) - 72)
    if (container) {
      container.scrollTo({ top: targetTop, behavior: 'auto' })
    } else {
      const el = pageRefs.current[target - 1]
      el?.scrollIntoView({ block: 'start' })
    }
    setCurrentPage(target)
    setPageInput(String(target))
  }, [clampPage, getPageTop, numPages, scale])

  const goToSearchResult = useCallback((result: SearchResult) => {
    goToPage(result.page, result.top)
  }, [goToPage])

  const placeholderHeightForPage = useCallback((pageNum: number) => {
    return Math.max(120, estimatePageHeight(pageNum - 1, scale))
  }, [estimatePageHeight, scale])

  const handleScroll = useCallback(() => {
    const container = scrollRef.current
    if (!container || numPages <= 0) return

    const wrapperGap = isMobile ? 0 : 24
    const anchor = container.scrollTop + Math.max(48, container.clientHeight * 0.28)
    let cursor = 0
    let nextPage = 1
    for (let index = 0; index < numPages; index += 1) {
      const pageHeight = estimatePageHeight(index, scale) + wrapperGap
      if (anchor < cursor + pageHeight) {
        nextPage = index + 1
        break
      }
      cursor += pageHeight
      nextPage = index + 1
    }
    if (nextPage !== currentPage) setCurrentPage(nextPage)
  }, [currentPage, estimatePageHeight, isMobile, numPages, scale])

  // Detecta mobile uma vez no cliente
  useEffect(() => {
    const check = () => setIsMobile(window.innerWidth < 768)
    check()
    window.addEventListener('resize', check)
    return () => window.removeEventListener('resize', check)
  }, [])

  useEffect(() => {
    const standalone = 'standalone' in window.navigator && (window.navigator as Navigator & { standalone?: boolean }).standalone === true
    setIsIosStandalone(/iphone|ipad|ipod/i.test(window.navigator.userAgent) && standalone)
  }, [])

  useEffect(() => {
    const preventGesture = (event: Event) => event.preventDefault()
    const preventCtrlWheel = (event: WheelEvent) => {
      if (event.ctrlKey) event.preventDefault()
    }

    document.addEventListener('gesturestart', preventGesture, { passive: false })
    document.addEventListener('gesturechange', preventGesture, { passive: false })
    document.addEventListener('gestureend', preventGesture, { passive: false })
    document.addEventListener('wheel', preventCtrlWheel, { passive: false })

    return () => {
      document.removeEventListener('gesturestart', preventGesture)
      document.removeEventListener('gesturechange', preventGesture)
      document.removeEventListener('gestureend', preventGesture)
      document.removeEventListener('wheel', preventCtrlWheel)
    }
  }, [])

  // Carrega o PDF e calcula a escala baseada na tela
  useEffect(() => {
    if (!fileUrl || isMobile === null) return
    let cancelled = false
    const loadController = new AbortController()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let loadTask: any = null
    async function load() {
      setLoading(true)
      setLoadProgress(null)
      setError(null)
      setPdfDoc(null)
      setNumPages(0)
      setPageMetrics([])

      const lib = await import('pdfjs-dist')
      lib.GlobalWorkerOptions.workerSrc = '/pdf.worker.min.mjs'

      // Fetch only the byte ranges needed by visible pages. Streaming and
      // auto-fetch would otherwise continue downloading a 200MB+ volume after
      // page 1 is already available.
      loadTask = lib.getDocument({
        url: fileUrl,
        rangeChunkSize: 524288,
        disableRange: false,
        disableStream: true,
        disableAutoFetch: true,
      })
      loadTask.onProgress = ({ loaded, total }: { loaded: number; total?: number }) => {
        if (!cancelled && total && total > 0) {
          setLoadProgress(Math.min(100, Math.round((loaded / total) * 100)))
        }
      }

      const LOAD_TIMEOUT_MS = 120_000
      let timeoutId: ReturnType<typeof setTimeout> | null = null
      let removeAbortListener = () => {}
      const timeoutPromise = new Promise<never>((_, reject) => {
        timeoutId = setTimeout(
          () => reject(new Error('O PDF demorou muito para carregar. Tente novamente em alguns segundos.')),
          LOAD_TIMEOUT_MS,
        )
      })
      const cancelledPromise = new Promise<never>((_, reject) => {
        const onAbort = () => reject(new DOMException('Carregamento cancelado.', 'AbortError'))
        if (loadController.signal.aborted) {
          onAbort()
          return
        }
        loadController.signal.addEventListener('abort', onAbort, { once: true })
        removeAbortListener = () => loadController.signal.removeEventListener('abort', onAbort)
      })

      let doc: Awaited<typeof loadTask.promise>
      let firstPage: Awaited<ReturnType<typeof doc.getPage>>
      try {
        doc = await Promise.race([loadTask.promise, timeoutPromise, cancelledPromise])
        firstPage = await Promise.race([doc.getPage(1), timeoutPromise, cancelledPromise])
      } catch (loadError) {
        await loadTask.destroy().catch(() => {})
        throw loadError
      } finally {
        if (timeoutId !== null) clearTimeout(timeoutId)
        removeAbortListener()
      }
      if (cancelled) return

      // Calcula escala automática pela largura da tela (mobile) ou fixa (desktop)
      const baseVp = firstPage.getViewport({ scale: 1 })
      const firstMetric = { width: baseVp.width, height: baseVp.height }
      const autoScale = isMobile ? window.innerWidth / baseVp.width : 1.5

      // Seed all pages with the first page dimensions. Metrics are updated lazily
      // when each page renders — avoids blocking page 1 with 200+ getPage() calls.
      const initialMetrics = Array.from({ length: doc.numPages }, () => firstMetric)

      setScale(autoScale)
      setFitScale(autoScale)
      setPlaceholderH(Math.round(baseVp.height * autoScale))
      setPageMetrics(initialMetrics)

      setPdfjsLib(lib)
      setPdfDoc(doc)
      setNumPages(doc.numPages)
      setLoading(false)
    }
    load().catch((e) => {
      if (!cancelled) {
        const message = String(e?.message ?? '')
        const authError = /\b(401|403)\b|unauthorized|forbidden/i.test(message)
        setError(authError ? 'Sua sessão expirou. Entre novamente para abrir este PDF.' : (message || 'Erro ao carregar PDF.'))
        setLoading(false)
      }
    })
    return () => {
      cancelled = true
      loadController.abort()
      if (loadTask) void loadTask.destroy().catch(() => {})
    }
  }, [fileUrl, isMobile])

  // Scroll para a página inicial após o PDF carregar
  useEffect(() => {
    if (!pdfDoc || numPages <= 0) return
    requestAnimationFrame(() => goToPage(initialPage))
  }, [pdfDoc, numPages, initialPage, goToPage])

  useEffect(() => {
    if (!isEditingPage) setPageInput(String(currentPage))
  }, [currentPage, isEditingPage])

  const handleVisible = useCallback((n: number) => setCurrentPage(n), [])
  const activeSearch = searchResults[activeSearchIndex] ?? null

  function setScaleKeepingPosition(nextScale: number) {
    const container = scrollRef.current
    const page = clampPage(currentPage)
    const oldTop = getPageTop(page, scale)
    const offsetWithinPage = container ? Math.max(0, container.scrollTop - oldTop) / Math.max(scale, 0.01) : 0

    setScale(nextScale)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        const nextContainer = scrollRef.current
        if (!nextContainer) return
        nextContainer.scrollTop = getPageTop(page, nextScale) + Math.max(0, Math.round(offsetWithinPage * nextScale))
        setCurrentPage(page)
      })
    })
  }

  function zoomBy(delta: number) {
    const nextScale = Math.min(3, Math.max(0.45, Number((scale + delta).toFixed(2))))
    setScaleKeepingPosition(nextScale)
  }

  function resetZoom() {
    setScaleKeepingPosition(fitScale)
  }

  function commitPageInput() {
    const trimmed = pageInput.trim()
    if (!trimmed) {
      setPageInput(String(currentPage))
      return
    }
    const page = Number(trimmed)
    if (!Number.isFinite(page)) {
      setPageInput(String(currentPage))
      return
    }
    const target = clampPage(page)
    goToPage(target)
  }

  function handlePageSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setIsEditingPage(false)
    commitPageInput()
  }

  async function handleSearchSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const term = searchText.trim()
    setSearchResults([])
    setActiveSearchIndex(0)
    setSearchMessage('')
    setSubmittedSearchText(term)
    if (!term || !pdfDoc || numPages <= 0) return

    searchAbortRef.current?.abort()
    const controller = new AbortController()
    searchAbortRef.current = controller
    let timedOut = false
    let timeoutId: ReturnType<typeof setTimeout> | undefined
    let removeAbortListener = () => {}
    const interrupted = new Promise<never>((_, reject) => {
      const onAbort = () => reject(new DOMException('Busca cancelada.', 'AbortError'))
      controller.signal.addEventListener('abort', onAbort, { once: true })
      removeAbortListener = () => controller.signal.removeEventListener('abort', onAbort)
      timeoutId = setTimeout(() => {
        timedOut = true
        controller.abort()
      }, PDF_SEARCH_TIMEOUT_MS)
    })

    setSearching(true)
    try {
      const normalizedTerm = normalizeText(term)
      const found: SearchResult[] = []
      for (let pageNum = 1; pageNum <= numPages; pageNum += 1) {
        if (pageNum === 1 || pageNum % 10 === 0 || pageNum === numPages) {
          setSearchMessage(`Buscando na página ${pageNum} de ${numPages}...`)
        }
        const page = await Promise.race([pdfDoc.getPage(pageNum), interrupted])
        const textContent = await Promise.race([page.getTextContent(), interrupted])
        const items = (textContent.items as PdfTextItem[]).filter((item) => item.str)
        const rawText = items
          .map((item) => item.str)
          .join(' ')
          .replace(/\s+/g, ' ')
          .trim()
        const { parts, fullNormalized } = buildJoinedText(items)
        const ranges = findExactRanges(fullNormalized, normalizedTerm)
        if (ranges.length === 0) continue

        const viewport = page.getViewport({ scale: 1 })
        ranges.forEach((range, occurrence) => {
          const firstPart = parts.find((part) => part.normalized && part.end > range.start && part.start < range.end)
          const top = firstPart && pdfjsLib ? getItemBox(pdfjsLib, viewport, firstPart.item).top : 0
          found.push({
            page: pageNum,
            occurrence,
            top,
            preview: buildSearchPreview(rawText, term, occurrence),
          })
        })
      }

      setSearchResults(found)
      if (found.length > 0) {
        setSearchMessage(`Resultado 1 de ${found.length} na página ${found[0].page}.`)
        goToSearchResult(found[0])
      } else {
        setSearchMessage('Nenhum resultado encontrado neste PDF.')
      }
    } catch (error) {
      if (timedOut) {
        setSearchMessage('A busca no PDF excedeu dois minutos. Refine o termo e tente novamente.')
      } else if (controller.signal.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
        setSearchMessage('Busca cancelada.')
      } else {
        setSearchMessage('Não foi possível buscar o texto neste PDF.')
      }
    } finally {
      if (timeoutId !== undefined) clearTimeout(timeoutId)
      removeAbortListener()
      if (searchAbortRef.current === controller) searchAbortRef.current = null
      setSearching(false)
    }
  }

  function cancelPdfSearch() {
    searchAbortRef.current?.abort()
  }

  function moveSearch(delta: number) {
    if (searchResults.length === 0) return
    const nextIndex = (activeSearchIndex + delta + searchResults.length) % searchResults.length
    const result = searchResults[nextIndex]
    setActiveSearchIndex(nextIndex)
    setSearchMessage(`Resultado ${nextIndex + 1} de ${searchResults.length} na página ${result.page}.`)
    goToSearchResult(result)
  }

  if (isMobile === null) {
    return (
      <div className="min-h-screen bg-zinc-950 flex items-center justify-center">
        <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
      </div>
    )
  }

  return (
    <div className="fixed inset-0 flex flex-col bg-zinc-950 text-white" style={{ height: '100dvh' }}>

      {isMobile ? (
        <div
          className="shrink-0 sticky top-0 z-20 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur-sm"
          style={{ paddingTop: isIosStandalone ? 'calc(max(env(safe-area-inset-top), 44px) + 4px)' : 'calc(env(safe-area-inset-top) + 4px)' }}
        >
          <div className="flex h-11 min-w-0 items-center gap-0.5 px-2">
            <button type="button" onClick={() => router.back()} className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-zinc-300 transition-colors hover:bg-zinc-800" aria-label="Voltar">‹</button>
            <span className="min-w-0 flex-1 truncate text-[11px] text-zinc-500">PDF</span>
            <button type="button" onClick={() => zoomBy(-0.15)} className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-zinc-300 transition-colors hover:bg-zinc-800" aria-label="Diminuir zoom">−</button>
            <button type="button" onClick={resetZoom} className="w-9 shrink-0 text-center text-[11px] tabular-nums text-zinc-500" aria-label="Redefinir zoom">{Math.round(scale * 100)}%</button>
            <button type="button" onClick={() => zoomBy(0.15)} className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-zinc-300 transition-colors hover:bg-zinc-800" aria-label="Aumentar zoom">+</button>
            <form onSubmit={handlePageSubmit} className="flex shrink-0 items-center gap-1">
              <label htmlFor="pdf-page-input-mobile" className="sr-only">Pagina</label>
              <input
                id="pdf-page-input-mobile"
                type="number"
                min={1}
                max={numPages || undefined}
                value={pageInput}
                onFocus={() => setIsEditingPage(true)}
                onBlur={() => { setIsEditingPage(false); commitPageInput() }}
                onChange={(event) => setPageInput(event.target.value)}
                className="h-8 w-11 rounded border border-zinc-700 bg-zinc-900 px-1 text-center text-xs text-zinc-100 outline-none focus:border-amber-400"
                aria-label="Pagina"
              />
              <span className="max-w-8 truncate text-[10px] text-zinc-500">/{numPages || '-'}</span>
            </form>
            <button
              type="button"
              onClick={() => setShowSearch((visible) => !visible)}
              aria-pressed={showSearch}
              className={`flex h-8 w-8 shrink-0 items-center justify-center rounded transition-colors ${
                showSearch ? 'bg-amber-400 text-zinc-950' : 'text-zinc-300 hover:bg-zinc-800'
              }`}
              aria-label="Buscar no PDF"
            >
              ⌕
            </button>
          </div>
          {showSearch && (
            <form onSubmit={handleSearchSubmit} className="flex gap-2 px-2 pb-2">
              <label htmlFor="pdf-search-input-mobile" className="sr-only">Buscar no texto</label>
              <input
                id="pdf-search-input-mobile"
                type="search"
                value={searchText}
                onChange={(event) => setSearchText(event.target.value)}
                placeholder="Buscar palavra ou trecho"
                className="h-9 min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-900 px-2 text-sm text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-amber-400"
              />
              <button
                type={searching ? 'button' : 'submit'}
                onClick={searching ? cancelPdfSearch : undefined}
                disabled={!searching && (!searchText.trim() || !pdfDoc)}
                className="h-9 rounded bg-amber-400 px-3 text-xs font-semibold text-zinc-950 transition-colors hover:bg-amber-300 disabled:opacity-40"
              >
                {searching ? 'Cancelar' : 'Buscar'}
              </button>
            </form>
          )}
        </div>
      ) : (
        <div className="shrink-0 sticky top-0 z-20 flex flex-wrap items-center gap-2 border-b border-zinc-800 bg-zinc-950/95 px-3 py-2 backdrop-blur-sm">
          <button onClick={() => router.back()} className="flex items-center gap-1 rounded px-2 py-1.5 text-sm text-zinc-400 hover:bg-zinc-800 active:scale-95 transition-all">
            <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" /></svg>
            Voltar
          </button>
          <span className="text-xs text-zinc-500 ml-1">Visualizador de PDF</span>
          <form onSubmit={handlePageSubmit} className="flex items-center gap-1">
            <label htmlFor="pdf-page-input" className="sr-only">Pagina</label>
            <input id="pdf-page-input" type="number" min={1} max={numPages || undefined} value={pageInput} onFocus={() => setIsEditingPage(true)} onBlur={() => { setIsEditingPage(false); commitPageInput() }} onChange={(event) => setPageInput(event.target.value)} className="h-8 w-16 rounded border border-zinc-700 bg-zinc-900 px-2 text-xs text-zinc-100 outline-none focus:border-amber-400" aria-label="Pagina" />
            <button type="submit" disabled={numPages <= 0} className="h-8 rounded border border-zinc-700 px-2 text-xs text-zinc-300 transition-colors hover:border-amber-400 hover:text-amber-300 disabled:opacity-40">Ir</button>
          </form>
          <form onSubmit={handleSearchSubmit} className="flex min-w-0 flex-1 items-center gap-1 sm:max-w-sm">
            <label htmlFor="pdf-search-input" className="sr-only">Buscar no texto</label>
            <input id="pdf-search-input" type="search" value={searchText} onChange={(event) => setSearchText(event.target.value)} placeholder="Buscar palavra ou trecho" className="h-8 min-w-0 flex-1 rounded border border-zinc-700 bg-zinc-900 px-2 text-xs text-zinc-100 outline-none placeholder:text-zinc-500 focus:border-amber-400" />
            <button type={searching ? 'button' : 'submit'} onClick={searching ? cancelPdfSearch : undefined} disabled={!searching && (!searchText.trim() || !pdfDoc)} className="h-8 rounded bg-amber-400 px-3 text-xs font-semibold text-zinc-950 transition-colors hover:bg-amber-300 disabled:opacity-40">{searching ? 'Cancelar' : 'Buscar'}</button>
          </form>
          <div className="flex items-center gap-1">
            <button onClick={() => zoomBy(-0.2)} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 text-lg font-light">−</button>
            <button type="button" onClick={resetZoom} className="text-xs text-zinc-500 w-10 text-center" aria-label="Redefinir zoom">{Math.round(scale * 100)}%</button>
            <button onClick={() => zoomBy(0.2)} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 text-lg font-light">+</button>
          </div>
          {numPages > 0 && (
            <div className="flex items-center gap-1">
              <button onClick={() => goToPage(currentPage - 1)} disabled={currentPage <= 1} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 disabled:opacity-30">
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M11.78 5.22a.75.75 0 0 1 0 1.06L8.06 10l3.72 3.72a.75.75 0 1 1-1.06 1.06l-4.25-4.25a.75.75 0 0 1 0-1.06l4.25-4.25a.75.75 0 0 1 1.06 0Z" clipRule="evenodd" /></svg>
              </button>
              <span className="text-xs text-zinc-400 whitespace-nowrap tabular-nums">{currentPage} / {numPages}</span>
              <button onClick={() => goToPage(currentPage + 1)} disabled={currentPage >= numPages} className="w-8 h-8 flex items-center justify-center rounded text-zinc-400 hover:bg-zinc-800 active:scale-95 disabled:opacity-30">
                <svg viewBox="0 0 20 20" fill="currentColor" className="w-4 h-4"><path fillRule="evenodd" d="M8.22 5.22a.75.75 0 0 1 1.06 0l4.25 4.25a.75.75 0 0 1 0 1.06L9.28 14.78a.75.75 0 0 1-1.06-1.06L12.44 10 8.22 6.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" /></svg>
              </button>
            </div>
          )}
        </div>
      )}

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
      {(searchMessage || activeSearch) && (
        <div className="shrink-0 flex flex-col gap-2 border-b border-cyan-900/40 bg-cyan-950/30 px-3 py-2 text-xs text-cyan-100 sm:flex-row sm:items-center sm:justify-between">
          <p className="min-w-0 leading-relaxed">
            {searchMessage || `Resultado ${activeSearchIndex + 1} de ${searchResults.length} na página ${activeSearch?.page}.`}
            {activeSearch?.preview ? (
              <span className="ml-2 text-cyan-200/70">
                {activeSearch.preview.slice(0, 110)}{activeSearch.preview.length > 110 ? '...' : ''}
              </span>
            ) : null}
          </p>
          {searchResults.length > 1 && (
            <div className="flex shrink-0 gap-1">
              <button
                type="button"
                onClick={() => moveSearch(-1)}
                className="rounded border border-cyan-700 px-2 py-1 text-cyan-100 transition-colors hover:bg-cyan-900"
              >
                Anterior
              </button>
              <button
                type="button"
                onClick={() => moveSearch(1)}
                className="rounded border border-cyan-700 px-2 py-1 text-cyan-100 transition-colors hover:bg-cyan-900"
              >
                Proximo
              </button>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="flex-1 flex flex-col items-center justify-center gap-4 px-6 text-center">
          <span className="w-3 h-3 rounded-full bg-amber-400 animate-pulse" />
          <div>
            <p className="text-sm text-zinc-300 font-medium">Carregando PDF…</p>
            <p className="mt-1 text-xs text-zinc-500">
              {loadProgress != null
                ? `Preparando a primeira página (${loadProgress}%)…`
                : 'Preparando a primeira página sem baixar o volume inteiro…'}
            </p>
          </div>
        </div>
      )}
      {error && (
        <div className="flex-1 flex flex-col items-center justify-center gap-3 px-6 text-center">
          <p className="text-sm text-red-400">{error}</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded border border-zinc-700 px-4 py-1.5 text-xs text-zinc-300 hover:bg-zinc-800 transition-colors"
          >
            Tentar novamente
          </button>
        </div>
      )}

      {/* ── Scroll contínuo de páginas ── */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="flex-1 overflow-auto"
        style={{
          touchAction: 'pan-x pan-y',
          WebkitOverflowScrolling: 'touch',
          overscrollBehavior: 'contain',
          paddingBottom: isMobile ? (isIosStandalone ? 'max(env(safe-area-inset-bottom), 16px)' : 'env(safe-area-inset-bottom)') : undefined,
        } as React.CSSProperties}
      >
        {pdfDoc && Array.from({ length: numPages }, (_, i) => i + 1).map((pageNum) => (
          <div
            key={pageNum}
            ref={(el) => { pageRefs.current[pageNum - 1] = el }}
            className={isMobile ? 'px-0 py-0' : 'flex justify-center px-2 py-3'}
          >
            <PdfPageCanvas
              pdfjsLib={pdfjsLib}
              pdfDoc={pdfDoc}
              pageNum={pageNum}
              scale={scale}
              quote={quote}
              fallbackQuote={fallbackQuote}
              searchTerm={searchResults.length > 0 ? submittedSearchText : ''}
              activeSearchPage={activeSearch?.page ?? null}
              activeSearchOccurrence={activeSearch?.occurrence ?? null}
              onVisible={handleVisible}
              placeholderHeight={placeholderHeightForPage(pageNum)}
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
