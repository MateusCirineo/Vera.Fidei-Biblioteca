import PdfViewer from '@/components/PdfViewer'
import BackButton from '@/components/BackButton'

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8001'

export default async function VisualizarPage({
  params,
  searchParams,
}: {
  params: Promise<{ fileId: string }>
  searchParams: Promise<{ pagina?: string }>
}) {
  const { fileId } = await params
  const { pagina } = await searchParams
  const fileIdNum = parseInt(fileId, 10)
  const initialPage = pagina ? parseInt(pagina, 10) : 1

  return (
    <div className="flex flex-col h-[100dvh] bg-fundo">
      <header className="flex items-center gap-3 px-4 py-3 border-b border-fundo-borda bg-fundo-card shrink-0">
        <BackButton />
        <span className="text-sm text-texto-terciario">Visualizador de PDF</span>
      </header>

      <PdfViewer fileId={fileIdNum} initialPage={initialPage} apiBase={API_BASE} />
    </div>
  )
}
