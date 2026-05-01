'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'

const API_KEY = process.env.NEXT_PUBLIC_API_KEY ?? ''

interface Props {
  fileId: number
  initialPage?: number
  apiBase: string
}

export default function PdfViewer({ fileId, initialPage = 1, apiBase }: Props) {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const mql = window.matchMedia('(pointer: coarse), (max-width: 768px)')
    setIsMobile(mql.matches)
  }, [])

  const keyParam = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : ''
  const pdfUrl = `${apiBase}/pdfs/${fileId}${keyParam}`

  if (isMobile) {
    // On mobile: use the in-app PDF.js viewer (no external redirect)
    const viewerHref = `/viewer/pdf?file=${encodeURIComponent(pdfUrl)}&page=${initialPage}`
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-6 p-8 text-center">
        <div className="rounded-full bg-vinho-escuro/40 p-5">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-10 h-10 text-dourado">
            <path d="M5.625 1.5c-1.036 0-1.875.84-1.875 1.875v17.25c0 1.035.84 1.875 1.875 1.875h12.75c1.035 0 1.875-.84 1.875-1.875V12.75A3.75 3.75 0 0 0 16.5 9h-1.875a1.875 1.875 0 0 1-1.875-1.875V5.25A3.75 3.75 0 0 0 9 1.5H5.625Z" />
            <path d="M12.971 1.816A5.23 5.23 0 0 1 14.25 5.25v1.875c0 .207.168.375.375.375H16.5a5.23 5.23 0 0 1 3.434 1.279 9.768 9.768 0 0 0-6.963-6.963Z" />
          </svg>
        </div>
        <div className="space-y-2">
          <p className="text-base font-medium text-texto">Visualizar documento</p>
          <p className="text-sm text-texto-secundario max-w-xs mx-auto leading-relaxed">
            Toque para abrir o visualizador integrado com navegação por páginas.
          </p>
        </div>
        <Link
          href={viewerHref}
          className="rounded-lg bg-vinho px-7 py-3 text-sm font-semibold text-texto transition-colors hover:bg-vinho-claro active:scale-95"
        >
          Abrir PDF
        </Link>
      </div>
    )
  }

  return (
    <iframe
      src={`${pdfUrl}#page=${initialPage}`}
      className="flex-1 w-full border-0"
      title="Visualizador de PDF"
    />
  )
}
