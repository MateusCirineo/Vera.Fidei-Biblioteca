import { NextRequest, NextResponse } from 'next/server'

// Server-side requests must use the Docker network. Calling the public URL here
// would send /api/pdfs back through Nginx and recurse into this same handler.
const BASE = process.env.INTERNAL_API_URL ?? 'http://backend:8000'
const API_KEY = process.env.INTERNAL_API_KEY ?? process.env.NEXT_PUBLIC_API_KEY ?? ''

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ fileId: string }> },
) {
  const token = readToken(request)
  if (!token) {
    return NextResponse.json({ detail: 'Sessao expirada. Entre novamente.' }, { status: 401 })
  }

  const { fileId } = await context.params
  if (!/^\d+$/.test(fileId)) {
    return NextResponse.json({ detail: 'Arquivo invalido.' }, { status: 400 })
  }

  const upstreamUrl = new URL(`${BASE}/pdfs/${fileId}`)
  const rangeHeader = request.headers.get('range')
  const requestedStream = request.nextUrl.searchParams.get('stream')
  if (requestedStream) upstreamUrl.searchParams.set('stream', requestedStream)
  if (request.nextUrl.searchParams.get('download')) {
    upstreamUrl.searchParams.set('download', '1')
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  }
  if (API_KEY) headers['X-API-Key'] = API_KEY
  const forwardedApiKey = request.headers.get('x-api-key')
  if (forwardedApiKey) headers['X-API-Key'] = forwardedApiKey
  if (rangeHeader) headers.Range = rangeHeader

  const res = await fetch(upstreamUrl.toString(), {
    headers,
    cache: 'no-store',
  })

  if (!res.ok && res.status !== 206) {
    const detail = await res.text().catch(() => 'Erro ao abrir PDF.')
    return new NextResponse(detail, {
      status: res.status,
      headers: {
        'Content-Type': res.headers.get('content-type') ?? 'text/plain; charset=utf-8',
        'Cache-Control': 'no-store',
      },
    })
  }

  return new NextResponse(res.body, {
    status: res.status,
    headers: copyPdfHeaders(res.headers),
  })
}

function copyPdfHeaders(headers: Headers): Headers {
  const responseHeaders = new Headers()
  for (const key of [
    'accept-ranges',
    'content-disposition',
    'content-length',
    'content-range',
    'content-type',
    'etag',
    'last-modified',
    'x-accel-redirect',
  ]) {
    const value = headers.get(key)
    if (value) responseHeaders.set(key, value)
  }
  if (!responseHeaders.has('content-type')) {
    responseHeaders.set('content-type', 'application/pdf')
  }
  responseHeaders.set('cache-control', 'private, max-age=60, must-revalidate')
  responseHeaders.set('vary', 'Range')
  return responseHeaders
}

function readToken(request: NextRequest): string {
  const authHeader = request.headers.get('authorization')
  if (authHeader) {
    const [type, value] = authHeader.split(' ')
    if (type?.toLowerCase() === 'bearer' && value) {
      return value
    }
  }

  const cookieValue = request.cookies.get('vf_token')?.value
  if (!cookieValue) return ''
  try {
    return decodeURIComponent(cookieValue)
  } catch {
    return cookieValue
  }
}
