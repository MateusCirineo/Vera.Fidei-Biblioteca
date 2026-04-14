interface Props {
  fileId: number
  initialPage?: number
  apiBase: string
}

export default function PdfViewer({ fileId, initialPage = 1, apiBase }: Props) {
  const src = `${apiBase}/pdfs/${fileId}#page=${initialPage}`

  return (
    <iframe
      src={src}
      className="flex-1 w-full border-0"
      title="Visualizador de PDF"
    />
  )
}
