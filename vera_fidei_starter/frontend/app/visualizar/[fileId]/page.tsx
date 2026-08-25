import { notFound, redirect } from 'next/navigation'

export default async function VisualizarPage({
  params,
  searchParams,
}: {
  params: Promise<{ fileId: string }>
  searchParams: Promise<{ page?: string; pagina?: string }>
}) {
  const { fileId } = await params
  const { page, pagina } = await searchParams
  const fileIdNum = parseInt(fileId, 10)
  if (!Number.isSafeInteger(fileIdNum) || fileIdNum <= 0) notFound()

  const requestedPage = page ?? pagina
  const parsedPage = requestedPage ? parseInt(requestedPage, 10) : 1
  const initialPage = Number.isSafeInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1
  const query = new URLSearchParams({
    file: `/api/pdfs/${fileIdNum}`,
    page: String(initialPage),
  })
  redirect(`/viewer/pdf?${query.toString()}`)
}
