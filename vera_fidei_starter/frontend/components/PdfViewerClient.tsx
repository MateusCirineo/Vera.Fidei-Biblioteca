'use client'

import dynamic from 'next/dynamic'

const PdfViewer = dynamic(() => import('./PdfViewer'), { ssr: false })

interface Props {
  fileId: number
  initialPage: number
  apiBase: string
}

export default function PdfViewerClient(props: Props) {
  return <PdfViewer {...props} />
}
