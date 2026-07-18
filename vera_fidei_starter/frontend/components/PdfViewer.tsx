'use client'

import { useEffect, useState } from 'react'

interface Props {
  fileId: number
  initialPage?: number
}

export default function PdfViewer({ fileId, initialPage = 1 }: Props) {
  const [isMobile, setIsMobile] = useState(false)

  useEffect(() => {
    const mql = window.matchMedia('(pointer: coarse), (max-width: 768px)')
    const update = () => setIsMobile(mql.matches)
    update()
    mql.addEventListener('change', update)
    return () => mql.removeEventListener('change', update)
  }, [])

  const pdfUrl = `/pdfs/${fileId}`
  const viewerHref = `/viewer/pdf?file=${encodeURIComponent(pdfUrl)}&page=${initialPage}`

  if (!isMobile) {
    return (
      <iframe
        src={`${pdfUrl}#page=${initialPage}`}
        className="flex-1 w-full border-0"
        title="Visualizador de PDF"
      />
    )
  }

  return (
    <iframe
      src={viewerHref}
      className="fixed inset-0 z-[100] h-dvh w-screen border-0 bg-zinc-950"
      title="Visualizador de PDF"
    />
  )
}
